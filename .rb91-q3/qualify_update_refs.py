#!/usr/bin/env python3
"""RB91-Q3: real GitHub GraphQL expected-old experiment, synthetic refs only.

No OIDC, Codespaces, Codex, reviewed material, or production journal access.
Run as `python3 qualify_update_refs.py run|cleanup` in a dedicated branch-only
GitHub Actions job with `contents: write` and no other GitHub permission.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from datetime import datetime, timezone

REPO = "fanilosendrison/review-broker"
RUN_BRANCH = "qualification/rb91-q3-graphql-20261107"
PREFIX = "refs/heads/qualification/rb91-q3-data-"
PATH = ".rb91-q3/synthetic-state.json"
ZERO = "0" * 40
OUT = Path("rb91-q3-receipts")
QUERY_REPO = "query($owner:String!,$name:String!){repository(owner:$owner,name:$name){id,databaseId,nameWithOwner}}"
QUERY_SCHEMA = 'query{__type(name:"RefUpdate"){inputFields{name}} __schema{mutationType{fields{name}}}}'
MUTATE = "mutation($input:UpdateRefsInput!){updateRefs(input:$input){clientMutationId}}"
OID = re.compile(r"[a-f0-9]{40}\Z")

class Q3Stop(RuntimeError):
    pass


def record_json(name: str, data: object) -> None:
    OUT.mkdir(exist_ok=True)
    p = OUT / name
    if not re.fullmatch(r"[a-z0-9_-]+\.json", name):
        raise Q3Stop("INVALID_RECEIPT_FILENAME")
    p.write_text(json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def api(method: str, endpoint: str, data: object | None = None) -> dict:
    # All endpoints are developer-fixed; arguments never carry raw credentials.
    if not endpoint.startswith(f"repos/{REPO}/"):
        raise Q3Stop("API_ENDPOINT_OUT_OF_SCOPE")
    args = ["gh", "api", "--method", method, endpoint]
    if data is not None:
        args += ["--input", "-"]
    return _gh(args, data)


def graphql(query: str, variables: dict | None = None) -> dict:
    return _gh(["gh", "api", "graphql", "--input", "-"], {"query": query, "variables": variables or {}})


def _gh(args: list[str], data: object | None) -> dict:
    env = dict(os.environ)
    if not env.get("GH_TOKEN"):
        raise Q3Stop("SCOPED_GITHUB_ACTIONS_TOKEN_MISSING")
    # Credentials are supplied only through the inherited Actions environment.
    request_body = json.dumps(data, separators=(",", ":")) if data is not None else None
    try:
        p = subprocess.run(args, input=request_body, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=35, env=env, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "class": type(exc).__name__}
    if p.returncode != 0:
        # Retain only a parsed status code; raw stderr may echo sensitive material.
        match = re.search(r"\bHTTP ([1-5][0-9][0-9])\b", p.stderr)
        if match:
            kind = "HTTP_" + match.group(1)
        elif "GraphQL:" in p.stderr or "graphql:" in p.stderr.lower():
            kind = "GRAPHQL_REFUSAL_FROM_CLI"
        else:
            kind = "CLI_OR_TRANSPORT_FAILURE"
        redacted = p.stderr.replace(env["GH_TOKEN"], "[REDACTED_TOKEN]")
        redacted = re.sub(r"(?:ghp_|ghs_|gho_|github_pat_)[A-Za-z0-9_]+", "[REDACTED_CREDENTIAL]", redacted)
        redacted = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9_.-]+", r"\1[REDACTED]", redacted)
        return {"ok": False, "class": kind, "code": p.returncode,
                "stderr_sha256": hashlib.sha256(redacted.encode()).hexdigest(),
                "sanitized_error_preview": redacted[:480]}
    try:
        value = json.loads(p.stdout)
    except (ValueError, TypeError):
        return {"ok": False, "class": "MALFORMED_RESPONSE"}
    if not isinstance(value, dict):
        return {"ok": False, "class": "UNEXPECTED_RESPONSE_SHAPE"}
    if value.get("errors"):
        return {"ok": False, "class": "GRAPHQL_ERRORS", "count": len(value["errors"])}
    return {"ok": True, "value": value}


def require_ok(result: dict, error: str) -> dict:
    if not result["ok"]:
        raise Q3Stop(error + ":" + result.get("class", "UNKNOWN"))
    return result["value"]


def get_ref(ref: str) -> dict:
    if not ref.startswith(PREFIX) or not re.fullmatch(r"refs/heads/qualification/rb91-q3-data-[a-z0-9-]+", ref):
        raise Q3Stop("TEST_REF_OUT_OF_SCOPE")
    return api("GET", f"repos/{REPO}/git/ref/{ref.removeprefix('refs/')} ".strip())


def get_ref_sha(ref: str) -> str:
    value = require_ok(get_ref(ref), "REF_READ_FAILED")
    sha = value.get("object", {}).get("sha")
    if not isinstance(sha, str) or not OID.fullmatch(sha):
        raise Q3Stop("REF_OBJECT_INVALID")
    return sha


def git_commit(parent: str, payload: dict, label: str) -> str:
    if not OID.fullmatch(parent):
        raise Q3Stop("COMMIT_PARENT_INVALID")
    parent_value = require_ok(api("GET", f"repos/{REPO}/git/commits/{parent}"), "PARENT_UNAVAILABLE")
    tree = parent_value.get("tree", {}).get("sha")
    if not isinstance(tree, str) or not OID.fullmatch(tree):
        raise Q3Stop("PARENT_TREE_INVALID")
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    blob = require_ok(api("POST", f"repos/{REPO}/git/blobs", {"content": raw, "encoding": "utf-8"}), "BLOB_FAILED")["sha"]
    tree_value = require_ok(api("POST", f"repos/{REPO}/git/trees", {"base_tree": tree,
       "tree": [{"path": PATH, "mode": "100644", "type": "blob", "sha": blob}]}), "TREE_FAILED")
    sha = require_ok(api("POST", f"repos/{REPO}/git/commits", {"message": f"rb91-q3 synthetic {label}",
        "tree": tree_value["sha"], "parents": [parent]}), "COMMIT_FAILED")["sha"]
    if not OID.fullmatch(sha) or sha == parent:
        raise Q3Stop("COMMIT_NOT_UNIQUE")
    return sha


def update_ref(repo_id: str, name: str, before: str, after: str, cid: str) -> dict:
    if not name.startswith(PREFIX) or not OID.fullmatch(before) or not OID.fullmatch(after):
        raise Q3Stop("UNSCOPED_GRAPHQL_MUTATION_REFUSED")
    result = graphql(MUTATE, {"input": {"repositoryId": repo_id,
         "refUpdates": [{"name": name, "beforeOid": before, "afterOid": after, "force": False}],
         "clientMutationId": cid}})
    if result["ok"] and "updateRefs" not in result["value"].get("data", {}):
        return {"ok": False, "class": "GRAPHQL_UPDATE_REFS_MISSING"}
    return result


def validated_context() -> tuple[str, str, str, str]:
    e = os.environ
    if (e.get("GITHUB_REPOSITORY") != REPO
      or e.get("GITHUB_REF") != f"refs/heads/{RUN_BRANCH}"
      or e.get("GITHUB_EVENT_NAME") != "push"):
        raise Q3Stop("ACTION_CONTEXT_INVALID")
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        if not re.fullmatch(r"[1-9][0-9]*", e.get(key, "")):
            raise Q3Stop("ACTION_RUN_ID_INVALID")
    base = e.get("GITHUB_SHA", "")
    if not OID.fullmatch(base):
        raise Q3Stop("ACTION_SHA_INVALID")
    nonce = secrets.token_hex(8)
    name_base = f"{PREFIX}{e['GITHUB_RUN_ID']}-{e['GITHUB_RUN_ATTEMPT']}-{nonce}"
    return base, name_base, e["GITHUB_RUN_ID"], e["GITHUB_RUN_ATTEMPT"]


def make_case(base: str, prefix: str, label: str, nonce: str) -> tuple[str, str, str, str]:
    ref = prefix + "-" + label
    absence = get_ref(ref)
    if absence["ok"]:
        raise Q3Stop("TEST_REF_ALREADY_PRESENT")
    if absence.get("class") != "HTTP_404":
        raise Q3Stop("TEST_REF_EXISTENCE_UNCERTAIN:" + absence.get("class", "UNKNOWN"))
    parent = git_commit(base, {"protocol": "rb91-q3-synthetic-v1", "state": "PREPARED",
        "invocation_count": 0, "nonce": nonce, "case": label}, label + " P")
    a = git_commit(parent, {"protocol": "rb91-q3-synthetic-v1", "state": "ARMED",
        "invocation_count": 1, "nonce": nonce, "case": label, "challenge": "A"}, label + " A")
    b = git_commit(parent, {"protocol": "rb91-q3-synthetic-v1", "state": "ARMED",
        "invocation_count": 1, "nonce": nonce, "case": label, "challenge": "B"}, label + " B")
    require_ok(api("POST", f"repos/{REPO}/git/refs", {"ref": ref, "sha": parent}), "REF_CREATE_FAILED")
    if get_ref_sha(ref) != parent:
        raise Q3Stop("REF_CREATE_NOT_OBSERVED")
    return ref, parent, a, b


def run() -> None:
    base, prefix, run_id, run_attempt = validated_context()
    result = {"task": "RB91_Q3_EXPECTED_OLD", "repository": REPO, "status": "IN_PROGRESS",
              "run_id": run_id, "run_attempt": run_attempt, "branch": RUN_BRANCH,
              "base_sha": base, "cases": {}, "no_oidc": True, "no_model": True,
              "started_at": datetime.now(timezone.utc).isoformat()}
    record_json("result.json", result)
    refs = []
    plan = {"repository": REPO, "run_id": run_id, "run_attempt": run_attempt, "refs": refs}
    try:
        schema = require_ok(graphql(QUERY_SCHEMA), "GRAPHQL_SCHEMA_UNAVAILABLE")
        fields = schema.get("data", {}).get("__type", {}).get("inputFields", [])
        field_names = {f["name"] for f in fields}
        mut_names = {f["name"] for f in schema.get("data", {}).get("__schema", {}).get("mutationType", {}).get("fields", [])}
        if not {"beforeOid", "afterOid", "force", "name"}.issubset(field_names) or "updateRefs" not in mut_names:
            raise Q3Stop("GRAPHQL_EXPECTED_OLD_SCHEMA_MISSING")
        identity = require_ok(graphql(QUERY_REPO, {"owner": "fanilosendrison", "name": "review-broker"}), "GRAPHQL_REPOSITORY_UNAVAILABLE")
        info = identity.get("data", {}).get("repository", {})
        if info.get("nameWithOwner") != REPO or info.get("databaseId") != 1433701208 or not info.get("id"):
            raise Q3Stop("GRAPHQL_REPOSITORY_ID_MISMATCH")
        repo_id = info["id"]
        result["graphql_schema"] = "EXPECTED_OLD_PRESENT"
        result["repository_id"] = info["databaseId"]
        record_json("result.json", result)
        for label in ("race", "identical", "stale", "ack"):
            ref, p, a, b = make_case(base, prefix, label, secrets.token_hex(8))
            refs.append({"ref": ref, "current_sha": p, "created": True})
            record_json("cleanup-plan.json", plan)
            if label in {"race", "identical"}:
                targets = [a, b] if label == "race" else [a, a]
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [executor.submit(update_ref, repo_id, ref, p, v, label+"-"+str(i)) for i,v in enumerate(targets)]
                    outcomes = [f.result() for f in futures]
                observed = get_ref_sha(ref)
                # Record exact current head immediately; a later diagnostic failure must
                # never leave a stale cleanup plan at PREPARED.
                refs[-1]["current_sha"] = observed
                record_json("cleanup-plan.json", plan)
                success = [i for i, v in enumerate(outcomes) if v["ok"]]
                if len(success) != 1 or observed != targets[success[0]]:
                    raise Q3Stop(label.upper()+"_EXPECTED_OLD_VIOLATED")
                failures = [x for x in outcomes if not x["ok"]]
                result["cases"][label] = {"status": "PASS_ONE_ACCEPTED", "parent": p, "targets": targets,
                    "winner": success[0], "head": observed, "loser": failures}
            elif label == "stale":
                first = update_ref(repo_id, ref, p, a, label+"-win")
                second = update_ref(repo_id, ref, p, b, label+"-stale") if first["ok"] else {"ok":False,"class":"NOT_ATTEMPTED"}
                observed = get_ref_sha(ref)
                refs[-1]["current_sha"] = observed
                record_json("cleanup-plan.json", plan)
                if not first["ok"] or second["ok"] or observed != a:
                    raise Q3Stop("STALE_BEFORE_OID_INCORRECT")
                result["cases"][label] = {"status": "PASS_ONE_ACCEPTED", "parent": p,
                    "head": observed, "stale_error": second}
            else:
                actual = update_ref(repo_id, ref, p, a, label+"-discard")
                # Force an application-level lost acknowledgement *after the real HTTP request*;
                # never submit a second mutation. Record the diagnostic separately.
                if not actual["ok"]:
                    raise Q3Stop("ACK_SCENARIO_INITIAL_COMMIT_FAILED:"+actual.get("class", "UNKNOWN"))
                visible_to_caller = None
                observed = get_ref_sha(ref)
                if visible_to_caller is not None or observed != a:
                    raise Q3Stop("ACK_LOSS_NOT_CONSERVATIVE")
                result["cases"][label] = {"status": "PASS_SIMULATED_LOST_CLIENT_ACK",
                    "parent": p, "head": observed, "mutation_count": 1,
                    "retry_count": 0, "oidc_mints": 0}
            refs[-1]["current_sha"] = result["cases"][label]["head"]
            record_json("cleanup-plan.json", plan)
            record_json("result.json", result)
        result["status"] = "PASS_BOUNDED_REAL_GRAPHQL"
    except Exception as exc:
        result["status"] = "STOPPED"
        result["failed_gate"] = str(exc) if isinstance(exc, Q3Stop) else type(exc).__name__
        raise
    finally:
        result["completed_at"] = datetime.now(timezone.utc).isoformat()
        record_json("result.json", result)
        record_json("cleanup-plan.json", plan)


def cleanup() -> None:
    base, _, run_id, run_attempt = validated_context()
    plan = json.loads((OUT/"cleanup-plan.json").read_text())
    if plan.get("repository") != REPO or plan.get("run_id") != run_id or plan.get("run_attempt") != run_attempt:
        raise Q3Stop("CLEANUP_PLAN_IDENTITY_MISMATCH")
    identity = require_ok(graphql(QUERY_REPO, {"owner": "fanilosendrison", "name": "review-broker"}), "GRAPHQL_REPOSITORY_UNAVAILABLE")
    info = identity.get("data", {}).get("repository", {})
    if info.get("databaseId") != 1433701208:
        raise Q3Stop("CLEANUP_REPOSITORY_MISMATCH")
    outcomes = []
    for item in plan["refs"]:
        ref, expected = item["ref"], item["current_sha"]
        if not ref.startswith(PREFIX + run_id + "-" + run_attempt + "-") or not OID.fullmatch(expected):
            raise Q3Stop("CLEANUP_REF_OUT_OF_SCOPE")
        observed = get_ref_sha(ref)
        if observed != expected:
            raise Q3Stop("CLEANUP_UNEXPECTED_REF_HEAD")
        response = update_ref(info["id"], ref, expected, ZERO, "cleanup-"+ref.split("-")[-1])
        if not response["ok"]:
            raise Q3Stop("CLEANUP_GRAPHQL_DELETE_REJECTED:"+response.get("class", "UNKNOWN"))
        after = get_ref(ref)
        if after["ok"] or after.get("class") != "HTTP_404":
            raise Q3Stop("CLEANUP_ABSENCE_NOT_OBSERVED:" + after.get("class", "STILL_PRESENT"))
        outcomes.append({"ref": ref, "deleted": True, "negative_read_class": "HTTP_404"})
    record_json("cleanup.json", {"status": "DONE", "results": outcomes})


def main():
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in {"run", "cleanup"}:
            raise Q3Stop("USAGE_RUN_OR_CLEANUP")
        globals()[sys.argv[1]]()
    except Exception as exc:
        print("Q3_RESULT=STOPPED; GATE=" + (str(exc) if isinstance(exc,Q3Stop) else type(exc).__name__))
        sys.exit(1)
    else:
        print("Q3_RESULT=PASS:"+sys.argv[1])

if __name__ == "__main__":
    main()