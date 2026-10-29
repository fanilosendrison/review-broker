import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from jsonschema import Draft202012Validator

from review_broker.admission import (
    AdmissionError,
    AuthorizationPolicy,
    authorize,
    resolve_request,
    select_operational_admission,
)
from review_broker.identity import (
    attempt_identity,
    request_identity,
    review_intent_identity,
)
from review_broker.predecessor import (
    PredecessorAuthority,
    PredecessorError,
    verify_v2_operation,
)
from review_broker.queue import AttemptRecord, AttemptState, InMemoryJournal
from review_broker.request import (
    RequestContractError,
    build_issue_body,
    parse_issue_body,
    validate_request,
)
from review_broker.requester import request_v2

ROOT = Path(__file__).parents[1]
V1 = json.loads((ROOT / "tests/fixtures/sample-request.json").read_text())
ISSUE28_REQUEST = json.loads(
    (ROOT / "tests/fixtures/issue28-request-v1.json").read_text()
)
ISSUE28_REQUEST_ID = "request:sha256:b7be8e246a6794135979b9e7818c96d8cab59bcfa9c5e7f219683aa316ea260f"
ISSUE28_ATTEMPT_ID = "attempt:sha256:81b20128c1e1bb4c2263ab64e3ef70b51d5ba79deb40df5fb52ef73eaf7a5702"
ISSUE28_HEAD = "06da37a80c49cd33c6a50c7b6edd256395873a8c"


def v2(kind="initial", *, head="a" * 40, previous=None, nonce=None):
    value = copy.deepcopy(V1)
    value["schema_version"] = 2
    value["subject"]["expected_head_commit"] = head
    operation = {"kind": kind}
    if previous is not None:
        operation["previous_request_id"] = previous
    if nonce is not None:
        operation["authorization_nonce"] = nonce
    value["review_operation"] = operation
    return value


def resolved(request):
    head = request["subject"].get("expected_head_commit", ISSUE28_HEAD)
    value = {
        "schema_version": 1,
        "request": request,
        "request_id": request_identity(request),
        "subject": {
            "kind": "github_pr",
            "repository": request["subject"]["repository"],
            "repository_id": 7,
            "pull_request": request["subject"]["pull_request"],
            "head_commit": head,
            "base_commit": "b" * 40,
            "merge_base": "c" * 40,
        },
        "subject_id": "subject:sha256:" + "d" * 64,
        "mission_id": "mission:sha256:" + "e" * 64,
        "policy_id": "policy:sha256:" + "f" * 64,
    }
    if request.get("schema_version") == 2:
        value["review_intent_id"] = review_intent_identity(request)
    return value


class FakeJournal:
    def __init__(self, records):
        self.records = records

    def get(self, request_id):
        if request_id not in self.records:
            raise KeyError(request_id)
        return self.records[request_id]


