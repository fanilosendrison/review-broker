"""Narrow read-only App authority oracle; not a production v3 source adapter."""
import base64
import hashlib
import json
import os
import re
import signal
import sys
import time
import urllib.error
import urllib.request

REPOSITORY = "fanilosendrison/review-broker"
REPOSITORY_ID = 1433701208
ROOT = "/repos/" + REPOSITORY
HEAD = "9258617056e9d2e20cce7f05e6be71ea82dfbd23"
BASE = "83b02c1b9b5bad6c6f64af76affb140957fcbd38"
INSTALLATION = "/installation/repositories?per_page=100&page=1"
COMPARE = ROOT + "/compare/" + BASE + "..." + HEAD
FILES = ROOT + "/pulls/71/files?per_page=100&page=1"
PERMISSIONS = ["contents:read", "pull_requests:read", "metadata:read", "issues:read"]
MAX_BODY = 1048576
CREDENTIAL = re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}")


class QualificationError(ValueError):
    """Only fixed, content-free markers may escape the observation boundary."""


def require(condition, marker):
    if not condition:
        raise QualificationError(marker)


def object_value(value, marker):
    require(type(value) is dict, marker)
    return value


def integer(value, marker):
    require(type(value) is int and value > 0, marker)
    return value


def oid(value, marker):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value)
            and value != "0" * 40, marker)
    return value


def digest(body):
    return hashlib.sha256(body).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def safe_content(raw, token):
    require(token.encode() not in raw and not CREDENTIAL.search(raw.decode("utf-8", "replace")),
            "CREDENTIAL_CONTAMINATION")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        raise QualificationError("HTTP_REDIRECT")


class Client:
    """Fixed-origin GET transport; injected opener is used only by offline tests."""

    def __init__(self, token, opener=None):
        require(type(token) is str and bool(token) and not any(c.isspace() for c in token),
                "SOURCE_TOKEN_REQUIRED")
        self.token = token
        self.opener = opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        ).open
        self.paths = {INSTALLATION, ROOT, ROOT + "/issues/43",
                      ROOT + "/issues/comments/6535094733", ROOT + "/issues/51",
                      ROOT + "/pulls/71", COMPARE, FILES, ROOT + "/git/commits/" + HEAD}

    def allow_object(self, family, sha):
        require(family in {"trees", "blobs"}, "ENDPOINT_REJECTED")
        path = ROOT + "/git/" + family + "/" + oid(sha, "GIT_OBJECT_ID")
        self.paths.add(path)
        return path

    def get(self, path, method="GET"):
        require(method == "GET", "METHOD_REJECTED")
        require(path in self.paths, "ENDPOINT_REJECTED")
        request = urllib.request.Request("https://api.github.com" + path, method="GET", headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
        })
        # The workflow is POSIX/Linux. A real-time alarm bounds even a server
        # trickling bytes below the socket timeout, including response headers.
        def expired(_signum, _frame):
            raise QualificationError("HTTP_DEADLINE")
        previous_handler = signal.signal(signal.SIGALRM, expired)
        previous_timer = signal.setitimer(signal.ITIMER_REAL, 30)
        try:
            deadline = time.monotonic() + 30
            with self.opener(request, timeout=10) as response:
                require(response.status == 200, "HTTP_STATUS")
                # This fixed one-page oracle never follows pagination links. Any
                # Link header, even malformed or ambiguous, fails closed.
                require(not response.headers.get_all("Link"), "PAGINATION_INCOMPLETE")
                chunks, size = [], 0
                while True:
                    require(time.monotonic() <= deadline, "HTTP_DEADLINE")
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    size += len(chunk)
                    require(size <= MAX_BODY, "HTTP_OVERSIZED")
                    chunks.append(chunk)
            raw = b"".join(chunks)
            safe_content(raw, self.token)
            value = json.loads(raw, object_pairs_hook=unique_object)
            safe_content(encoded(value), self.token)
            return value
        except QualificationError:
            raise
        except urllib.error.HTTPError as error:
            raise QualificationError("HTTP_" + str(error.code)) from None
        except (urllib.error.URLError, OSError, TimeoutError):
            raise QualificationError("HTTP_TRANSPORT") from None
        except (ValueError, UnicodeError):
            raise QualificationError("HTTP_JSON") from None
        finally:
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)
            signal.signal(signal.SIGALRM, previous_handler)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def repository(value):
    value = object_value(value, "REPOSITORY_IDENTITY")
    require(value.get("full_name") == REPOSITORY and
            type(value.get("id")) is int and value["id"] == REPOSITORY_ID,
            "REPOSITORY_IDENTITY")
    require(value.get("private") is True and
            value.get("visibility", "private") == "private", "REPOSITORY_VISIBILITY")


