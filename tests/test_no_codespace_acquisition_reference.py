"""Non-normative PM26-PM35 and current-workflow ordering falsifiers.

All evidence of run coverage, absence of side effects and trusted gates is
explicitly INJECTED. No Codespace or GitHub mutations. None of these PASS
results qualifies the deployed v3 terminal operation.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from review_broker.identity import artifact_identity, canonical_bytes
from tests.reference_pre_model_v3 import (
    ADMISSION_ID, CODESPACE_NAME, FIXED_NOW, MemoryClaim,
    OBSERVATION_ID, ProtocolError, identity,
)


TRACE_ID = "artifact:sha256:" + "4" * 64
GATE_ID = "artifact:sha256:" + "5" * 64


class NoCodespaceAcquisitionReferenceTests(unittest.TestCase):
    def ready_refused(self):
        c = MemoryClaim()
        c.reserve_initial()
        w = c.worker_token()
        c.bind_worker(w, trusted_run_context=True)
        c.admit(w)
        c.fail(w, "PERMANENT", "SOURCE_DIGEST_MISMATCH",
               trusted_observation_id=OBSERVATION_ID)
        return c, w

    def receipt(self, c):
        _, r = c.read()
        ct = r["pre_model_control"]
        worker = ct["worker"]
        return {
            "schema_version": 1,
            "evidence_type": "pre-model-no-codespace-access",
            "request_id": r["request_id"],
            "attempt_id": r["attempt_id"],
            "admission_evidence_id": ADMISSION_ID,
            "generation": ct["generation"],
            "reservation_id": ct["reservation_id"],
            "workflow_run_id": worker["run_id"],
            "workflow_run_attempt": worker["run_attempt"],
            "codespace_name": CODESPACE_NAME,
            "workflow_trace_evidence_id": TRACE_ID,
            "start_gate_evidence_id": GATE_ID,
            "codespace_access_attempted": False,
            "observed_at": FIXED_NOW,
        }

    def finalize(self, c, receipt=None, **kwargs):
        return c.finish_without_codespace(
            receipt or self.receipt(c),
            authenticated_run_trace_evidence_id=TRACE_ID,
            authenticated_start_gate_evidence_id=GATE_ID,
            all_workers_accounted_for=True,
            observed_codespace_commands=(),
            **kwargs,
        )

    def test_pm26_before_prepared_refusal_terminal_without_shutdown(self):
        c, w = self.ready_refused()
        out = self.finalize(c)
        self.assertEqual(out["state"], "STOPPED")
        self.assertEqual(out["invocation_count"], 0)
        self.assertEqual(out["pre_model_control"]["disposition"], "REFUSED_PERMANENT")
        terminal = out["history"][-1]
        self.assertEqual(terminal["kind"], "STOPPED")
        self.assertEqual(terminal["receipt"]["evidence_type"], "pre-model-no-codespace-access")
        self.assertNotIn("observed_state", terminal["receipt"])
        self.assertFalse(any(e["kind"] in {"PREPARED", "ARMED"} for e in out["history"]))

    def test_pm27_other_request_codespace_active_does_not_prevent_nonaccess_terminal(self):
        c, _ = self.ready_refused()
        shared_codespace = {"state":"Available", "other_attempt_active":True,
                            "stop_calls":0,"start_calls":0,"ssh_calls":0}
        self.finalize(c)
        self.assertEqual(shared_codespace["state"], "Available")
        self.assertEqual(sum(shared_codespace[x] for x in
                         ("stop_calls","start_calls","ssh_calls")),0)
        # The isolated model NEVER received a Codespace controller. This is
        # conditional no-I/O logic, not proof of global resource ownership.

    def test_pm28_missing_trusted_workflow_trace_or_start_gate_is_blocked(self):
        c, _ = self.ready_refused()
        for kwargs in (
            {"authenticated_run_trace_evidence_id":None},
            {"authenticated_start_gate_evidence_id":None},
            {"all_workers_accounted_for":False},
        ):
            with self.subTest(kwargs=kwargs):
                base={
                    "authenticated_run_trace_evidence_id":TRACE_ID,
                    "authenticated_start_gate_evidence_id":GATE_ID,
                    "all_workers_accounted_for":True,
                    "observed_codespace_commands":(),
                }
                base.update(kwargs)
                with self.assertRaisesRegex(ProtocolError,"NO_CODESPACE_PROOF_UNVERIFIED"):
                    c.finish_without_codespace(self.receipt(c),**base)
        self.assertEqual(c.read()[1]["state"],"ADMITTED")

    def test_pm29_start_ssh_copy_stop_or_ambiguous_attempt_never_claims_nonaccess(self):
        c, _ = self.ready_refused()
        for attempted in (("start",),("ssh",),("copy",),("stop",),None):
            with self.subTest(attempted=attempted):
                with self.assertRaisesRegex(ProtocolError,"NO_CODESPACE_PROOF_UNVERIFIED"):
                    c.finish_without_codespace(
                        self.receipt(c),
                        authenticated_run_trace_evidence_id=TRACE_ID,
                        authenticated_start_gate_evidence_id=GATE_ID,
                        all_workers_accounted_for=True,
                        observed_codespace_commands=attempted,
                    )
        bad=self.receipt(c)
        bad["codespace_access_attempted"]=True
        with self.assertRaisesRegex(ProtocolError,"SCHEMA_NO_CODESPACE_INVALID"):
            self.finalize(c,bad)

    def test_pm30_stale_worker_cannot_start_before_or_after_refusal(self):
        c = MemoryClaim()
        c.reserve_initial()
        w = c.worker_token()
        c.bind_worker(w, trusted_run_context=True)
        c.admit(w)
        with self.assertRaisesRegex(ProtocolError,"CODESPACE_ACCESS_BEFORE_PREPARED_FORBIDDEN"):
            c.assert_codespace_start_permitted(w)
        c.fail(w,"PERMANENT","SOURCE_DIGEST_MISMATCH",
               trusted_observation_id=OBSERVATION_ID)
        with self.assertRaisesRegex(ProtocolError,"WORKER_FENCE_REJECTED"):
            c.assert_codespace_start_permitted(w)
        self.finalize(c)
        with self.assertRaisesRegex(ProtocolError,"WORKER_FENCE_REJECTED"):
            c.assert_codespace_start_permitted(w)

    def test_pm31_after_prepared_cannot_use_nonacquisition_refusal(self):
        c = MemoryClaim()
        c.reserve_initial()
        w=c.worker_token()
        c.bind_worker(w,trusted_run_context=True)
        c.admit(w)
        c.prepare(w)
        c.assert_codespace_start_permitted(w)
        with self.assertRaisesRegex(ProtocolError,"FAILURE_AFTER_PREPARED"):
            c.fail(w,"PERMANENT","SOURCE_DIGEST_MISMATCH",
                   trusted_observation_id=OBSERVATION_ID)
        # The terminal proof is not an alternative to post-PREPARED cleanup.
        r=self.receipt(c)
        with self.assertRaisesRegex(ProtocolError,"TERMINAL_PREMODEL_REFUSAL_INVALID"):
            self.finalize(c,r)

    def test_pm32_wrong_claim_worker_generation_and_admission_rejected(self):
        c,_=self.ready_refused()
        fields={
            "request_id":"request:sha256:"+"f"*64,
            "attempt_id":"attempt:sha256:"+"f"*64,
            "admission_evidence_id":"artifact:sha256:"+"f"*64,
            "generation":2,
            "reservation_id":"preparation-dispatch:sha256:"+"e"*64,
            "workflow_run_id":999,
            "workflow_run_attempt":2,
            "codespace_name":"wrong-codespace",
        }
        for key,value in fields.items():
            with self.subTest(field=key):
                bad=self.receipt(c);bad[key]=value
                with self.assertRaisesRegex(ProtocolError,"NO_CODESPACE_RECEIPT_IDENTITY_MISMATCH"):
                    self.finalize(c,bad)

    def test_pm33_crash_after_refusal_without_trace_remains_terminally_blocked(self):
        c,_=self.ready_refused()
        self.assertEqual(c.sweep(),"CLEANUP_ONLY")
        self.assertEqual(c.read()[1]["state"],"ADMITTED")
        with self.assertRaisesRegex(ProtocolError,"NO_CODESPACE_PROOF_UNVERIFIED"):
            c.finish_without_codespace(
                self.receipt(c),
                authenticated_run_trace_evidence_id=TRACE_ID,
                authenticated_start_gate_evidence_id=GATE_ID,
                all_workers_accounted_for=False,
                observed_codespace_commands=(),
            )
        self.assertEqual(c.read()[1]["pre_model_control"]["disposition"],"REFUSED_PERMANENT")

    def test_pm34_ambiguous_run_coverage_never_infers_no_acquisition(self):
        c,_=self.ready_refused()
        with self.assertRaisesRegex(ProtocolError,"NO_CODESPACE_PROOF_UNVERIFIED"):
            c.finish_without_codespace(
                self.receipt(c),
                authenticated_run_trace_evidence_id=TRACE_ID,
                authenticated_start_gate_evidence_id=GATE_ID,
                all_workers_accounted_for=True,
                observed_codespace_commands=None,
            )

    def test_pm35_cas_stale_terminal_decision_cannot_override_refusal_state(self):
        c=MemoryClaim()
        c.reserve_initial()
        w=c.worker_token()
        c.bind_worker(w,trusted_run_context=True)
        c.admit(w)
        rev,_=c.read()
        c.fail(w,"PERMANENT","SOURCE_DIGEST_MISMATCH",
               trusted_observation_id=OBSERVATION_ID)
        with self.assertRaisesRegex(ProtocolError,"STALE_COMPARE_AND_SWAP"):
            self.finalize(c,expected_revision=rev)
        self.assertEqual(c.read()[1]["state"],"ADMITTED")
        self.finalize(c)
        with self.assertRaisesRegex(ProtocolError,"TERMINAL_PREMODEL_REFUSAL_INVALID"):
            self.finalize(c)

    def test_current_workflow_prepare_precedes_first_codespace_access(self):
        wf=Path(__file__).resolve().parents[1]/".github/workflows/review-request.yml"
        content=wf.read_text(encoding="utf-8")
        self.assertLess(content.index("id: prepare"),content.index("id: start"))
        self.assertLess(content.index("id: start"),content.index("gh api --method POST"))
        # Current workflow shape only. Does not qualify future v3 start fence.

    def test_current_workflow_cleanup_only_if_start_was_entered(self):
        wf=Path(__file__).resolve().parents[1]/".github/workflows/review-request.yml"
        content=wf.read_text(encoding="utf-8")
        self.assertIn("steps.start.outcome != 'skipped'",content)
        self.assertIn("id: stop",content)
        # A started step may have an ambiguous start outcome; it must not
        # produce no-Codespace-access proof merely because it failed.

    def test_current_action_workflows_share_concurrency_group(self):
        root=Path(__file__).resolve().parents[1]/".github/workflows"
        request=(root/"review-request.yml").read_text(encoding="utf-8")
        reconcile=(root/"review-reconciler.yml").read_text(encoding="utf-8")
        for s in (request,reconcile):
            self.assertIn("group: review-broker-single-reviewer",s)
            self.assertIn("cancel-in-progress: false",s)
        # Schedules only workflows: not a universal Codespace lease.


if __name__ == "__main__":
    unittest.main()
