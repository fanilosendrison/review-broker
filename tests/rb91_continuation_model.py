"""Bounded explicit-state research for D05/D06, not an OS/protocol proof."""
from collections import deque
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class State:
    # Model begins at the single already-committed AtomicArm, count1.
    controller: bool = True
    ack: str = 'pending'
    proof: bool = False
    launcher: str = 'waiting'
    reconciler: str = 'idle'
    cancel: str = 'none'
    shutdown: bool = False
    journal: str = 'ARMED'
    starts: int = 0
    late: bool = False
    clone: bool = False
    checked: bool = False


def successors(s, mode):
    def edge(name, **changes):
        return name, replace(s, **changes)
    if s.controller:
        yield edge('controller-dies', controller=False)
        if s.ack == 'pending':
            yield edge('clean-ACK-and-exact-readback', ack='verified')
            yield edge('ACK-lost', ack='lost')
        if s.ack == 'verified' and not s.proof and s.reconciler == 'idle':
            yield edge('proof-in-transit', proof=True)
    if s.proof and s.launcher == 'waiting' and not s.shutdown:
        yield edge('original-launcher-receives-proof', launcher='ready')
    if s.launcher == 'ready' and not s.shutdown:
        yield edge('one-shot-claim', launcher='claimed')
    if s.launcher in {'waiting', 'ready', 'claimed', 'running'}:
        yield edge('launcher-crashes-or-SSH-abort', launcher='dead')
    if not s.controller and s.reconciler == 'idle':
        yield edge('reconciler-begins', reconciler='active')
    if s.reconciler == 'active':
        if s.cancel == 'none':
            yield edge('cancel-in-transit', cancel='sent')
        if s.cancel == 'sent' and s.launcher != 'running':
            yield edge('protected-cancel-fences-before-spawn', cancel='fenced', launcher='dead')
        if not s.shutdown:
            yield edge('observe-actual-Shutdown', shutdown=True, launcher='dead', clone=False)
        can_terminal = mode in {'mark_first', 'cancel_only', 'read_before_start'}
        if mode == 'cancel_only':
            can_terminal = s.cancel != 'none'
        if mode in {'stop_first', 'clone', 'reenter'}:
            can_terminal = s.shutdown
        if s.journal == 'ARMED' and can_terminal:
            yield edge('commit-INDETERMINATE', journal='INDETERMINATE')
        if s.journal == 'INDETERMINATE' and s.shutdown:
            yield edge('record-STOPPED', journal='STOPPED', reconciler='done')
    if mode == 'read_before_start' and s.launcher == 'claimed' and s.journal == 'ARMED':
        yield edge('fresh-head-check', checked=True)
    if s.launcher == 'claimed' and not s.shutdown and s.starts < 2:
        if mode != 'read_before_start' or s.checked:
            yield edge('first-child-start', launcher='running', starts=s.starts+1,
                       late=s.late or s.journal != 'ARMED')
        if mode == 'clone' and not s.clone:
            yield edge('FAULT-copy-authorized-process', clone=True)
    if mode == 'clone' and s.clone and not s.shutdown and s.starts < 2:
        yield edge('copied-process-start', clone=False, starts=s.starts+1,
                   late=s.late or s.journal != 'ARMED')
    if mode == 'reenter' and s.launcher == 'running' and not s.shutdown and s.starts < 2:
        yield edge('FAULT-reenter-start-call', starts=s.starts+1)


def explore(mode):
    initial = State()
    pending = deque([initial])
    paths = {initial: ()}
    edges = 0
    while pending:
        state = pending.popleft()
        for event, child in successors(state, mode):
            edges += 1
            if child not in paths:
                paths[child] = paths[state] + (event,)
                pending.append(child)
    def witness(predicate):
        matches = [s for s in paths if predicate(s)]
        return list(min((paths[s] for s in matches), key=len)) if matches else None
    return dict(mode=mode, states=len(paths), edges=edges,
        double_start=witness(lambda s:s.starts > 1),
        late_start=witness(lambda s:s.late),
        launch_reachable=any(s.starts == 1 for s in paths),
        stopped_reachable=any(s.journal == 'STOPPED' for s in paths),
        lost_ack_start=any(s.ack == 'lost' and s.starts for s in paths),
        stop_without_shutdown=any(s.journal == 'STOPPED' and not s.shutdown for s in paths),
        start_during_cancel=any(s.starts and s.cancel == 'sent' and not s.shutdown for s in paths))
