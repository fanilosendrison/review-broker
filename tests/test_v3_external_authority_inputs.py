"""Source-bounded boundary falsifiers for candidate GitHub v3 authority.

No network, token or real Codespace. Data is injected; all PASS claims are
conditional on an authenticated caller satisfying the missing trust root.
"""
from __future__ import annotations

from copy import deepcopy
import unittest


class AuthorityBoundaryError(ValueError):
    pass


EXPECTED = {
    "repository": "example/review-broker",
    "repository_id": 1433701208,
    "run_id": 4000,
    "run_attempt": 1,
    "workflow_id": 3100,
    "broker_head_sha": "a" * 40,
    "request_id": "request:sha256:" + "b" * 64,
    "attempt_id": "attempt:sha256:" + "c" * 64,
    "reservation_id": "preparation-dispatch:sha256:" + "d" * 64,
    "generation": 1,
    "codespace_name": "review-broker-safe",
}


def dispatch_outcome(status: int | None, response: dict | None) -> tuple[str, int | None]:
    """Parse candidate return_run_details response; NEVER initiate dispatch."""
    if status == 200:
        if not isinstance(response, dict):
            raise AuthorityBoundaryError("DISPATCH_RUN_DETAILS_INVALID")
        rid = response.get("workflow_run_id")
        if type(rid) is not int or rid <= 0:
            raise AuthorityBoundaryError("DISPATCH_RUN_DETAILS_INVALID")
        return "RUN_ID_OBSERVED", rid
    if status == 204:
        return "ACCEPTANCE_RUN_ID_UNDETERMINED", None
    return "DISPATCH_OUTCOME_UNKNOWN_OR_FAILED", None


def validate_run_metadata(getter, expected: dict) -> dict:
    """Require an injected external metadata provider, not requester text."""
    run_id = expected["run_id"]
    endpoint = f"repos/{expected['repository']}/actions/runs/{run_id}"
    result = getter(endpoint)
    if not isinstance(result, dict):
        raise AuthorityBoundaryError("RUN_METADATA_UNAVAILABLE")
    repo = result.get("repository")
    fields = {
        "id": run_id,
        "run_attempt": expected["run_attempt"],
        "workflow_id": expected["workflow_id"],
        "head_sha": expected["broker_head_sha"],
        "event": "workflow_dispatch",
    }
    if (
        not isinstance(repo, dict)
        or type(repo.get("id")) is not int
        or repo["id"] != expected["repository_id"]
        or repo.get("full_name") != expected["repository"]
        or any(result.get(name) != value for name, value in fields.items())
        or result.get("status") not in {"queued", "in_progress", "completed"}
    ):
        raise AuthorityBoundaryError("RUN_IDENTITY_MISMATCH")
    return result


def validate_worker_binding(getter, expected: dict, worker: dict) -> None:
    """Live identity must also match accepted reservation (journal check elsewhere)."""
    validate_run_metadata(getter, expected)
    if (
        set(worker) != {"run_id", "run_attempt", "request_id", "attempt_id",
                        "generation", "reservation_id"}
        or any(worker[k] != expected[k] for k in worker)
    ):
        raise AuthorityBoundaryError("WORKER_RESERVATION_NOT_BOUND")


def codespace_observation_is_resource_owner(
    observation: dict | None,
    expected: dict,
) -> bool:
    """GitHub Codespace API name/repo/state alone is NOT an exclusive lease."""
    if not isinstance(observation, dict):
        return False
    repo = observation.get("repository")
    return (
        observation.get("name") == expected["codespace_name"]
        and isinstance(repo, dict)
        and repo.get("id") == expected["repository_id"]
        and observation.get("state") in {"Available", "Shutdown"}
        and False  # No request/run/generation ownership is attested by this API.
    )


def may_stop_with_injected_lease(lease: dict | None, expected: dict,
                                 exclusive_lease_proven: bool = False) -> bool:
    """A fixture-only implication, NOT a GitHub/production lease verifier."""
    if not exclusive_lease_proven or not isinstance(lease, dict):
        return False
    required = {"codespace_name", "repository_id", "request_id", "attempt_id",
                "run_id", "run_attempt", "generation", "reservation_id"}
    return set(lease) == required and all(lease[k] == expected[k] for k in required)


def sample_run():
    return {
        "id": EXPECTED["run_id"],
        "run_attempt": EXPECTED["run_attempt"],
        "workflow_id": EXPECTED["workflow_id"],
        "head_sha": EXPECTED["broker_head_sha"],
        "event": "workflow_dispatch",
        "status": "in_progress",
        "repository": {
            "id": EXPECTED["repository_id"], "full_name": EXPECTED["repository"],
        },
    }


def getter_for(run, calls=None):
    def get(endpoint):
        if calls is not None:
            calls.append(endpoint)
        if endpoint != f"repos/{EXPECTED['repository']}/actions/runs/{EXPECTED['run_id']}":
            raise AssertionError("EXTERNAL_PATH_NOT_BOUNDED")
        return deepcopy(run)
    return get


def sample_worker():
    return {k: EXPECTED[k] for k in (
        "run_id", "run_attempt", "request_id", "attempt_id",
        "generation", "reservation_id",
    )}


