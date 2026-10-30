"""Conditional, non-normative proof by prevention; NOT operational attestation.

A protected journal that never reached PREPARED plus an *actually
enforced* pre-side-effect Codespace gate can imply that the particular
attempt did not acquire Codespace through the trusted broker. GitHub
step logs alone do not establish universal gate enforcement. Every
deployed gate/version fact below is an injected assumption.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import unittest
from tests.reference_pre_model_v3 import MemoryClaim, OBSERVATION_ID

ROOT=Path(__file__).resolve().parents[1]
AUDITED_SHA="a"*40


@dataclass(frozen=True)
class InjectedGateBasis:
    audited_sha: str = AUDITED_SHA
    executing_sha: str = AUDITED_SHA
    all_effectful_paths_fenced: bool = True
    legacy_workers_excluded: bool = True
    credential_confinement_qualified: bool = True


def no_acquisition_entailed(record, basis: InjectedGateBasis):
    """Only a logical implication assuming audited source/rollout authority."""
    control=record["pre_model_control"]
    return (
        record["state"] in {"REQUESTED","ADMITTED"}
        and control["disposition"] == "REFUSED_PERMANENT"
        and record["invocation_count"] == 0
        and record["packet_evidence_id"] is None
        and not any(e["kind"] in {"PREPARED","ARMED"} for e in record["history"])
        and basis.audited_sha == basis.executing_sha
        and basis.all_effectful_paths_fenced
        and basis.legacy_workers_excluded
        and basis.credential_confinement_qualified
    )


class ConditionalGateBasisTests(unittest.TestCase):
    def refused(self):
        claim=MemoryClaim()
        claim.reserve_initial()
        worker=claim.worker_token()
        claim.bind_worker(worker,trusted_run_context=True)
        claim.admit(worker)
        claim.fail(worker,"PERMANENT","SOURCE_DIGEST_MISMATCH",
                   trusted_observation_id=OBSERVATION_ID)
        return claim.read()[1]

    def test_current_main_workflow_order_and_dedicated_token_scoping(self):
        source=(ROOT/".github/workflows/review-request.yml").read_text()
        i=source.index("- name: Admit and prepare immutable packet")
        j=source.index("- name: Quarantine unsafe prepared packet",i)
        k=source.index("- name: Start and observe dedicated Codespace")
        self.assertLess(j,k)
        early=source[i:j]
        self.assertIn("internal-prepare",early)
        self.assertNotIn("REVIEW_BROKER_CODESPACE_TOKEN",early)
        self.assertNotIn("CODESPACE_TOKEN",early)
        self.assertNotIn("gh codespace",early)
        self.assertNotIn("user/codespaces/",early)
        self.assertIn("github.token",early)
        # Static check, not a proof of all transitive code or future workers.

    def test_current_prepare_body_has_no_direct_codespace_controller_call(self):
        source=(ROOT/"src/review_broker/orchestration.py").read_text()
        prepare=source.split("\ndef prepare_issue(",1)[1].split(
            "\ndef publish_validated_result(",1)[0]
        self.assertIn("GitHubRefJournal(",prepare)
        self.assertNotIn("CodespaceController",prepare)
        self.assertNotIn("gh codespace",prepare)

    def test_current_codespace_start_path_has_no_proposed_v3_gate(self):
        source=(ROOT/".github/workflows/review-request.yml").read_text()
        start=source.split("- name: Start and observe dedicated Codespace",1)[1].split(
            "- name: Transfer and verify packet",1)[0]
        self.assertIn("user/codespaces/",start)
        self.assertNotIn("internal-verify-v3-codespace-gate",start)
        # Reproduces a future v3 implementation gap, not a v1 regression.

    def test_reconciler_and_cli_are_separate_effectful_routes(self):
        workflow=(ROOT/".github/workflows/review-reconciler.yml").read_text()
        reconcile=(ROOT/"src/review_broker/reconciliation.py").read_text()
        cli=(ROOT/"src/review_broker/cli.py").read_text()
        self.assertIn("REVIEW_BROKER_CODESPACE_TOKEN",workflow)
        self.assertIn("controller.stop()",reconcile)
        self.assertIn("internal-stop-codespace",cli)

    def test_conditional_positive_without_exhaustive_run_step_trace(self):
        self.assertTrue(no_acquisition_entailed(self.refused(),InjectedGateBasis()))
        # Gate assumptions are injected and unqualified in production.

    def test_unknown_old_workers_or_unfenced_path_blocks_inference(self):
        record=self.refused()
        for basis in (
            InjectedGateBasis(legacy_workers_excluded=False),
            InjectedGateBasis(all_effectful_paths_fenced=False),
            InjectedGateBasis(credential_confinement_qualified=False),
            InjectedGateBasis(executing_sha="b"*40),
        ):
            with self.subTest(basis=basis):
                self.assertFalse(no_acquisition_entailed(record,basis))

    def test_uncommitted_permanent_veto_or_prepared_history_blocks_inference(self):
        claim=MemoryClaim()
        claim.reserve_initial()
        worker=claim.worker_token()
        claim.bind_worker(worker,trusted_run_context=True)
        claim.admit(worker)
        self.assertFalse(no_acquisition_entailed(
            claim.read()[1],InjectedGateBasis()))
        claim.prepare(worker)
        self.assertFalse(no_acquisition_entailed(
            claim.read()[1],InjectedGateBasis()))

    def test_skipped_step_without_qualified_gate_does_not_prove_no_access(self):
        job={"steps":[{"name":"start","conclusion":"skipped"}]}
        self.assertEqual(job["steps"][0]["conclusion"],"skipped")
        self.assertFalse(no_acquisition_entailed(
            self.refused(),
            InjectedGateBasis(all_effectful_paths_fenced=False),
        ))


if __name__=="__main__":
    unittest.main()
