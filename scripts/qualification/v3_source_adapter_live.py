"""Owner-gated qualification controller for one immutable experimental checkout."""
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

CANDIDATE_SHA = "e65e4db932cb59d7a0fcfbd442ba19e548fc141d"
CANDIDATE_TREE = "420a18d006e421e197d23b8e93681376fbabc2db"
REPOSITORY = "fanilosendrison/review-broker"
REPOSITORY_ID = 1433701208
HEAD = "9258617056e9d2e20cce7f05e6be71ea82dfbd23"
BASE = "83b02c1b9b5bad6c6f64af76affb140957fcbd38"
PR_ID = 5101281733
FILE_COUNT = 9
FILE_PATH = "AGENTS.md"
FILE_OID = "72ccb739729759ed4a3cd9fa812483ea81976bee"
FILE_DIGEST = "22b7d2e4ac5556d3c355c2cc35d1fdc457c1363a37c922f71a0755180e03beea"
PERMISSIONS = frozenset({"contents:read", "pull_requests:read", "metadata:read", "issues:read"})
MODULES = ("github_source_authority_v3", "github_pull_request_observation_v3",
           "github_subject_capture_v3", "github_git_file_v3", "github_issue_reference_v3")
CREDENTIAL = re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}")


class QualificationError(RuntimeError):
    """Only controller-owned fixed markers may cross the output boundary."""


def require(value, marker):
    if not value:
        raise QualificationError(marker)


def git(root, *arguments):
    environment = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
    environment.update({"GIT_NO_REPLACE_OBJECTS": "1", "GIT_CONFIG_NOSYSTEM": "1",
                        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_NO_LAZY_FETCH": "1",
                        "GIT_TERMINAL_PROMPT": "0"})
    result = subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", str(root), *arguments],
                            capture_output=True, timeout=60, env=environment)
    require(result.returncode == 0, "CANDIDATE_GIT_FAILED")
    return result.stdout


def verify_candidate(root):
    root = Path(root)
    require(not root.is_symlink() and root.is_dir(), "CANDIDATE_PATH")
    require(git(root, "rev-parse", "HEAD").strip().decode() == CANDIDATE_SHA,
            "CANDIDATE_SHA")
    require(git(root, "rev-parse", "HEAD^{tree}").strip().decode() == CANDIDATE_TREE,
            "CANDIDATE_TREE")
    require(git(root, "rev-parse", "--abbrev-ref", "HEAD").strip() == b"HEAD",
            "CANDIDATE_MUTABLE_REF")
    require(not git(root, "status", "--porcelain", "--untracked-files=all", "--ignored=matching"),
            "CANDIDATE_DIRTY")
    # Hash every tracked file, not only stat-cache entries or named entry points.
    for entry in git(root, "ls-tree", "-rz", "HEAD").split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, kind, oid = metadata.split()
        path = root / os.fsdecode(name)
        require(kind == b"blob", "CANDIDATE_NONREGULAR_FILE")
        if mode == b"120000":
            require(path.is_symlink() and path.resolve().is_relative_to(root.resolve())
                    and path.is_file(), "CANDIDATE_SYMLINK")
            data = os.fsencode(os.readlink(path))
        else:
            require(mode in (b"100644", b"100755") and not path.is_symlink()
                    and path.is_file(), "CANDIDATE_NONREGULAR_FILE")
            data = path.read_bytes()
        require(hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
                == oid.decode(), "CANDIDATE_FILE_CHANGED")
    for name in MODULES:
        require((root / "src/review_broker" / (name + ".py")).is_file(), "CANDIDATE_MODULE")
    for name in ("packet-v2.candidate.schema.json", "review-request-v3.candidate.schema.json"):
        require((root / "src/review_broker/schemas" / name).is_file(), "CANDIDATE_SCHEMA")
    return root.resolve()