def issue(value, number, identity=None):
    value = object_value(value, "ISSUE_IDENTITY")
    require(type(value.get("number")) is int and value["number"] == number
            and "pull_request" not in value, "ISSUE_IDENTITY")
    integer(value.get("id"), "ISSUE_IDENTITY")
    require(identity is None or value["id"] == identity, "ISSUE_IDENTITY")
    require(value.get("url") == f"https://api.github.com{ROOT}/issues/{number}",
            "ISSUE_IDENTITY")
    return value


def body_digest(value):
    require(type(value.get("body")) is str, "BODY_INVALID")
    try:
        return digest(value["body"].encode("utf-8", "strict"))
    except UnicodeError:
        raise QualificationError("BODY_INVALID") from None


def pull(value):
    value = object_value(value, "PR_IDENTITY")
    require(type(value.get("id")) is int and value["id"] == 5101281733 and
            type(value.get("number")) is int and value["number"] == 71, "PR_IDENTITY")
    for role, expected in (("base", BASE), ("head", HEAD)):
        side = object_value(value.get(role), "PR_" + role.upper())
        repository(side.get("repo"))
        require(side.get("sha") == expected, "PR_" + role.upper())
    require(type(value.get("changed_files")) is int and value["changed_files"] == 9,
            "PR_FILE_COUNT")
    return (value["id"], value["number"], BASE, HEAD, value["changed_files"])


def safe_path(value):
    require(type(value) is str and bool(value) and not value.startswith("/") and
            "\\" not in value and all(ord(c) >= 32 and ord(c) != 127 for c in value) and
            all(part not in {"", ".", "..", ".git"} for part in value.split("/")), "FILE_PATH")
    return value


