"""PM01-PM25 against an isolated, UNACCEPTED reference state engine.

This is NOT a test of live v3. No network, actual Codespace or model calls.
External actor, workflow and resource-owner evidence is simulated.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import threading
import unittest

from review_broker.evidence import build_shutdown_observation
from review_broker.identity import canonical_bytes
from review_broker.queue import AttemptRecord, AttemptState
from tests.reference_pre_model_v3 import (
    CODESPACE_NAME, FIXED_NOW, OBSERVATION_ID, PACKET_ID, REQUEST_HEX,
    MemoryClaim, ProtocolError, dispatch_id, failure_id, identity,
    recovery_id, strict_decode_v2, validate_record,
)


class PreModelV3ReferenceTests(unittest.TestCase):
    def ready(self):
        claim=MemoryClaim()
        claim.reserve_initial()
        worker=claim.worker_token()
        claim.bind_worker(worker,trusted_run_context=True)
        claim.admit(worker)
        return claim,worker

    def failure(self,c,w,classification="PERMANENT",code="SOURCE_DIGEST_MISMATCH"):
        return c.fail(w,classification,code,trusted_observation_id=OBSERVATION_ID)

    def auth(self,c,nonce="1"*32, actor=12345):
        _,r=c.read()
        k=r["pre_model_control"]
        return {
            "schema_version":1,"evidence_type":"pre-model-recovery-authorization",
            "request_id":r["request_id"],"attempt_id":r["attempt_id"],
            "previous_generation":k["generation"],
            "previous_reservation_id":k["reservation_id"],
            "authorization_nonce":nonce,"actor_github_id":actor,
            "prior_run_observation_id":OBSERVATION_ID,"authorized_at":FIXED_NOW,
        }

    def recover(self,c,auth):
        return c.recover(auth,trusted_actor_id=auth["actor_github_id"],
                         observed_quiescent=True,
                         trusted_run_observation_id=OBSERVATION_ID)

    def shutdown(self,c,codespace=CODESPACE_NAME,aid=None):
        _,r=c.read()
        return build_shutdown_observation(
            codespace_name=codespace,request_id=r["request_id"],
            attempt_id=aid or r["attempt_id"],observed_state="Shutdown",
            context={"workflow_run_id":"synthetic","workflow_run_attempt":"1"},
            observed_at=FIXED_NOW,
        )

    def finalize_no_access(self, c):
        """Injected trusted workflow evidence; never an actual run attestation."""
        _, r = c.read()
        info = r["pre_model_control"]
        worker = info["worker"]
        trace = "artifact:sha256:" + "4" * 64
        start_gate = "artifact:sha256:" + "5" * 64
        receipt = {
            "schema_version": 1,
            "evidence_type": "pre-model-no-codespace-access",
            "request_id": r["request_id"],
            "attempt_id": r["attempt_id"],
            "admission_evidence_id": c.admission_id,
            "generation": info["generation"],
            "reservation_id": info["reservation_id"],
            "workflow_run_id": worker["run_id"],
            "workflow_run_attempt": worker["run_attempt"],
            "codespace_name": CODESPACE_NAME,
            "workflow_trace_evidence_id": trace,
            "start_gate_evidence_id": start_gate,
            "codespace_access_attempted": False,
            "observed_at": FIXED_NOW,
        }
        return c.finish_without_codespace(
            receipt,
            authenticated_run_trace_evidence_id=trace,
            authenticated_start_gate_evidence_id=start_gate,
            all_workers_accounted_for=True,
            observed_codespace_commands=(),
        )

    def test_pm01_one_initial_automatic_reservation(self):
        c=MemoryClaim()
        results=[c.sweep() for _ in range(4)]
        self.assertEqual(results.count("DISPATCH_RESERVED_ONCE"),1)
        self.assertEqual(c.read()[1]["pre_model_control"]["generation"],1)

    def test_pm02_two_controllers_compete_in_one_cas(self):
        c=MemoryClaim()
        barrier=threading.Barrier(2)
        def run(_):
            barrier.wait()
            try:
                c.reserve_initial()
                return "WON"
            except ProtocolError:
                return "LOST"
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcome=list(pool.map(run,range(2)))
        self.assertEqual(sorted(outcome),["LOST","WON"])

    def test_pm03_dispatch_response_lost_does_not_resend(self):
        c=MemoryClaim()
        c.reserve_initial()
        previous=c.read()[0]
        self.assertEqual(c.sweep(),"AWAIT_EXPLICIT_OBSERVATION_OR_RECOVERY")
        with self.assertRaisesRegex(ProtocolError,"AUTO_DISPATCH_ALREADY_RESERVED"):
            c.reserve_initial()
        self.assertEqual(c.read()[0],previous)

    def test_pm04_previous_generation_cannot_prepare_after_recovery(self):
        c,old=self.ready()
        self.failure(c,old,"TRANSIENT","SOURCE_TRANSFER_FAILURE")
        self.recover(c,self.auth(c))
        with self.assertRaisesRegex(ProtocolError,"WORKER_FENCE_REJECTED"):
            c.prepare(old)
        newer=c.worker_token(run_id=124)
        c.bind_worker(newer,trusted_run_context=True)
        c.prepare(newer)
        self.assertEqual(c.read()[1]["state"],"PREPARED")

    def test_pm05_inflight_read_not_retroactively_undone_but_new_work_blocked(self):
        c,w=self.ready()
        c.can_fetch(w)
        self.failure(c,w)
        with self.assertRaisesRegex(ProtocolError,"WORKER_FENCE_REJECTED"):
            c.can_fetch(w)
        with self.assertRaisesRegex(ProtocolError,"WORKER_FENCE_REJECTED"):
            c.prepare(w)

    def test_pm06_prepared_vs_refused_conflict_only_one_cas_winner(self):
        c,w=self.ready()
        rev,_=c.read()
        b=threading.Barrier(2)
        def run(choice):
            b.wait()
            try:
                if choice=="P":
                    c.prepare(w,expected_revision=rev)
                else:
                    c.fail(w,"PERMANENT","SOURCE_DIGEST_MISMATCH",
                           trusted_observation_id=OBSERVATION_ID,
                           expected_revision=rev)
                return "WON"
            except ProtocolError:
                return "LOST"
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(run,["P","F"]))
        self.assertEqual(sorted(outcomes),["LOST","WON"])
        _,r=c.read()
        self.assertIn((r["state"],r["pre_model_control"]["disposition"]),
                      {("PREPARED","RESERVED"),("ADMITTED","REFUSED_PERMANENT")})

    def test_pm07_refused_crash_before_cleanup_only_stays_blocked(self):
        c,w=self.ready()
        self.failure(c,w)
        self.assertEqual(c.sweep(),"CLEANUP_ONLY")
        with self.assertRaisesRegex(ProtocolError,"RESOURCE_OWNERSHIP_UNVERIFIED"):
            c.stop_permanent(self.shutdown(c))
        self.assertEqual(c.read()[1]["state"],"ADMITTED")

    def test_pm08_wrong_shutdown_or_attempt_never_stopped(self):
        c,w=self.ready()
        self.failure(c,w)
        with self.assertRaisesRegex(ProtocolError,"CODESPACE_IDENTITY_MISMATCH"):
            c.stop_permanent(self.shutdown(c,codespace="another"),
                             trusted_resource_observation=True)
        with self.assertRaisesRegex(ProtocolError,"SHUTDOWN_RECEIPT_INVALID"):
            c.stop_permanent(self.shutdown(c,aid="attempt:sha256:"+"f"*64),
                             trusted_resource_observation=True)
        self.assertEqual(c.read()[1]["state"],"ADMITTED")

    def test_pm09_refused_prepared_never_acquired_codespace_terminal_without_shutdown(self):
        c,w=self.ready()
        self.failure(c,w)
        r=self.finalize_no_access(c)
        self.assertEqual(r["state"],"STOPPED")
        self.assertEqual(r["invocation_count"],0)
        self.assertEqual(r["history"][-1]["receipt"]["evidence_type"],
                         "pre-model-no-codespace-access")
        self.assertFalse(any(e["kind"]=="ARMED" for e in r["history"]))

    def test_pm10_transient_explicit_recovery_generates_one_new_reservation(self):
        c,w=self.ready()
        self.failure(c,w,"TRANSIENT","SOURCE_TRANSFER_FAILURE")
        r=self.recover(c,self.auth(c))
        k=r["pre_model_control"]
        self.assertEqual(k["generation"],2)
        self.assertEqual(k["disposition"],"RESERVED")
        self.assertIsNone(k["worker"])
        self.assertIsNone(k["failure_receipt_id"])
        self.assertEqual(c.sweep(),"AWAIT_EXPLICIT_OBSERVATION_OR_RECOVERY")

    def test_pm11_ambiguous_permission_never_counts_as_absent(self):
        c,w=self.ready()
        self.failure(c,w,"UNKNOWN","API_OBSERVATION_UNKNOWN")
        self.assertEqual(c.read()[1]["pre_model_control"]["disposition"],"BLOCKED")
        self.assertEqual(c.sweep(),"AWAIT_EXPLICIT_OBSERVATION_OR_RECOVERY")

    def test_pm12_crash_before_failure_cas_leaves_reserved_ambiguity(self):
        c=MemoryClaim()
        c.reserve_initial()
        self.assertEqual(c.sweep(),"AWAIT_EXPLICIT_OBSERVATION_OR_RECOVERY")
        self.assertIsNone(c.read()[1]["pre_model_control"]["failure_receipt_id"])

    def test_pm13_double_worker_binding_rejects_second(self):
        c=MemoryClaim()
        c.reserve_initial()
        one=c.worker_token(run_id=123)
        two=c.worker_token(run_id=124)
        c.bind_worker(one,trusted_run_context=True)
        with self.assertRaisesRegex(ProtocolError,"WORKER_BINDING_CONFLICT"):
            c.bind_worker(two,trusted_run_context=True)
        self.assertEqual(c.read()[1]["pre_model_control"]["worker"],
                         {"run_id":123,"run_attempt":1})

    def test_pm14_prepared_packet_unrefreshable(self):
        c,w=self.ready()
        c.prepare(w)
        initial=c.encode()
        with self.assertRaisesRegex(ProtocolError,"PREPARED_BOUNDARY_BLOCKED"):
            c.prepare(w,"artifact:sha256:"+"b"*64)
        with self.assertRaisesRegex(ProtocolError,"RECOVERY_AFTER_PREPARED_OR_ARMED"):
            self.recover(c,self.auth(c))
        self.assertEqual(c.encode(),initial)

    def test_pm15_armed_durable_one_invocation_no_retry(self):
        c,w=self.ready()
        c.prepare(w)
        c.arm(w)
        with self.assertRaisesRegex(ProtocolError,"MODEL_INVOCATION_ALREADY_RESERVED"):
            c.arm(w)
        self.assertEqual(c.read()[1]["invocation_count"],1)

    def test_pm16_stale_recovery_nonce_actor_and_predecessor(self):
        c,w=self.ready()
        self.failure(c,w,"TRANSIENT","SOURCE_TRANSFER_FAILURE")
        a=self.auth(c)
        with self.assertRaisesRegex(ProtocolError,"RECOVERY_AUTHORITY_OR_QUIESCENCE_UNVERIFIED"):
            c.recover(a,trusted_actor_id=999,observed_quiescent=True,
                      trusted_run_observation_id=OBSERVATION_ID)
        self.recover(c,a)
        with self.assertRaisesRegex(ProtocolError,"RECOVERY_PREDECESSOR_MISMATCH"):
            self.recover(c,a)

    def test_pm17_historical_v1_serialization_unchanged(self):
        c=MemoryClaim()
        _,r=c.read()
        original=AttemptRecord(
            request_id=REQUEST_HEX,attempt_id=r["attempt_id"],
            state=AttemptState.REQUESTED,
            history=({"state":"REQUESTED","evidence_ids":[]},),
        ).as_dict()
        self.assertEqual(AttemptRecord.from_dict(deepcopy(original)).as_dict(),original)
        with self.assertRaisesRegex(ProtocolError,"SCHEMA_JOURNAL_INVALID"):
            strict_decode_v2(canonical_bytes(original)+b"\n")

    def test_pm18_malformed_or_secret_bearing_receipt_is_refused(self):
        c,w=self.ready()
        with self.assertRaisesRegex(ProtocolError,"SCHEMA_FAILURE_INVALID"):
            c.fail(w,"PERMANENT","ghp_RAW_SECRET",
                   trusted_observation_id=OBSERVATION_ID)
        self.assertEqual(c.read()[1]["pre_model_control"]["disposition"],"RESERVED")
        a=self.auth(c)
        with self.assertRaisesRegex(ProtocolError,"SCHEMA_RECOVERY_INVALID"):
            recovery_id({**a,"extra":"secret"})

    def test_pm19_replayed_issue_after_terminal_refusal_does_not_dispatch(self):
        c,w=self.ready()
        self.failure(c,w)
        self.finalize_no_access(c)
        self.assertEqual(c.sweep(),"NO_ACTION")
        with self.assertRaisesRegex(ProtocolError,"AUTO_DISPATCH_ALREADY_RESERVED"):
            c.reserve_initial()

    def test_pm20_ambiguous_cas_ack_requires_readback(self):
        c=MemoryClaim()
        c.reserve_initial()
        revision,record=c.read()
        self.assertEqual(record["pre_model_control"]["generation"],1)
        with self.assertRaisesRegex(ProtocolError,"AUTO_DISPATCH_ALREADY_RESERVED"):
            c.reserve_initial()
        self.assertEqual(c.read()[0],revision)

    def test_pm21_decoder_strict_v2_v1_and_extra_field(self):
        c=MemoryClaim()
        self.assertEqual(strict_decode_v2(c.encode()),c.read()[1])
        record=c.read()[1]
        v1=deepcopy(record);v1["schema_version"]=1
        with self.assertRaisesRegex(ProtocolError,"SCHEMA_JOURNAL_INVALID"):
            strict_decode_v2(canonical_bytes(v1)+b"\n")
        extra=deepcopy(record);extra["pre_model_control"]["future"]=True
        with self.assertRaisesRegex(ProtocolError,"SCHEMA_JOURNAL_INVALID"):
            strict_decode_v2(canonical_bytes(extra)+b"\n")

    def test_pm22_cross_request_codespace_owner_not_stopped_by_nonacquiring_A(self):
        c,w=self.ready()
        self.failure(c,w)
        other={"request_id":"request:sha256:"+"f"*64,
               "attempt_id":"attempt:sha256:"+"f"*64,
               "generation":1,"worker":{"run_id":456,"run_attempt":1}}
        with self.assertRaisesRegex(ProtocolError,"CROSS_REQUEST_CODESPACE_OWNER_MISMATCH"):
            c.stop_permanent(self.shutdown(c),observed_owner=other,
                             trusted_resource_observation=True)
        # A's positive terminal outcome does not require stopping B.
        outcome=self.finalize_no_access(c)
        self.assertEqual(outcome["state"],"STOPPED")
        self.assertEqual(outcome["history"][-1]["receipt"]["evidence_type"],
                         "pre-model-no-codespace-access")

    def test_pm23_issue_event_and_reconciler_one_reservation_controller(self):
        c=MemoryClaim()
        barrier=threading.Barrier(2)
        def run(_):
            barrier.wait()
            return c.sweep()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(run,["EVENT","RECONCILER"]))
        self.assertEqual(outcomes.count("DISPATCH_RESERVED_ONCE"),1)

    def test_pm24_worker_generation_fence_checked_in_commit_cas(self):
        c,w=self.ready()
        oldrev,_=c.read()
        self.failure(c,w)
        with self.assertRaisesRegex(ProtocolError,"STALE_COMPARE_AND_SWAP"):
            c.prepare(w,expected_revision=oldrev)
        with self.assertRaisesRegex(ProtocolError,"WORKER_FENCE_REJECTED"):
            c.prepare(w)

    def test_pm25_recovery_resets_current_fields_and_preserves_history(self):
        c,w=self.ready()
        self.failure(c,w,"TRANSIENT","SOURCE_TRANSFER_FAILURE")
        before=c.read()[1]
        self.recover(c,self.auth(c))
        after=c.read()[1]
        self.assertIsNone(after["pre_model_control"]["worker"])
        self.assertIsNone(after["pre_model_control"]["failure_receipt_id"])
        self.assertGreater(len(after["history"]),len(before["history"]))
        self.assertTrue(any(e["kind"]=="PREMODEL_FAILED" for e in after["history"]))

    def test_schema_journal_is_closed_and_rejects_bool_as_int(self):
        _,r=MemoryClaim().read()
        for key,val in [("schema_version",3),("future",None),("invocation_count",True)]:
            with self.subTest(key=key):
                bad=deepcopy(r);bad[key]=val
                with self.assertRaisesRegex(ProtocolError,"SCHEMA_JOURNAL_INVALID"):
                    validate_record(bad)

    def test_schema_failure_reason_class_must_match(self):
        c,w=self.ready()
        with self.assertRaisesRegex(ProtocolError,"SCHEMA_FAILURE_INVALID"):
            c.fail(w,"PERMANENT","SOURCE_TRANSFER_FAILURE",
                   trusted_observation_id=OBSERVATION_ID)

    def test_schema_observation_requires_external_trust(self):
        c,w=self.ready()
        with self.assertRaisesRegex(ProtocolError,"FAILURE_OBSERVATION_UNVERIFIED"):
            c.fail(w,"PERMANENT","SOURCE_DIGEST_MISMATCH")

    def test_schema_recovery_requires_verified_quiescence(self):
        c,w=self.ready()
        self.failure(c,w,"TRANSIENT","SOURCE_TRANSFER_FAILURE")
        a=self.auth(c)
        with self.assertRaisesRegex(ProtocolError,"RECOVERY_AUTHORITY_OR_QUIESCENCE_UNVERIFIED"):
            c.recover(a,trusted_actor_id=a["actor_github_id"],
                      observed_quiescent=False,
                      trusted_run_observation_id=OBSERVATION_ID)

    def test_schema_unicode_canonical_jcs_and_id_domain(self):
        x={"é":"𝄞","B":"€"};y={"B":"€","é":"𝄞"}
        self.assertEqual(canonical_bytes(x),canonical_bytes(y))
        self.assertEqual(identity("test",x),identity("test",y))

    def test_schema_workflow_cannot_bind_from_untrusted_caller(self):
        c=MemoryClaim();c.reserve_initial()
        with self.assertRaisesRegex(ProtocolError,"WORKFLOW_RUN_AUTHORITY_UNVERIFIED"):
            c.bind_worker(c.worker_token())

    def test_schema_failure_receipt_content_tamper_detected(self):
        c,w=self.ready();self.failure(c,w)
        r=c.read()[1]
        for e in r["history"]:
            if e["kind"]=="PREMODEL_FAILED":
                e["receipt"]["reason_code"]="UNSUPPORTED_KIND"
        with self.assertRaisesRegex(ProtocolError,"FAILURE_EVIDENCE_MISSING_OR_TAMPERED"):
            validate_record(r)

    def test_schema_armed_requires_one_invocation(self):
        c,w=self.ready();c.prepare(w);c.arm(w)
        r=c.read()[1];r["invocation_count"]=0
        with self.assertRaisesRegex(ProtocolError,"SCHEMA_JOURNAL_INVALID"):
            validate_record(r)

    def test_schema_reservation_identity_deterministic(self):
        c=MemoryClaim()
        _,r=c.read();c.reserve_initial()
        k=c.read()[1]["pre_model_control"]
        self.assertEqual(k["reservation_id"],
                         dispatch_id(r["request_id"],r["attempt_id"],1,r["request_id"]))


if __name__=="__main__":
    unittest.main()