def load_candidate(root):
    root = verify_candidate(root)
    require(not any(n == "review_broker" or n.startswith("review_broker.")
                    for n in sys.modules), "PACKAGE_ALREADY_IMPORTED")
    sys.dont_write_bytecode = True
    source = root / "src"
    sys.path.insert(0, str(source))
    for package, version in (("jsonschema", "4.26.0"), ("rfc8785", "0.1.4")):
        require(importlib.metadata.version(package) == version, "DEPENDENCY_VERSION")
    modules = {name: importlib.import_module("review_broker." + name) for name in MODULES}
    for name, module in tuple(sys.modules.items()):
        if name == "review_broker" or name.startswith("review_broker."):
            path = Path(module.__file__).resolve()
            require(path.is_relative_to(source), "CANDIDATE_IMPORT_ORIGIN")
    return modules


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_bytes(data, token):
    require(token.encode() not in data and not CREDENTIAL.search(data), "CREDENTIAL_CONTAMINATION")


def verify_capture(scope, capture, authorization, packet):
    """Check the orchestration result against local Git, without source execution."""
    require((capture.repository, capture.repository_id, capture.pull_request,
             capture.pull_request_id, capture.head_sha, capture.base_sha,
             capture.merge_base_sha, capture.changes) ==
            (scope.repository, scope.repository_id, scope.pull_request,
             scope.pull_request_id, scope.head_sha, scope.base_sha,
             scope.merge_base_sha, scope.changes), "CAPTURE_SCOPE")
    require(capture.source_authorization_evidence_id == authorization.evidence_id and
            capture.pr_observation_evidence_id == scope.evidence_id and
            packet.subject_capture_evidence_id_v2(capture) == capture.evidence_id,
            "CAPTURE_PROVENANCE")
    root = capture.repository_root
    require(git(root, "merge-base", scope.base_sha, scope.head_sha).strip().decode()
            == scope.merge_base_sha, "CAPTURE_MERGE_BASE")
    expected = []
    for change in scope.changes:
        if change["status"] != "added":
            expected.append((scope.merge_base_sha, change["previous_path"] or change["path"]))
        if change["status"] != "removed":
            expected.append((scope.head_sha, change["path"]))
    require([(r.commit, r.path) for r in capture.records] == expected, "CAPTURE_IMAGES")
    for record in capture.records:
        require(record.repository == scope.repository, "CAPTURE_REPOSITORY")
        object_name = record.commit + ":" + record.path
        data = record.original_bytes
        oid = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        require(oid == record.git_blob_oid and
                git(root, "rev-parse", object_name).strip().decode() == record.git_blob_oid
                and git(root, "cat-file", "blob", record.git_blob_oid) == data,
                "CAPTURE_BLOB")
    require(git(root, "diff", "--binary", "--full-index", "--no-ext-diff", "--no-textconv",
                "--find-renames", "--find-copies-harder", scope.merge_base_sha,
                scope.head_sha, "--") == capture.diff, "CAPTURE_DIFF")