class V2SchemaAndIdentityTests(unittest.TestCase):
    def test_public_and_packaged_schema_are_identical_and_valid(self):
        public = (ROOT / "schemas/review-request-v2.schema.json").read_bytes()
        packaged = (ROOT / "src/review_broker/schemas/review-request-v2.schema.json").read_bytes()
        self.assertEqual(public, packaged)
        Draft202012Validator.check_schema(json.loads(public))

    def test_all_operation_shapes_validate(self):
        predecessor = "request:sha256:" + "1" * 64
        for request in (
            v2(),
            v2("changed_head", previous=predecessor),
            v2("repeat_same_head", previous=predecessor, nonce="2" * 32),
        ):
            validate_request(request)

    def test_invalid_operation_combinations_fail(self):
        predecessor = "request:sha256:" + "1" * 64
        invalid = (
            v2("initial", previous=predecessor),
            v2("changed_head", previous=predecessor, nonce="2" * 32),
            v2("repeat_same_head", previous=predecessor),
        )
        for request in invalid:
            with self.assertRaises(RequestContractError):
                validate_request(request)

    def test_versioned_envelope_rejects_mixed_and_disagreement(self):
        request = v2()
        body = build_issue_body(request)
        self.assertEqual(parse_issue_body(body), request)
        with self.assertRaises(RequestContractError):
            parse_issue_body(body + "\n<!-- review-broker-request:v1 -->")
        with self.assertRaisesRegex(RequestContractError, "disagree"):
            parse_issue_body(body.replace('"schema_version":2', '"schema_version":1'))

    def test_review_intent_is_stable_across_heads_and_sensitive_to_purpose(self):
        first = v2(head="1" * 40)
        second = v2(head="2" * 40)
        self.assertEqual(review_intent_identity(first), review_intent_identity(second))
        second["mission"]["objective"] += " changed"
        self.assertNotEqual(review_intent_identity(first), review_intent_identity(second))
        second = v2(head="2" * 40)
        second["policy"]["profile"] = "architecture"
        self.assertNotEqual(review_intent_identity(first), review_intent_identity(second))

    def test_v1_identity_and_envelope_are_unchanged(self):
        expected = request_identity(V1)
        self.assertEqual(expected, "request:sha256:b2c0e6e3056d67777a0ce02e417503dc5f1d42e0bf310da5b1b4fb6a6994aa91")
        self.assertEqual(
            attempt_identity(expected, 1),
            "attempt:sha256:745de04b6ceb36d56ffcc775abf36b9c5a67af2b0d6bfd87b398713856aab754",
        )
        self.assertIn("<!-- review-broker-request:v1 -->", build_issue_body(V1))
        self.assertNotIn("Review-Intent-ID", build_issue_body(V1))

    def test_exact_head_is_enforced_by_request_not_environment(self):
        request = v2(head="1" * 40)

        def getter(endpoint):
            if "/pulls/" in endpoint:
                return {"head": {"sha": "2" * 40}, "base": {"sha": "b" * 40, "repo": {"id": 7}}}
            return {"merge_base_commit": {"sha": "c" * 40}}

        with self.assertRaisesRegex(AdmissionError, "PR_HEAD_MISMATCH"):
            resolve_request(request, getter)

    def test_v2_operational_admission_is_default_disabled(self):
        with self.assertRaisesRegex(AdmissionError, "V2_OPERATIONAL_ADMISSION_DISABLED"):
            select_operational_admission(v2(), {}, lambda endpoint: {})