def observe(client, environment):
    """Validate the fixed evidence sequence; retain only explicit safe metadata."""
    slug = environment.get("SOURCE_APP_SLUG", "")
    require(bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", slug)), "APP_IDENTITY")
    installation = environment.get("SOURCE_INSTALLATION_ID", "")
    require(bool(re.fullmatch(r"[1-9][0-9]{0,19}", installation)), "INSTALLATION_IDENTITY")
    require(environment.get("EXPECTED_REPOSITORY") == REPOSITORY and
            environment.get("EXPECTED_REPOSITORY_ID") == str(REPOSITORY_ID), "REPOSITORY_CONFIG")
    source_sha = oid(environment.get("GITHUB_SHA"), "EXECUTION_IDENTITY")
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        require(bool(re.fullmatch(r"[1-9][0-9]{0,19}", environment.get(key, ""))),
                "EXECUTION_IDENTITY")
    require(environment.get("GITHUB_JOB") == "qualify", "EXECUTION_IDENTITY")
    scope = object_value(client.get(INSTALLATION), "INSTALLATION_SCOPE")
    require(type(scope.get("total_count")) is int and scope["total_count"] == 1 and
            type(scope.get("repositories")) is list and len(scope["repositories"]) == 1,
            "INSTALLATION_SCOPE")
    repository(scope["repositories"][0])
    repository(client.get(ROOT))
    original_issue = issue(client.get(ROOT + "/issues/43"), 43, 6101161202)
    issue_hash = body_digest(original_issue)
    comment = object_value(client.get(ROOT + "/issues/comments/6535094733"), "COMMENT_IDENTITY")
    require(type(comment.get("id")) is int and comment["id"] == 6535094733,
            "COMMENT_IDENTITY")
    author = object_value(comment.get("user"), "COMMENT_AUTHOR")
    require(type(author.get("id")) is int and author["id"] == 30498238, "COMMENT_AUTHOR")
    require(comment.get("issue_url") == "https://api.github.com" + ROOT + "/issues/51",
            "COMMENT_PARENT")
    comment_hash = body_digest(comment)
    issue(client.get(ROOT + "/issues/51"), 51)
    first_pr = pull(client.get(ROOT + "/pulls/71"))
    compare = object_value(client.get(COMPARE), "COMPARE_IDENTITY")
    compare_base = object_value(compare.get("base_commit"), "COMPARE_IDENTITY")
    merge = object_value(compare.get("merge_base_commit"), "COMPARE_IDENTITY")
    merge_sha = oid(merge.get("sha"), "COMPARE_MERGE_BASE")
    commits = compare.get("commits")
    require(compare_base.get("sha") == BASE and type(commits) is list and
            1 <= len(commits) <= 250 and type(compare.get("total_commits")) is int and
            compare["total_commits"] == len(commits), "COMPARE_IDENTITY")
    require(object_value(commits[-1], "COMPARE_IDENTITY").get("sha") == HEAD,
            "COMPARE_IDENTITY")
    require((compare.get("status") == "ahead" and merge_sha == BASE) or
            (compare.get("status") == "diverged" and merge_sha not in {BASE, HEAD}),
            "COMPARE_MERGE_BASE")
    files = client.get(FILES)
    require(type(files) is list and len(files) == 9, "FILE_INVENTORY")
    seen = set()
    for item in files:
        item = object_value(item, "FILE_INVENTORY")
        path = safe_path(item.get("filename"))
        require(path not in seen, "FILE_DUPLICATE")
        seen.add(path)
        require(item.get("status") in {"added", "modified", "removed", "renamed", "copied"},
                "FILE_STATUS")
        if item["status"] in {"renamed", "copied"}:
            safe_path(item.get("previous_filename"))
    commit = object_value(client.get(ROOT + "/git/commits/" + HEAD), "GIT_COMMIT")
    require(commit.get("sha") == HEAD, "GIT_COMMIT")
    root = oid(object_value(commit.get("tree"), "GIT_TREE").get("sha"), "GIT_TREE")
    tree = object_value(client.get(client.allow_object("trees", root)), "GIT_TREE")
    require(tree.get("sha") == root and tree.get("truncated") is False and
            type(tree.get("tree")) is list, "GIT_TREE")
    entries, paths = [], set()
    for entry in tree["tree"]:
        entry = object_value(entry, "GIT_TREE")
        path = safe_path(entry.get("path"))
        require("/" not in path and path not in paths, "GIT_TREE")
        paths.add(path)
        if path == "AGENTS.md":
            entries.append(entry)
    require(len(entries) == 1, "GIT_ENTRY")
    entry = entries[0]
    require(entry.get("mode") in {"100644", "100755"} and entry.get("type") == "blob",
            "GIT_MODE")
    blob_oid = oid(entry.get("sha"), "GIT_BLOB")
    blob = object_value(client.get(client.allow_object("blobs", blob_oid)), "GIT_BLOB")
    require(blob.get("sha") == blob_oid and blob.get("encoding") == "base64" and
            type(blob.get("content")) is str, "GIT_BLOB")
    try:
        # GitHub wraps canonical base64 in LF-separated lines. No other
        # whitespace or alphabet relaxation is accepted.
        original = base64.b64decode(blob["content"].replace("\n", ""), validate=True)
    except ValueError:
        raise QualificationError("GIT_BASE64") from None
    safe_content(original, client.token)
    require(type(blob.get("size")) is int and blob["size"] == len(original) and
            type(entry.get("size")) is int and entry["size"] == len(original), "GIT_SIZE")
    actual_oid = hashlib.sha1(b"blob " + str(len(original)).encode() + b"\0" + original).hexdigest()
    require(actual_oid == blob_oid, "GIT_BLOB_IDENTITY")
    require(pull(client.get(ROOT + "/pulls/71")) == first_pr, "PR_DRIFT")
    receipt = {
        "schema_version": "1.0.0", "executing_source_sha": source_sha,
        "run_id": int(environment["GITHUB_RUN_ID"]),
        "run_attempt": int(environment["GITHUB_RUN_ATTEMPT"]), "job": "qualify",
        "app_slug": slug, "installation_id": int(installation),
        "requested_permissions": PERMISSIONS, "repository": REPOSITORY,
        "repository_id": REPOSITORY_ID, "installation_repository_count": 1,
        "issue_number": 43, "issue_id": 6101161202, "issue_body_sha256": issue_hash,
        "comment_id": 6535094733, "comment_parent_issue": 51,
        "comment_author_id": 30498238, "comment_body_sha256": comment_hash,
        "pr_number": 71, "pr_id": 5101281733, "base_sha": BASE, "head_sha": HEAD,
        "observed_compare_merge_base_sha": merge_sha, "changed_file_count": 9,
        "git_commit_oid": HEAD, "git_root_tree_oid": root, "git_blob_oid": blob_oid,
        "git_blob_mode": entry["mode"], "git_blob_type": "blob",
        "git_blob_encoding": "base64", "git_blob_size": len(original),
        "git_original_sha256": digest(original),
        "boundaries": {key: "PASS" for key in (
            "trusted_mint_metadata", "installation_repository_scope", "repository_identity",
            "issue_read", "comment_read", "pr_identity", "file_inventory", "git_blob", "pr_recheck")},
        "github_mutations": 0, "codespace_effects": 0, "model_invocations": 0,
    }
    safe_content(encoded(receipt), client.token)
    receipt["receipt_sha256"] = digest(encoded(receipt))
    return receipt


def main(environment=None, opener=None):
    environment = dict(os.environ if environment is None else environment)
    token = environment.pop("REVIEW_BROKER_SOURCE_TOKEN", "")
    try:
        receipt = observe(Client(token, opener), environment)
        sys.stdout.write(encoded(receipt).decode() + "\n")
        return 0
    except QualificationError as error:
        sys.stderr.write(str(error) + "\n")
        return 1
    except Exception:
        sys.stderr.write("INCOMPLETE_EVIDENCE\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
