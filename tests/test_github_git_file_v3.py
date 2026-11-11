import base64
from dataclasses import replace
from unittest.mock import patch
from datetime import datetime, timezone
import hashlib
import json
import unittest

from review_broker.github_git_file_v3 import GitHubGitFileReaderV3, GitHubGitFileV3Error
from review_broker.identity import artifact_identity, canonical_bytes
from review_broker.github_http_live_v3 import HttpResponseV3
from tests.issue69_test_support import source_authority

REPO = "fanilosendrison/review-broker"; REPO_ID = 1433701208
COMMIT = "a" * 40; TREE = "b" * 40; DATA = b"alpha\r\nbeta\n"
def blob_oid(data=DATA):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


class Api:
    def __init__(self, *, data=DATA, repo_id=REPO_ID, status=None, truncated=False,
                 mode="100644", duplicate=False, commit=COMMIT, encoding="base64"):
        self.data, self.repo_id, self.status = data, repo_id, status
        self.truncated, self.mode, self.duplicate = truncated, mode, duplicate
        self.commit, self.encoding, self.calls = commit, encoding, []
    def __call__(self, request):
        self.calls.append((request.method, request.full_url))
        suffix = ("/installation" if request.full_url.endswith("/installation")
                  else request.full_url.split("/review-broker", 1)[1])
        if self.status and suffix != "": return HttpResponseV3(self.status, b"{}", {})
        if request.full_url.endswith("/installation"): value = {"id": 123}
        elif suffix == "": value = {"id": self.repo_id, "full_name": REPO}
        elif suffix == f"/git/commits/{COMMIT}": value = {"sha": self.commit, "tree": {"sha": TREE}}
        elif suffix == f"/git/trees/{TREE}":
            entry = {"path": "contract.md", "mode": self.mode,
                     "type": "blob" if self.mode not in {"040000", "160000"} else "commit",
                     "sha": blob_oid(self.data)}
            value = {"sha": TREE, "truncated": self.truncated,
                     "tree": [entry, dict(entry)] if self.duplicate else [entry]}
        elif suffix == f"/git/blobs/{blob_oid(self.data)}":
            content = base64.b64encode(self.data).decode() if self.encoding == "base64" else "%%%"
            value = {"sha": blob_oid(self.data), "encoding": self.encoding,
                     "size": len(self.data), "content": content}
        else: raise AssertionError(suffix)
        return HttpResponseV3(200, json.dumps(value).encode(), {})


def reader(api, source=None):
    source = source_authority() if source is None else source
    authorization = source.authorize(REPO, REPO_ID)
    return GitHubGitFileReaderV3("token", REPO, REPO_ID, authority_evidence_id=authorization.evidence_id,
        source_authority=source, executor=api,
        clock=lambda: datetime(2026, 11, 1, tzinfo=timezone.utc))


