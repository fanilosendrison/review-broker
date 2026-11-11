from __future__ import annotations

from copy import deepcopy
import unittest

from review_broker.admission_v3 import (
    AdmissionV3CandidateError, SubjectSourceFeasibilityV3,
    admit_initial_inline_v3,
)
from review_broker.admission_evidence_v3 import validate_journal_admission_v3
from review_broker.request_v3 import build_issue_envelope_v3
from tests.request_v3_test_support import (
    HEAD, REPOSITORY, REPOSITORY_ID, HistoryAuthority, PrAuthority,
    RequesterAuthority, SourceAuthority, origin, request,
)


class AdmissionV3CandidateTests(unittest.TestCase):
    def admit(self, observed=None, **authorities):
        return admit_initial_inline_v3(
            observed or origin(), broker_issue_number=51,
            expected_broker_issue_id=6106789428,
            expected_requester_id=30498238,
            requester_authority=authorities.get("requester", RequesterAuthority()),
            pr_authority=authorities.get("pr", PrAuthority()),
            source_authority=authorities.get("source", SourceAuthority()),
            history_authority=authorities.get("history", HistoryAuthority()),
        )

    def test_initial_empty_and_inline_admission_produce_journal_fields(self) -> None:
        empty = self.admit()
        self.assertEqual(empty.reference_ids, ())
        self.assertEqual(empty.journal_admission()["request_id"], empty.request_id)
        inline_request = request(references=[{
            "id": "note", "required": True,
            "source": {"kind": "inline", "text": "bounded context"},
        }])
        admitted = self.admit(origin(inline_request))
        self.assertEqual(admitted.reference_ids, ("note",))
        self.assertEqual(admitted.repository_id, REPOSITORY_ID)
        self.assertEqual(admitted.head_sha, HEAD)
        self.assertTrue(admitted.admission_evidence_id.startswith("artifact:sha256:"))

    def test_wrong_repository_id_and_changed_head_fail_closed(self) -> None:
        for authority, marker in (
            (PrAuthority(repository_id=1), "PULL_REQUEST_IDENTITY_MISMATCH"),
            (PrAuthority(head="f" * 40), "PULL_REQUEST_IDENTITY_MISMATCH"),
        ):
            with self.subTest(marker=marker):
                with self.assertRaisesRegex(AdmissionV3CandidateError, marker):
                    self.admit(pr=authority)

    def test_login_is_metadata_not_authority_and_numeric_requester_is_mandatory(self) -> None:
        admitted = self.admit(origin(login="spoofed-login"))
        self.assertEqual(admitted.requester_login_observed, "spoofed-login")
        with self.assertRaisesRegex(AdmissionV3CandidateError, "REQUESTER_ID_MISMATCH"):
            self.admit(origin(requester_id=1))
        with self.assertRaisesRegex(AdmissionV3CandidateError, "AUTHORIZATION_UNTRUSTED"):
            self.admit(requester=RequesterAuthority(False))

    def test_untrusted_issue_and_source_repository_fail_closed(self) -> None:
        with self.assertRaisesRegex(AdmissionV3CandidateError, "ISSUE_ID_MISMATCH"):
            self.admit(origin(issue_id=1))
        with self.assertRaisesRegex(AdmissionV3CandidateError, "SOURCE_REPOSITORY_UNAUTHORIZED"):
            self.admit(source=SourceAuthority(False))

    def test_initial_history_must_be_complete_and_conflict_free(self) -> None:
        with self.assertRaisesRegex(AdmissionV3CandidateError, "INITIAL_HISTORY_UNTRUSTED"):
            self.admit(history=HistoryAuthority(complete=False))
        with self.assertRaisesRegex(AdmissionV3CandidateError, "INTENT_ALREADY_EXISTS"):
            self.admit(history=HistoryAuthority(matching=("request:sha256:" + "f" * 64,)))

    def test_changed_head_and_repeat_same_head_are_structural_but_not_admitted(self) -> None:
        previous = "request:sha256:" + "f" * 64
        for operation, marker in (
            ({"kind": "changed_head", "previous_request_id": previous}, "CHANGED_HEAD"),
            ({"kind": "repeat_same_head", "previous_request_id": previous,
              "authorization_nonce": "1" * 32}, "REPEAT_SAME_HEAD"),
        ):
            value = request(review_operation=operation)
            with self.subTest(kind=operation["kind"]):
                with self.assertRaisesRegex(AdmissionV3CandidateError, marker):
                    self.admit(origin(value))

    def test_all_remote_selector_kinds_remain_not_yet_qualified(self) -> None:
        sources = [
            {"kind": "git_file", "repository": REPOSITORY,
             "path": "docs/a.md", "commit": "b" * 40},
            {"kind": "github_issue_body", "repository": REPOSITORY, "issue": 51},
            {"kind": "github_issue_comment", "repository": REPOSITORY, "comment_id": 99},
        ]
        for source in sources:
            value = request(references=[{"id": "remote", "required": False, "source": source}])
            with self.subTest(kind=source["kind"]):
                with self.assertRaisesRegex(
                    AdmissionV3CandidateError, "REMOTE_SOURCE_ADMISSION_NOT_YET_QUALIFIED"
                ):
                    self.admit(origin(value))

    def test_resolved_subject_must_fit_eventual_source_and_rendered_bounds(self) -> None:
        inline = request(references=[{
            "id": "note", "required": False,
            "source": {"kind": "inline", "text": "x"},
        }])
        with self.assertRaisesRegex(AdmissionV3CandidateError, "SOURCE_COUNT_EXCEEDED"):
            self.admit(origin(inline), pr=PrAuthority(source_count=999))
        with self.assertRaisesRegex(AdmissionV3CandidateError, "RENDERED_PACKET_EXCEEDED"):
            self.admit(pr=PrAuthority(rendered_bytes=8_000_001))
        with self.assertRaisesRegex(AdmissionV3CandidateError, "SUBJECT_SOURCE_BYTES_EXCEEDED"):
            self.admit(pr=PrAuthority(original_bytes=2_000_001))

    def test_subject_source_ids_are_bounded_strings_and_unique(self) -> None:
        for sources in (
            (SubjectSourceFeasibilityV3(True, 1, 1),),
            (SubjectSourceFeasibilityV3("", 1, 1),),
            (SubjectSourceFeasibilityV3("S٠٠١", 1, 1),),
            (SubjectSourceFeasibilityV3("S001", 1, 1),
             SubjectSourceFeasibilityV3("S001", 1, 1)),
        ):
            authority = PrAuthority()
            authority.sources = sources
            with self.subTest(sources=sources):
                with self.assertRaisesRegex(AdmissionV3CandidateError, "IDENTITY_MISMATCH"):
                    self.admit(pr=authority)

    def test_atomicity_true_rejects_mutable_github_reference_first(self) -> None:
        value = request(atomicity=True, references=[{
            "id": "remote", "required": False,
            "source": {"kind": "github_issue_body", "repository": REPOSITORY, "issue": 51},
        }])
        with self.assertRaisesRegex(AdmissionV3CandidateError, "ATOMICITY_MUTABLE_REFERENCE"):
            self.admit(origin(value))

    def test_authenticated_body_is_the_only_request_source(self) -> None:
        observed = origin()
        changed = request(atomicity=True)
        # Caller-side data is irrelevant; admission parses only the retained authenticated body.
        admitted = self.admit(observed)
        self.assertFalse(admitted.request["atomicity"])
        self.assertNotEqual(build_issue_envelope_v3(changed), observed.observe(51).body)

    def test_duplicate_same_request_history_is_reusable_but_distinct_intent_match_is_not(self) -> None:
        first = self.admit()
        duplicate = self.admit(history=HistoryAuthority(matching=(first.request_id,)))
        self.assertEqual(duplicate.request_id, first.request_id)

    def test_admission_request_and_journal_mapping_are_defensive_and_provenance_complete(self) -> None:
        admitted = self.admit()
        first = admitted.request
        first["subject"]["repository_id"] = 1
        self.assertEqual(admitted.request["subject"]["repository_id"], REPOSITORY_ID)
        journal = admitted.journal_admission()
        expected = {
            "request_id", "admission_evidence_id", "review_intent_id",
            "canonical_request", "broker_issue_id", "requester_id",
            "origin_evidence_id", "requester_authorization_evidence_id",
            "history_evidence_id", "history_scan_boundary", "repository_id",
            "resolved_subject", "source_admission_id", "origin_observation",
            "source_observation", "requester_authorization",
            "history_observation", "reference_ids",
        }
        self.assertEqual(set(journal), expected)
        self.assertEqual(
            validate_journal_admission_v3(journal, admitted.origin_body_bytes), journal
        )
        journal["canonical_request"]["subject"]["repository_id"] = 1
        with self.assertRaisesRegex(AdmissionV3CandidateError, "IDENTITY_MISMATCH"):
            validate_journal_admission_v3(journal, admitted.origin_body_bytes)

    def test_forged_origin_reader_shape_is_not_a_trusted_adapter(self) -> None:
        class ForgedReader:
            def observe(self, number):
                return origin().observe(number)
        with self.assertRaisesRegex(AdmissionV3CandidateError, "TRUSTED_ORIGIN_READER_REQUIRED"):
            self.admit(ForgedReader())


if __name__ == "__main__":
    unittest.main()
