"""Read-only Linux lifecycle observations for the temporary #115 qualification."""
from pathlib import Path
import os
import time


def process_state(pid):
    """Read one coherent /proc stat identity; disappearance is not a wait proof."""
    try:
        raw = (Path('/proc') / str(pid) / 'stat').read_text()
    except (FileNotFoundError, ProcessLookupError):
        return None
    suffix = raw[raw.rindex(')') + 2:].split()
    return {'pid': pid, 'state': suffix[0], 'ppid': int(suffix[1]),
            'pgid': int(suffix[2]), 'sid': int(suffix[3]),
            'start_ticks': int(suffix[19])}


def group_members(pgid):
    result = []
    for path in Path('/proc').iterdir():
        if path.name.isdecimal():
            state = process_state(int(path.name))
            if state is not None and state['pgid'] == pgid:
                result.append(state)
    return sorted(result, key=lambda row: row['pid'])


def snapshot(pid):
    return {'time_ns': time.monotonic_ns(), 'leader': process_state(pid),
            'group': group_members(pid)}


def independent_wait_oracle(pid):
    """Any waitable child is a failure, even if this oracle subsequently reaps it."""
    try:
        child, status = os.waitpid(pid, os.WNOHANG)
        return {'reaped_by_runner': False, 'waitpid': [child, status],
                'oracle_reaped_child': child == pid}
    except ChildProcessError:
        return {'reaped_by_runner': True, 'waitpid': 'ECHILD',
                'oracle_reaped_child': False}


def wait_for_group_absence(pgid, timeout=2):
    """Bounded observation only, never a cleanup signal or descendant reap."""
    deadline = time.monotonic() + timeout
    observations = []
    while True:
        state = snapshot(pgid)
        observations.append(state)
        if not state['group'] or time.monotonic() >= deadline:
            return observations
        time.sleep(0.01)