class ExternalAuthorityBoundaryTests(unittest.TestCase):
    def test_dispatch_200_with_run_details_returns_observed_run_id(self):
        status, rid = dispatch_outcome(200, {"workflow_run_id": EXPECTED["run_id"]})
        self.assertEqual((status,rid),("RUN_ID_OBSERVED",EXPECTED["run_id"]))

    def test_dispatch_204_yields_unknown_run_id_not_new_dispatch(self):
        status, rid = dispatch_outcome(204, None)
        self.assertEqual((status,rid),("ACCEPTANCE_RUN_ID_UNDETERMINED",None))

    def test_dispatch_invalid_run_id_boolean_is_rejected(self):
        for bad in (0,-1,True,"4000",None):
            with self.subTest(value=bad), self.assertRaisesRegex(
                AuthorityBoundaryError,"DISPATCH_RUN_DETAILS_INVALID"
            ):
                dispatch_outcome(200,{"workflow_run_id":bad})

    def test_dispatch_lost_or_unknown_status_never_returns_a_run(self):
        for code in (None,403,409,422,500):
            with self.subTest(status=code):
                self.assertEqual(
                    dispatch_outcome(code,None),
                    ("DISPATCH_OUTCOME_UNKNOWN_OR_FAILED",None),
                )

    def test_run_metadata_positive_bound_read(self):
        calls=[]
        r=validate_run_metadata(getter_for(sample_run(),calls),EXPECTED)
        self.assertEqual(r["id"],EXPECTED["run_id"])
        self.assertEqual(calls,[f"repos/{EXPECTED['repository']}/actions/runs/4000"])

    def test_run_metadata_repository_id_name_change_rejected(self):
        for field,value in (("id",123),("full_name","untrusted/repo")):
            with self.subTest(field=field):
                r=sample_run();r["repository"][field]=value
                with self.assertRaisesRegex(AuthorityBoundaryError,"RUN_IDENTITY_MISMATCH"):
                    validate_run_metadata(getter_for(r),EXPECTED)

    def test_run_metadata_workflow_head_and_event_change_rejected(self):
        for field,value in (("workflow_id",333),("head_sha","f"*40),
                            ("event","issues"),("run_attempt",2),("id",12)):
            with self.subTest(field=field):
                r=sample_run();r[field]=value
                with self.assertRaisesRegex(AuthorityBoundaryError,"RUN_IDENTITY_MISMATCH"):
                    validate_run_metadata(getter_for(r),EXPECTED)

    def test_run_metadata_unavailable_refuses_binding(self):
        with self.assertRaisesRegex(AuthorityBoundaryError,"RUN_METADATA_UNAVAILABLE"):
            validate_run_metadata(getter_for(None),EXPECTED)

    def test_worker_bound_to_run_and_reservation_positive(self):
        validate_worker_binding(getter_for(sample_run()),EXPECTED,sample_worker())

    def test_worker_reservation_tamper_rejected(self):
        for field,value in (("generation",2),("run_id",999),
                            ("reservation_id","preparation-dispatch:sha256:"+"e"*64),
                            ("request_id","request:sha256:"+"f"*64)):
            with self.subTest(field=field):
                w=sample_worker();w[field]=value
                with self.assertRaisesRegex(
                    AuthorityBoundaryError,"WORKER_RESERVATION_NOT_BOUND"
                ):
                    validate_worker_binding(getter_for(sample_run()),EXPECTED,w)

    def test_unchecked_worker_extra_field_is_rejected(self):
        w=sample_worker();w["caller_override"]=True
        with self.assertRaisesRegex(AuthorityBoundaryError,"WORKER_RESERVATION_NOT_BOUND"):
            validate_worker_binding(getter_for(sample_run()),EXPECTED,w)

    def test_codespace_api_name_and_state_are_not_lease(self):
        observed={"name":EXPECTED["codespace_name"],"state":"Available",
                  "repository":{"id":EXPECTED["repository_id"]}}
        self.assertFalse(codespace_observation_is_resource_owner(observed,EXPECTED))

    def test_codespace_concurrency_group_text_is_not_lease(self):
        observed={"name":EXPECTED["codespace_name"],"state":"Available",
                  "repository":{"id":EXPECTED["repository_id"]},
                  "concurrency_group":"review-broker-single-reviewer"}
        self.assertFalse(codespace_observation_is_resource_owner(observed,EXPECTED))

    def test_cross_request_resource_lease_rejected_when_mismatched(self):
        lease={k:EXPECTED[k] for k in (
            "codespace_name","repository_id","request_id","attempt_id",
            "run_id","run_attempt","generation","reservation_id")}
        lease["request_id"]="request:sha256:"+"f"*64
        self.assertFalse(may_stop_with_injected_lease(lease,EXPECTED,True))

    def test_only_externally_proven_matching_lease_allows_fixture_stop(self):
        lease={k:EXPECTED[k] for k in (
            "codespace_name","repository_id","request_id","attempt_id",
            "run_id","run_attempt","generation","reservation_id")}
        self.assertFalse(may_stop_with_injected_lease(lease,EXPECTED,False))
        self.assertTrue(may_stop_with_injected_lease(lease,EXPECTED,True))


if __name__ == "__main__":
    unittest.main()