def qualify(environment, modules, executor=None, *, acquire_repository=None):
    """Run actual adapters; optional acquisition/HTTP seams support offline tests."""
    token = environment.get("REVIEW_BROKER_SOURCE_TOKEN", "")
    require(bool(token), "SOURCE_TOKEN_REQUIRED")
    require(environment.get("SOURCE_APP_SLUG") == "review-broker-app" and
            environment.get("SOURCE_INSTALLATION_ID") == "176619170", "MINT_IDENTITY")
    require(re.fullmatch(r"[0-9a-f]{40}", environment.get("GITHUB_SHA", "")), "EXECUTION_SHA")
    require(environment.get("GITHUB_JOB") == "qualify", "EXECUTION_JOB")
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        require(re.fullmatch(r"[1-9][0-9]{0,19}", environment.get(key, "")), "EXECUTION_RUN")
    for key in ("GITHUB_TOKEN", "GH_TOKEN", "REVIEW_BROKER_JOURNAL_TOKEN",
                "REVIEW_BROKER_PUBLISH_TOKEN", "REVIEW_BROKER_CODESPACES_TOKEN",
                "REVIEW_BROKER_SOURCE_APP_PRIVATE_KEY"):
        require(not environment.get(key), "UNRELATED_CREDENTIAL")
    authority = modules[MODULES[0]].GitHubSourceAuthorityV3(
        token, expected_app_slug=environment["SOURCE_APP_SLUG"],
        expected_installation_id=176619170, repository=REPOSITORY,
        repository_id=REPOSITORY_ID, approved_permissions=PERMISSIONS,
        authorized_repositories=frozenset({REPOSITORY}), executor=executor)
    scope_authority = authority.observe_scope()
    require(scope_authority.observed_repository_count == 1, "SOURCE_SCOPE")
    authorization = authority.authorize(REPOSITORY, REPOSITORY_ID)
    require(authorization is not None, "SOURCE_AUTHORIZATION")
    reader = modules[MODULES[1]].GitHubPullRequestObservationReaderV3(
        token, REPOSITORY, REPOSITORY_ID, 71, HEAD, source_authority=authority, executor=executor)
    scope = reader.observe_scope()
    require((scope.pull_request_id, scope.head_sha, scope.base_sha, scope.changed_files) ==
            (PR_ID, HEAD, BASE, FILE_COUNT), "PR_PINNED_IDENTITY")
    capture_module = modules[MODULES[2]]
    # Live calls use the default gh acquisition; offline tests inject local Git.
    with tempfile.TemporaryDirectory(prefix="rb-v3-adapter-private-") as temporary:
        capture = capture_module.capture_authenticated_subject_v3(
            scope, reader, authorization, scope_authority.evidence_id, token, Path(temporary),
            acquire_repository=acquire_repository)
        packet = importlib.import_module("review_broker.packet_v2")
        verify_capture(scope, capture, authorization, packet)
        require(capture.verification == "AUTHENTICATED_SOURCE_READ_ONLY", "CAPTURE_PROVENANCE")
        final = reader.finalize(scope, capture)
        bound = capture_module.bind_authenticated_capture_v3(
            capture, authorization.evidence_id, final.evidence_id)
        require(bound.verification == "AUTHENTICATED_SOURCE_READ_ONLY" and
                bound.source_authorization_evidence_id == authorization.evidence_id and
                bound.pr_observation_evidence_id == final.evidence_id, "BOUND_PROVENANCE")
        require(packet.subject_capture_evidence_id_v2(bound) == bound.evidence_id,
                "BOUND_CAPTURE_IDENTITY")
        records = []
        total = 0
        for record in capture.records:
            safe_bytes(record.original_bytes, token)
            total += len(record.original_bytes)
            records.append({"commit": record.commit, "path": record.path,
                            "git_blob_oid": record.git_blob_oid,
                            "original_sha256": digest(record.original_bytes),
                            "original_size": len(record.original_bytes)})
        safe_bytes(capture.diff, token)
        git_file = modules[MODULES[3]].GitHubGitFileReaderV3(
            token, REPOSITORY, REPOSITORY_ID, authority_evidence_id=authorization.evidence_id,
            source_authority=authority, qualification_only=False, executor=executor)
        reference = git_file.observe(HEAD, FILE_PATH, FILE_DIGEST)
        require(reference.commit_sha == HEAD and reference.path == FILE_PATH and
                reference.git_blob_oid == FILE_OID and reference.sha256 == FILE_DIGEST and
                reference.authority_evidence_id == authorization.evidence_id and
                reference.qualification == "AUTHENTICATED_READ_ONLY", "GIT_REFERENCE")
        issues = modules[MODULES[4]].GitHubIssueReferenceReaderV3(
            token, REPOSITORY, REPOSITORY_ID, authority_evidence_id=authorization.evidence_id,
            source_authority=authority, qualification_only=False, executor=executor)
        issue = issues.observe_issue_body(43)
        comment = issues.observe_issue_comment(6535094733)
        require(issue.issue_id == 6101161202 and issue.issue_number == 43 and
                comment.comment_id == 6535094733 and comment.issue_number == 51 and
                comment.author_id == 30498238 and comment.issue_id == 6106789428,
                "ISSUE_REFERENCE_IDENTITY")
        for observation in (reference, issue, comment):
            safe_bytes(observation.original_bytes, token)
            require(observation.repository == REPOSITORY and
                    observation.original_byte_length == len(observation.original_bytes) and
                    observation.sha256 == digest(observation.original_bytes) and
                    type(observation.evidence_id) is str and
                    observation.evidence_id == packet.artifact_identity(
                        packet.canonical_bytes(observation.provenance_basis()) + b"\n"),
                    "REFERENCE_EVIDENCE")
            require(observation.installation_id == 176619170 and
                    observation.repository_id == REPOSITORY_ID and
                    observation.authority_evidence_id == authorization.evidence_id and
                    observation.qualification == "AUTHENTICATED_READ_ONLY",
                    "REFERENCE_AUTHORITY")
        receipt = {
            "schema_version": "1.0.0", "executing_source_sha": environment["GITHUB_SHA"],
            "candidate_sha": CANDIDATE_SHA, "candidate_tree": CANDIDATE_TREE,
            "run_id": int(environment["GITHUB_RUN_ID"]),
            "run_attempt": int(environment["GITHUB_RUN_ATTEMPT"]), "job": "qualify",
            "app_slug": environment["SOURCE_APP_SLUG"], "installation_id": 176619170,
            "repository": REPOSITORY, "repository_id": REPOSITORY_ID,
            "requested_permissions": sorted(PERMISSIONS), "installation_repository_count": 1,
            "source_authorization_evidence_id": authorization.evidence_id,
            "source_scope_evidence_id": scope_authority.evidence_id,
            "pr_number": 71, "pr_id": PR_ID, "head_sha": HEAD, "base_sha": scope.base_sha,
            "merge_base_sha": capture.merge_base_sha, "changed_file_count": len(scope.changes),
            "change_inventory_sha256": digest(packet.canonical_bytes(list(scope.changes))),
            "preimage_count": sum(x["status"] != "added" for x in scope.changes),
            "postimage_count": sum(x["status"] != "removed" for x in scope.changes),
            "images": records, "binary_diff_sha256": digest(capture.diff),
            "total_source_bytes": total, "capture_evidence_id": capture.evidence_id,
            "final_pr_evidence_id": final.evidence_id, "bound_capture_evidence_id": bound.evidence_id,
            "git_file_evidence_id": reference.evidence_id,
            "git_file_blob_oid": reference.git_blob_oid, "git_file_sha256": reference.sha256,
            "issue_evidence_id": issue.evidence_id, "issue_sha256": issue.sha256,
            "issue_id": issue.issue_id, "issue_number": issue.issue_number,
            "comment_evidence_id": comment.evidence_id, "comment_sha256": comment.sha256,
            "comment_id": comment.comment_id, "comment_issue_id": comment.issue_id,
            "comment_issue_number": comment.issue_number, "comment_author_id": comment.author_id,
            "boundaries": {key: "PASS" for key in ("source_authority", "pr_scope", "capture",
                "final_pr", "authenticated_provenance", "git_file", "issue", "comment")},
            "requester_authority": "NOT_QUALIFIED", "packet_readiness": "NOT_QUALIFIED",
            "github_mutations": 0, "codespace_effects": 0, "model_invocations": 0,
        }
        data = packet.canonical_bytes(receipt)
        require(len(data) < 1_000_000, "RECEIPT_SIZE")
        safe_bytes(data, token)
        receipt["receipt_sha256"] = digest(data)
        return receipt


def main():
    try:
        root = Path(__file__).resolve().parents[2]
        if sys.argv[1:] in (["--verify-code"], ["--preflight"]):
            require(not any(os.environ.get(k) for k in ("REVIEW_BROKER_SOURCE_TOKEN",
                    "REVIEW_BROKER_SOURCE_APP_PRIVATE_KEY", "GITHUB_TOKEN", "GH_TOKEN")),
                    "PREFLIGHT_CREDENTIAL")
        if sys.argv[1:] == ["--verify-code"]:
            verify_candidate(root / "candidate-v3")
            print("CANDIDATE_CODE_IDENTITY_PASS")
            return 0
        modules = load_candidate(root / "candidate-v3")
        if sys.argv[1:] == ["--preflight"]:
            print("CANDIDATE_CREDENTIAL_FREE_PREFLIGHT_PASS")
            return 0
        require(not sys.argv[1:], "UNSUPPORTED_ARGUMENT")
        receipt = qualify(dict(os.environ), modules)
        print(json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
        return 0
    except Exception:
        # Never stringify adapter, subprocess or import exceptions with private bytes.
        sys.stderr.write("V3_ADAPTER_QUALIFICATION_INCOMPLETE\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