class V2PredecessorTests(unittest.TestCase):
    def authority(self, predecessors, results=None):
        records = {
            request_id: AttemptRecord(
                request_id=request_id,
                attempt_id=attempt_identity(request_id, 1),
                state=AttemptState.REQUESTED,
                admission=value,
            )
            for request_id, value in predecessors.items()
        }
        results = results or {}
        return PredecessorAuthority(
            FakeJournal(records),
            lambda: tuple(records),
            lambda request_id: results[request_id],
        )

    def test_initial_rejects_known_same_intent(self):
        predecessor_request = v2(head="1" * 40)
        predecessor = resolved(predecessor_request)
        current = v2(head="2" * 40)
        authority = self.authority({predecessor["request_id"]: predecessor})
        with self.assertRaisesRegex(PredecessorError, "INITIAL_REVIEW_INTENT_ALREADY_EXISTS"):
            verify_v2_operation(current, resolved(current), authority)

    def test_duplicate_initial_delivery_reuses_its_existing_claim(self):
        request = v2()
        admission = resolved(request)
        verify_v2_operation(
            request,
            admission,
            self.authority({admission["request_id"]: admission}),
        )

    def test_changed_head_accepts_authenticated_different_head(self):
        old_request = v2(head="1" * 40)
        old = resolved(old_request)
        current = v2("changed_head", head="2" * 40, previous=old["request_id"])
        verify_v2_operation(current, resolved(current), self.authority({old["request_id"]: old}))
        same = v2("changed_head", head="1" * 40, previous=old["request_id"])
        with self.assertRaisesRegex(PredecessorError, "DIFFERENT_HEAD"):
            verify_v2_operation(same, resolved(same), self.authority({old["request_id"]: old}))

    def test_repeat_requires_same_intent_and_head(self):
        old_request = v2(head="1" * 40)
        old = resolved(old_request)
        current = v2(
            "repeat_same_head", head="1" * 40,
            previous=old["request_id"], nonce="3" * 32,
        )
        verify_v2_operation(current, resolved(current), self.authority({old["request_id"]: old}))
        mismatch = copy.deepcopy(current)
        mismatch["mission"]["objective"] += " changed"
        with self.assertRaisesRegex(PredecessorError, "INTENT_MISMATCH"):
            verify_v2_operation(mismatch, resolved(mismatch), self.authority({old["request_id"]: old}))

    def test_missing_or_forged_predecessor_fails(self):
        missing = "request:sha256:" + "9" * 64
        current = v2("changed_head", previous=missing)
        with self.assertRaisesRegex(PredecessorError, "CLAIM_NOT_FOUND"):
            verify_v2_operation(current, resolved(current), self.authority({}))
        forged_request = v2(head="1" * 40)
        forged = resolved(forged_request)
        forged["request_id"] = "request:sha256:" + "8" * 64
        with self.assertRaisesRegex(PredecessorError, "RESOLVED_REQUEST_INVALID"):
            self.authority({forged["request_id"]: forged}).get(forged["request_id"])

    def test_issue28_shaped_invalid_result_is_valid_predecessor_evidence_only(self):
        record = AttemptRecord(
            request_id=ISSUE28_REQUEST_ID,
            attempt_id=ISSUE28_ATTEMPT_ID,
            state=AttemptState.STOPPED,
        )
        result = {
            "request_id": ISSUE28_REQUEST_ID,
            "attempt_id": ISSUE28_ATTEMPT_ID,
            "evidence_status": "INVALID",
            "resolved_request": {
                **resolved(ISSUE28_REQUEST),
                "request_id": ISSUE28_REQUEST_ID,
            },
        }
        authority = PredecessorAuthority(
            FakeJournal({ISSUE28_REQUEST_ID: record}),
            lambda: (ISSUE28_REQUEST_ID,),
            lambda request_id: result,
        )
        current = copy.deepcopy(ISSUE28_REQUEST)
        current["schema_version"] = 2
        current["subject"]["expected_head_commit"] = ISSUE28_HEAD
        current["review_operation"] = {
            "kind": "repeat_same_head",
            "previous_request_id": ISSUE28_REQUEST_ID,
            "authorization_nonce": "4" * 32,
        }
        verify_v2_operation(current, resolved(current), authority)
        evidence = authority.get(ISSUE28_REQUEST_ID)
        self.assertEqual(evidence.head_commit, ISSUE28_HEAD)
        self.assertEqual(evidence.evidence_status, "INVALID")

    def test_repeat_nonce_reuse_and_distinct_attempt_identity(self):
        old_request = v2(head="1" * 40)
        old = resolved(old_request)
        first_repeat = v2(
            "repeat_same_head", head="1" * 40,
            previous=old["request_id"], nonce="5" * 32,
        )
        first = resolved(first_repeat)
        second = copy.deepcopy(first_repeat)
        second["review_operation"]["previous_request_id"] = first["request_id"]
        with self.assertRaisesRegex(PredecessorError, "NONCE_REUSED"):
            verify_v2_operation(
                second,
                resolved(second),
                self.authority({old["request_id"]: old, first["request_id"]: first}),
            )
        self.assertNotEqual(request_identity(old_request), request_identity(first_repeat))
        self.assertNotEqual(
            attempt_identity(request_identity(old_request), 1),
            attempt_identity(request_identity(first_repeat), 1),
        )

    def test_duplicate_claim_reuses_one_ordinal_one_attempt(self):
        request = v2()
        admission = resolved(request)
        journal = InMemoryJournal()
        first = journal.claim(admission["request_id"], admission)
        second = journal.claim(admission["request_id"], admission)
        self.assertEqual(journal.attempt_count, 1)
        self.assertEqual(first, second)
        self.assertEqual(first.attempt_id, attempt_identity(admission["request_id"], 1))


class RequesterV2Tests(unittest.TestCase):
    def test_request_v2_uses_caller_bytes_and_reports_both_identities(self):
        request = v2("repeat_same_head", previous="request:sha256:" + "6" * 64, nonce="7" * 32)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "request.json"
            path.write_text(json.dumps(request), encoding="utf-8")
            args = type("Args", (), {"request_file": path, "broker_repo": "owner/broker"})()
            outcome = type("Outcome", (), {"stdout": "https://example.invalid/issues/1\n"})()
            with mock.patch("review_broker.requester._run", return_value=outcome) as run, \
                    mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(request_v2(args), 0)
            command = run.call_args.args[0]
            self.assertEqual(command[:4], ["gh", "issue", "create", "--repo"])
            self.assertIn(f"REQUEST_ID={request_identity(request)}", output.getvalue())
            self.assertIn(f"REVIEW_INTENT_ID={review_intent_identity(request)}", output.getvalue())


if __name__ == "__main__":
    unittest.main()