class GitHubGitFileReaderTests(unittest.TestCase):
    def test_exact_authenticated_commit_tree_blob_and_bytes(self):
        api = Api(); value = reader(api).observe(COMMIT, "contract.md", hashlib.sha256(DATA).hexdigest())
        self.assertEqual(value.original_bytes, DATA)
        self.assertEqual(value.git_blob_oid, blob_oid())
        self.assertEqual(value.root_tree_sha, TREE)
        self.assertEqual(value.qualification, "AUTHENTICATED_READ_ONLY")
        self.assertTrue(value.evidence_id.startswith("artifact:sha256:"))
        self.assertTrue(all(method == "GET" for method, _ in api.calls))

    def test_identity_digest_authority_and_object_failures(self):
        cases = [
            (Api(repo_id=9), "REPOSITORY_IDENTITY_MISMATCH"),
            (Api(commit="c" * 40), "COMMIT_IDENTITY_MISMATCH"),
            (Api(truncated=True), "TREE_INCOMPLETE"),
            (Api(duplicate=True), "MISSING_OR_DUPLICATED"),
            (Api(mode="120000"), "FINAL_OBJECT_UNSUPPORTED"),
            (Api(mode="160000"), "FINAL_OBJECT_UNSUPPORTED"),
            (Api(encoding="bad"), "BLOB_IDENTITY_MISMATCH"),
            (Api(status=403), "AUTHORITY_AMBIGUOUS"),
            (Api(status=404), "AUTHORITY_AMBIGUOUS"),
        ]
        for api, marker in cases:
            with self.subTest(marker=marker), self.assertRaisesRegex(GitHubGitFileV3Error, marker):
                reader(api).observe(COMMIT, "contract.md")
        with self.assertRaisesRegex(GitHubGitFileV3Error, "EXPECTED_SHA256_MISMATCH"):
            reader(Api()).observe(COMMIT, "contract.md", "0" * 64)
        with self.assertRaisesRegex(GitHubGitFileV3Error, "SOURCE_CREDENTIAL_IN_CONTENT"):
            reader(Api(data=b"token")).observe(COMMIT, "contract.md")

    def test_invalid_commit_path_base64_utf8_and_size_fail(self):
        for commit, path, api, marker in (
            ("bad", "contract.md", Api(), "COMMIT_INVALID"),
            (COMMIT, "../secret", Api(), "PATH_INVALID"),
            (COMMIT, "contract.md", Api(encoding="base64"), ""),
            (COMMIT, "contract.md", Api(data=b"\xff"), "TEXT_ENCODING_INVALID"),
            (COMMIT, "contract.md", Api(data=b"x" * 2_000_001), "SOURCE_SIZE_INVALID"),
        ):
            if not marker: continue
            with self.subTest(marker=marker), self.assertRaisesRegex(GitHubGitFileV3Error, marker):
                reader(api).observe(commit, path)


class GitFileAuthorizationBindingTests(unittest.TestCase):
    marker = "GIT_FILE_SOURCE_AUTHORIZATION_EVIDENCE_MISMATCH"

    def test_substituted_authorization_rejected_before_first_get(self):
        source = source_authority()
        positive = reader(Api(), source).observe(COMMIT, "contract.md")
        self.assertEqual(positive.authority_evidence_id, source.authorize(REPO, REPO_ID).evidence_id)
        self.assertEqual(positive.qualification, "AUTHENTICATED_READ_ONLY")
        for substituted in ("artifact:sha256:" + "0" * 64, source.scope_observation.evidence_id):
            with self.subTest(substituted=substituted):
                api = Api(); value = reader(api, source)
                value.authority_evidence_id = substituted
                with self.assertRaisesRegex(GitHubGitFileV3Error, self.marker):
                    value.observe(COMMIT, "contract.md")
                self.assertEqual(api.calls, [])
        api = Api()
        value = GitHubGitFileReaderV3("token", REPO, REPO_ID,
            authority_evidence_id="artifact:sha256:" + "0" * 64,
            source_authority=source, executor=api)
        with self.assertRaisesRegex(GitHubGitFileV3Error, self.marker):
            value.observe(COMMIT, "contract.md")
        self.assertEqual(api.calls, [])

    def test_invalid_current_authorization_rejected_before_get(self):
        source = source_authority(); authorization = source.authorize(REPO, REPO_ID)
        cases = [None, {}, replace(authorization, repository="other/repository"),
                 replace(authorization, repository_id=REPO_ID + 1),
                 replace(authorization, installation_id=124),
                 replace(authorization, evidence_id="artifact:sha256:" + "f" * 64)]
        for current in cases:
            with self.subTest(current=current):
                api = Api(); value = reader(api, source)
                with patch.object(source, "authorize", return_value=current):
                    with self.assertRaisesRegex(GitHubGitFileV3Error, self.marker):
                        value.observe(COMMIT, "contract.md")
                self.assertEqual(api.calls, [])

    def test_wrong_token_repository_installation_and_unobserved_scope(self):
        for mutation, marker in (("token", "GIT_FILE_SOURCE_AUTHORITY_MISMATCH"),
                                 ("repository", "GIT_FILE_SOURCE_AUTHORITY_MISMATCH"),
                                 ("scope", "GIT_FILE_SOURCE_AUTHORITY_MISMATCH"),
                                 ("installation", self.marker), ("evidence", self.marker)):
            with self.subTest(mutation=mutation):
                source = source_authority(); api = Api(); value = reader(api, source)
                if mutation == "token": value._token = "different-token"
                if mutation == "repository": value.repository_id += 1
                if mutation == "scope": source._scope = None
                if mutation == "installation": source.installation_id += 1
                if mutation == "evidence": source.app_slug = "changed-source-app"
                with self.assertRaisesRegex(GitHubGitFileV3Error, marker):
                    value.observe(COMMIT, "contract.md")
                self.assertEqual(api.calls, [])

    def test_authority_rechecked_after_acquisition_before_emission(self):
        source = source_authority(); api = Api(); value = reader(api, source)
        def clock():
            source.app_slug = "changed-during-acquisition"
            return datetime(2026, 11, 1, tzinfo=timezone.utc)
        value._clock = clock
        with self.assertRaisesRegex(GitHubGitFileV3Error, self.marker):
            value.observe(COMMIT, "contract.md")
        self.assertEqual(len(api.calls), 5)

    def test_historical_qualification_mode_is_not_promoted(self):
        api = Api()
        value = GitHubGitFileReaderV3("token", REPO, REPO_ID,
            authority_evidence_id="artifact:sha256:" + "0" * 64,
            qualification_only=True, expected_installation_id=123, executor=api)
        observation = value.observe(COMMIT, "contract.md")
        self.assertEqual(observation.qualification, "SAME_REPOSITORY_ACTIONS_QUALIFICATION")
        self.assertEqual(observation.authority_evidence_id, "artifact:sha256:" + "0" * 64)


