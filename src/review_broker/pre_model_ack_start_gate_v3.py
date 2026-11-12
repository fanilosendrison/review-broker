"""Bounded observer-only wait before Worker source mint and original process startup."""
from dataclasses import dataclass
import time

from .github_actions_worker_authority_v3 import valid_worker_inputs
from .pre_model_dispatch_ack_v3 import acknowledgment_from_record

MAX_ACK_OBSERVATION_ATTEMPTS=30
ACK_OBSERVATION_INTERVAL_SECONDS=2


@dataclass(frozen=True)
class AckStartGateResultV3:
    accepted: bool
    reason: str
    principal_id: int | None = None


def wait_dispatch_ack_v3(*,journal,runtime,inputs,dispatch_authority,sleeper=time.sleep):
    if not valid_worker_inputs(inputs):return AckStartGateResultV3(False,'WORKER_INPUTS_INVALID')
    for index in range(MAX_ACK_OBSERVATION_ATTEMPTS):
        try:
            runtime.observe()
            current=journal.read(inputs.request_id);control=current.record.control
            if (current.record.attempt.state.value!='REQUESTED' or control.generation!=1
                    or control.reservation_id!=inputs.reservation_id or control.worker is not None
                    or control.disposition!='RESERVED'):
                return AckStartGateResultV3(False,'ACK_GATE_STALE_OR_UNBOUND')
            receipt=acknowledgment_from_record(current.record)
            if receipt is not None:
                e=runtime.expected
                if (receipt.workflow_run_id!=runtime.claim.run_id
                        or receipt.execution_ref!=e.workflow_execution_ref
                        or receipt.executable_sha!=e.executing_source_sha
                        or receipt.worker_workflow_path!=e.workflow_path
                        or receipt.reservation_id!=inputs.reservation_id or receipt.generation!=inputs.generation):
                    return AckStartGateResultV3(False,'ACK_GATE_MISMATCH')
                principal=dispatch_authority.principal_id(receipt)
                observed=runtime.observe()
                if observed.actor_id!=principal or observed.triggering_actor_id!=principal:
                    return AckStartGateResultV3(False,'ACK_GATE_PRINCIPAL_MISMATCH')
                return AckStartGateResultV3(True,'ACK_GATE_ACCEPTED',principal)
        except Exception:
            pass  # Only bounded reads, never binding, source reads, tickets or retry effects.
        if index+1<MAX_ACK_OBSERVATION_ATTEMPTS:sleeper(ACK_OBSERVATION_INTERVAL_SECONDS)
    return AckStartGateResultV3(False,'ACK_GATE_OBSERVATION_BUDGET_EXHAUSTED')
