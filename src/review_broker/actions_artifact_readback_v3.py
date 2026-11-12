"""Shared authenticated Artifact metadata and raw-byte download, with no upload authority."""
from __future__ import annotations

from datetime import datetime
import hashlib
from urllib.parse import urlsplit
from urllib.request import Request

from .artifact_locator import _timestamp
from .identity import artifact_identity
from .remote_prepared_receipt_v3 import api_decimal_v3, positive_json_integer_v3


def observe_named_artifact_v3(adapter, snapshot, worker, name, before_effect):
    expected = adapter.worker_history.expected
    repository = adapter.metadata.object(adapter.metadata.get("", before_effect))
    if (repository.get("full_name") != snapshot.repository
            or repository.get("node_id") != snapshot.repository_node_id
            or positive_json_integer_v3(repository.get("id")) != expected.repository_id):
        raise ValueError("PREPARED_ARTIFACT_REPOSITORY_MISMATCH")
    artifacts = adapter.metadata.listing(f"/actions/runs/{worker.run_id}/artifacts",
        {"name": name}, "artifacts", before_effect)
    if any(item.get("name") != name for item in artifacts):
        raise ValueError("PREPARED_ARTIFACT_FILTER_MISMATCH")
    if len(artifacts) != 1:
        raise ValueError("PREPARED_ARTIFACT_UNAVAILABLE_OR_AMBIGUOUS")
    item = artifacts[0]
    run = item.get("workflow_run")
    if type(run) is not dict:
        raise ValueError("PREPARED_ARTIFACT_RUN_MISSING")
    if (positive_json_integer_v3(run.get("id")) != worker.run_id
            or positive_json_integer_v3(run.get("repository_id")) != expected.repository_id
            or positive_json_integer_v3(run.get("head_repository_id")) != expected.repository_id
            or run.get("head_sha") != expected.executing_source_sha):
        raise ValueError("PREPARED_ARTIFACT_RUN_MISMATCH")
    size = positive_json_integer_v3(item.get("size_in_bytes"))
    if size > adapter.budget.max_archive_bytes:
        raise ValueError("PREPARED_ARTIFACT_ARCHIVE_BUDGET")
    digest = item.get("digest")
    import re
    if type(digest) is not str or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None:
        raise ValueError("ARTIFACT_DIGEST_INVALID")
    created = _timestamp(item.get("created_at"), "PREPARED_CREATED_AT_INVALID")
    expires = _timestamp(item.get("expires_at"), "PREPARED_EXPIRES_AT_INVALID")
    now = adapter.clock()
    if (type(now) is not datetime or now.tzinfo is None or created >= expires
            or item.get("expired") is not False or now >= expires):
        raise ValueError("PREPARED_ARTIFACT_EXPIRED_OR_TIME_INVALID")
    return {
        "backend": "github-actions-artifact", "repository": expected.repository,
        "repository_id": expected.repository_id, "workflow_run_id": worker.run_id,
        "workflow_run_attempt": 1, "workflow_id": expected.workflow_id,
        "workflow_path": expected.workflow_path, "execution_ref": expected.workflow_execution_ref,
        "executable_sha": expected.executing_source_sha, "verified_worker_job_id": worker.job_id,
        "artifact_id": api_decimal_v3(item.get("id")), "artifact_name": name,
        "artifact_digest": digest, "artifact_size_in_bytes": size,
        "created_at": item.get("created_at"), "expires_at": item.get("expires_at"),
    }


def download_artifact_bytes_v3(adapter, storage, before_effect):
    """Caller validates the storage contract first. No recompression or ZIP wrapper."""
    response = adapter.metadata.get(f"/actions/artifacts/{storage['artifact_id']}/zip", before_effect)
    locations = [v for k, v in response.headers.items() if k.lower() == "location"]
    if response.status != 302 or len(locations) != 1:
        raise ValueError("PREPARED_ARCHIVE_REDIRECT_REQUIRED")
    destination = urlsplit(locations[0])
    host = destination.hostname or ""
    if (destination.scheme != "https" or destination.username or destination.password
            or destination.port not in {None, 443} or destination.fragment
            or not destination.path.startswith("/")
            or not any(host.endswith("." + suffix) and host != suffix for suffix in (
                "blob.core.windows.net", "actions.githubusercontent.com"))):
        raise ValueError("PREPARED_ARCHIVE_REDIRECT_INVALID")
    request = Request(locations[0], method="GET")
    chunks, count, digest = [], 0, hashlib.sha256()
    try:
        before_effect()
        stream = iter(adapter.storage_executor(request, max_bytes=adapter.budget.max_archive_bytes))
        while True:
            before_effect()
            try:
                chunk = next(stream)
            except StopIteration:
                break
            if type(chunk) is not bytes:
                raise ValueError("PREPARED_ARCHIVE_CHUNK_INVALID")
            count += len(chunk)
            if count > adapter.budget.max_archive_bytes or count > storage["artifact_size_in_bytes"]:
                raise ValueError("PREPARED_ARCHIVE_SIZE_MISMATCH")
            digest.update(chunk)
            chunks.append(chunk)
    except TimeoutError:
        if adapter.failure_observer is not None:
            adapter.failure_observer.read_timeout(adapter, request, storage)
        raise ValueError("PREPARED_ARCHIVE_READ_UNAVAILABLE_OR_INVALID") from None
    except Exception:
        raise ValueError("PREPARED_ARCHIVE_READ_UNAVAILABLE_OR_INVALID") from None
    raw = b"".join(chunks)
    if count != storage["artifact_size_in_bytes"] or "sha256:" + digest.hexdigest() != storage["artifact_digest"]:
        if adapter.failure_observer is not None:
            adapter.failure_observer.verification_failed("ARCHIVE_BYTES", "artifact:" + storage["artifact_digest"],
                artifact_identity(raw), adapter, storage, storage["artifact_size_in_bytes"], count)
        raise ValueError("PREPARED_ARCHIVE_DIGEST_OR_SIZE_MISMATCH")
    before_effect()
    return raw