class SwapOnSecondComparison(str):
    def arm(self, reader):
        self.reader = reader
        self.comparisons = 0

    def __ne__(self, other):
        self.comparisons += 1
        if self.comparisons == 2:
            self.reader.authority_evidence_id = self.encode("ascii").decode("ascii")
        return False


class PlainString(str):
    pass


class TrapString(str):
    def forbidden(self, *args, **kwargs):
        raise AssertionError("SUBCLASS_METHOD_MUST_NOT_EXECUTE")
    __eq__ = __ne__ = __str__ = __len__ = startswith = encode = forbidden


class GitFileStringSubclassTests(unittest.TestCase):
    marker = "GIT_FILE_SOURCE_AUTHORIZATION_EVIDENCE_MISMATCH"

    def test_constructor_rejects_all_subclasses_without_methods(self):
        source = source_authority(); actual = source.authorize(REPO, REPO_ID).evidence_id
        for kind in (PlainString, TrapString):
            for qualification in (False, True):
                with self.subTest(kind=kind.__name__, qualification=qualification):
                    api = Api()
                    with self.assertRaisesRegex(ValueError, "GITHUB_SOURCE_AUTHORITY_INVALID"):
                        GitHubGitFileReaderV3("token", REPO, REPO_ID,
                            authority_evidence_id=kind(actual), source_authority=source,
                            qualification_only=qualification, executor=api)
                    self.assertEqual(api.calls, [])

    def test_post_construction_subclass_rejected_without_get_or_methods(self):
        for kind in (PlainString, TrapString, SwapOnSecondComparison):
            with self.subTest(kind=kind.__name__):
                source = source_authority(); api = Api(); value = reader(api, source)
                value.authority_evidence_id = kind(value.authority_evidence_id)
                with self.assertRaisesRegex(GitHubGitFileV3Error, self.marker):
                    value.observe(COMMIT, "contract.md")
                self.assertEqual(api.calls, [])

    def test_actual_authorization_subclass_rejected_before_get(self):
        for kind in (PlainString, TrapString, SwapOnSecondComparison):
            with self.subTest(kind=kind.__name__):
                source = source_authority(); api = Api(); value = reader(api, source)
                actual = source.authorize(REPO, REPO_ID)
                with patch.object(source, "authorize", return_value=replace(
                        actual, evidence_id=kind(actual.evidence_id))):
                    with self.assertRaisesRegex(GitHubGitFileV3Error, self.marker):
                        value.observe(COMMIT, "contract.md")
                self.assertEqual(api.calls, [])

    def test_field_mutation_during_acquisition_rejected(self):
        for kind in (str, PlainString, TrapString):
            with self.subTest(kind=kind.__name__):
                source = source_authority(); api = Api(); value = reader(api, source)
                def clock():
                    value.authority_evidence_id = kind("artifact:sha256:" + "0" * 64)
                    return datetime(2026, 11, 1, tzinfo=timezone.utc)
                value._clock = clock
                with self.assertRaisesRegex(GitHubGitFileV3Error, self.marker):
                    value.observe(COMMIT, "contract.md")
                self.assertEqual(len(api.calls), 5)

    def test_actual_authorization_subclass_at_final_check_rejected(self):
        source = source_authority(); api = Api(); value = reader(api, source)
        actual = source.authorize(REPO, REPO_ID)
        with patch.object(source, "authorize", side_effect=[actual,
                replace(actual, evidence_id=TrapString(actual.evidence_id))]):
            with self.assertRaisesRegex(GitHubGitFileV3Error, self.marker):
                value.observe(COMMIT, "contract.md")
        self.assertEqual(len(api.calls), 5)

    def test_emission_uses_verified_local_id_not_mutated_field(self):
        source = source_authority(); value = reader(Api(), source)
        actual = source.authorize(REPO, REPO_ID).evidence_id
        original = value._verify_credential_authority
        calls = []
        def verify_then_mutate():
            verified = original(); calls.append(verified)
            if len(calls) == 2:
                value.authority_evidence_id = "artifact:sha256:" + "0" * 64
            return verified
        value._verify_credential_authority = verify_then_mutate
        observed = value.observe(COMMIT, "contract.md")
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(value.authority_evidence_id, actual)
        self.assertIs(type(observed.authority_evidence_id), str)
        self.assertEqual(observed.authority_evidence_id, actual)
        basis = observed.provenance_basis()
        self.assertEqual(basis["authority_evidence_id"], actual)
        encoded = canonical_bytes(basis) + b"\n"
        self.assertEqual(observed.evidence_id, artifact_identity(encoded))
        self.assertNotIn(b"token", encoded)

    def test_canonical_native_id_and_historical_emission(self):
        source = source_authority(); actual = source.authorize(REPO, REPO_ID).evidence_id
        for qualification in (False, True):
            value = GitHubGitFileReaderV3("token", REPO, REPO_ID,
                authority_evidence_id=actual, source_authority=source,
                qualification_only=qualification, executor=Api())
            observed = value.observe(COMMIT, "contract.md")
            self.assertIs(type(observed.authority_evidence_id), str)
            self.assertEqual(observed.authority_evidence_id, actual)
            self.assertEqual(observed.qualification, "SAME_REPOSITORY_ACTIONS_QUALIFICATION"
                             if qualification else "AUTHENTICATED_READ_ONLY")
        for invalid in ("artifact:sha256:" + "g" * 64, "artifact:sha256:0"):
            with self.assertRaisesRegex(ValueError, "GITHUB_SOURCE_AUTHORITY_INVALID"):
                GitHubGitFileReaderV3("token", REPO, REPO_ID,
                    authority_evidence_id=invalid, source_authority=source, executor=Api())

    def test_exact_reviewer_witness_rejected(self):
        source = source_authority(); api = Api()
        actual = source.authorize(REPO, REPO_ID).evidence_id
        bad_text = "artifact:sha256:" + "0" * 64
        self.assertNotEqual(actual, bad_text)
        supplied = SwapOnSecondComparison(bad_text)
        with self.assertRaisesRegex(ValueError, "GITHUB_SOURCE_AUTHORITY_INVALID"):
            value = GitHubGitFileReaderV3("token", REPO, REPO_ID,
                authority_evidence_id=supplied, source_authority=source, executor=api)
            supplied.arm(value)
            observed = value.observe(COMMIT, "contract.md")
            # On the old code, establish that the exact witness emits a forged
            # built-in string before the expected-rejection assertion goes RED.
            self.assertEqual(observed.qualification, "AUTHENTICATED_READ_ONLY")
            self.assertIs(type(observed.authority_evidence_id), str)
            self.assertEqual(observed.authority_evidence_id, bad_text)
            self.assertNotEqual(observed.authority_evidence_id, actual)
        self.assertEqual(api.calls, [])


if __name__ == "__main__": unittest.main()
