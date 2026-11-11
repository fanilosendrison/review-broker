"""Pure ADMITTED/RESERVED generation-one failure-decision domain."""
from .queue import AttemptState


def require_preparation_open_control_v3(record) -> None:
    """Failed control never authorizes new preparation, including legacy helpers."""
    if record.control.disposition != "RESERVED" or record.control.failure_receipt_id is not None:
        raise ValueError("PREPARATION_RESERVED_CONTROL_REQUIRED")


def require_failure_predecessor_v3(record) -> None:
    require_preparation_open_control_v3(record)
    attempt, control = record.attempt, record.control
    if (attempt.state is not AttemptState.ADMITTED or attempt.invocation_count != 0
            or type(control.generation) is not int or control.generation != 1
            or control.worker is None or control.worker.run_attempt != 1
            or any(e.get("state") in {"PREPARED", "ARMED"} or e.get("event") == "PRE_MODEL_FAILURE"
                   for e in attempt.history)):
        raise ValueError("ORIGINAL_ADMITTED_DECISION_DOMAIN_REQUIRED")
