"""Fixed 450-case diagnostic of exact candidate code; not production CI or a fix."""
from collections import Counter
import gc
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import traceback
import warnings

from linux_process_observation import (
    independent_wait_oracle, process_state, snapshot, wait_for_group_absence,
)

C = '0d0e3764f645edb5014195f67bbddae6ef2a55fe'
SOURCE = 'src/review_broker/actions_artifact_child_v3.py'
TEST = 'tests/test_issue70_live_prep_artifact_child.py'
SOURCE_BLOB = '8921f85af1561b7336bd6031eafb90b9068718af'
TEST_BLOB = '3e463c07e3f0746d460285fff29c87015ae03c4b'
WORKER_BLOB = '670aebe4798401fb6007767d7bbfb2068843c900'
PLAN = {'overflow': 200, 'timeout': 100, 'normal': 100, 'group': 50}
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/rb115-linux-diagnostic'
# Only this exact local source tree supplies the production function.
sys.path.insert(0, str(ROOT / 'src'))
from review_broker.actions_artifact_child_v3 import run_artifact_child_v3


def emit(kind, value):
    print('RB115_' + kind + '=' + json.dumps(value, sort_keys=True), flush=True)


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def tree(ref):
    raw = subprocess.check_output(['git', 'ls-tree', '-r', '-z', ref], cwd=ROOT)
    return {row.split(b'\t', 1)[1].decode(): row.split(b'\t', 1)[0].decode()
            for row in raw.split(b'\0') if row}


def verify_subject():
    if platform.system() != 'Linux' or sys.version_info[:2] != (3, 11):
        raise RuntimeError('REQUIRES_ACTUAL_LINUX_PYTHON311')
    release = platform.freedesktop_os_release()
    if release.get('ID') != 'ubuntu' or release.get('VERSION_ID') != '24.04':
        raise RuntimeError('REQUIRES_ACTUAL_UBUNTU2404')
    head = git('rev-parse', 'HEAD')
    if head != os.environ['EXPECTED_DIAGNOSTIC_SHA']:
        raise RuntimeError('DIAGNOSTIC_HEAD_MISMATCH')
    if git('rev-parse', C + '^{tree}') != '5f7b59fbb97ebafed772b53c3831b68708147e9b':
        raise RuntimeError('CANDIDATE_TREE_MISMATCH')
    for path, oid in ((SOURCE, SOURCE_BLOB), (TEST, TEST_BLOB),
                      ('.github/workflows/v3-pre-model-worker.yml', WORKER_BLOB)):
        if git('hash-object', '--no-filters', path) != oid:
            raise RuntimeError('EXACT_BLOB_MISMATCH:' + path)
    base, current = tree(C), tree(head)
    if any(current.get(path) != entry for path, entry in base.items()):
        raise RuntimeError('PREEXISTING_C_PATH_CHANGED')
    additions = sorted(set(current) - set(base))
    if not additions or any(not (p.startswith('diagnostics/rb115/') or
            p == '.github/workflows/rb115-linux-artifact-child-diagnostic.yml') for p in additions):
        raise RuntimeError('UNAUTHORIZED_DIAGNOSTIC_ADDITION')
    return {'head': head, 'candidate': C, 'source_blob': SOURCE_BLOB,
            'test_blob': TEST_BLOB, 'worker_blob': WORKER_BLOB,
            'preexisting_entries_preserved': len(base), 'additions': additions,
            'uname': list(platform.uname()), 'python': sys.version,
            'os_release': release, 'source_file': run_artifact_child_v3.__code__.co_filename,
            'matrix': PLAN, 'instrumentation': 'line tracing; no mocked process/signal/wait/selector',
            'proc_is_observational': True}


class DiagnosticHang(RuntimeError):
    pass


def experiment(kind, iteration):
    directory = OUT / f'{kind}-{iteration:03d}'
    directory.mkdir(parents=True, mode=0o700)
    log = directory / 'output'
    events, references = [], {}
    record = {'kind': kind, 'iteration': iteration, 'expected': kind,
              'unexpected_process_effects': [], 'warnings': []}

    def note(event, **fields):
        events.append({'event': event, 'time_ns': time.monotonic_ns(), **fields})

    def started(pid):
        references['pid'] = pid
        note('spawn', snapshot=snapshot(pid))

    def trace(frame, action, value):
        if frame.f_code is not run_artifact_child_v3.__code__:
            return None
        process = frame.f_locals.get('process')
        if process is not None:
            references['process'] = process
        if action == 'exception':
            note('source_exception', line=frame.f_lineno,
                 exception=type(value[1]).__name__, message=str(value[1]))
        if action == 'line' and process is not None:
            if frame.f_lineno == 111:
                note('before_killpg', snapshot=snapshot(process.pid), signal='SIGKILL')
            elif frame.f_lineno == 114:
                note('before_cleanup_wait')
            elif frame.f_lineno == 115:
                note('after_cleanup_wait', returncode=process.returncode)
            elif frame.f_lineno == 107:
                note('before_normal_wait')
        return trace

    code = {'normal': "import sys;sys.stdout.write('bounded')",
            'overflow': "import sys;sys.stdout.write('x'*10000)",
            'timeout': 'import time;time.sleep(10)', 'group': ''}[kind]
    if kind == 'group':
        descendant_file = str(directory / 'descendant.json')
        descendant_code = 'import time;time.sleep(10)'
        code = ("import subprocess,sys,os,json,time;"
                f"p=subprocess.Popen([sys.executable,'-c',{descendant_code!r}],"
                "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
                f"open({descendant_file!r},'w').write(json.dumps({{'pid':p.pid,'pgid':os.getpgid(p.pid),'sid':os.getsid(p.pid)}}));"
                "sys.stdout.write('x'*10000);sys.stdout.flush();time.sleep(10)")
    timeout = 0.05 if kind == 'timeout' else 5
    limit = 37 if kind in ('overflow', 'group') else 100
    began = time.monotonic_ns()

    def watchdog(signum, frame):
        raise DiagnosticHang('DIAGNOSTIC_ITERATION_DEADLINE')

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter('always', ResourceWarning)
        previous = signal.signal(signal.SIGALRM, watchdog)
        signal.setitimer(signal.ITIMER_REAL, 15, 5)
        try:
            sys.settrace(trace)
            value = run_artifact_child_v3([sys.executable, '-c', code], {}, log,
                                          timeout=timeout, max_log_bytes=limit, on_started=started)
            result = {'class': 'return', 'value': value}
        except BaseException as exc:
            result = {'class': type(exc).__name__, 'message': str(exc),
                      'traceback': ''.join(traceback.format_exception(exc))}
        finally:
            sys.settrace(None)
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
        record['duration_ns'] = time.monotonic_ns() - began
        record['result'] = result
        pid, process = references.get('pid'), references.get('process')
        if pid is None or process is None:
            record['qualification_pass'] = False
            record['harness_error'] = 'NO_PROCESS_REFERENCE'
            record['events'] = events
            return record
        record['leader_pid'] = pid
        record['after_return'] = snapshot(pid)
        record['cached_returncode'] = process.returncode
        record['stdout_closed'] = process.stdout.closed
        record['wait_oracle'] = independent_wait_oracle(pid)
        record['group_observations'] = wait_for_group_absence(pid)
        record['final_group'] = record['group_observations'][-1]['group']
        record['output_bytes'] = log.stat().st_size
        record['output_bound_pass'] = record['output_bytes'] == limit if kind in ('overflow', 'group') else record['output_bytes'] <= limit
        descendant = directory / 'descendant.json'
        if descendant.exists():
            record['descendant'] = json.loads(descendant.read_text())
            record['descendant_after'] = process_state(record['descendant']['pid'])
        elif kind == 'group':
            record['harness_error'] = 'MISSING_DESCENDANT_IDENTITY'
        record['events'] = events
        # Keep Popen alive through return observation; destructor polling cannot mask missing wait.
        record['warnings'] = [str(w.message) for w in captured]
        expected_class = {'normal': 'return', 'timeout': 'TimeoutError',
                          'overflow': 'ValueError', 'group': 'ValueError'}[kind]
        expected_message = 'ARTIFACT_CHILD_TIMEOUT' if kind == 'timeout' else 'ARTIFACT_CHILD_OUTPUT_BUDGET'
        expected = result['class'] == expected_class
        if kind == 'normal':
            expected = expected and result.get('value') == 0 and log.read_bytes() == b'bounded'
        else:
            expected = expected and result.get('message') == expected_message
        own_members = {pid}
        if 'descendant' in record:
            own_members.add(record['descendant']['pid'])
            expected = expected and record['descendant']['pgid'] == pid and record['descendant']['sid'] == pid
        signal_events = [x for x in events if x['event'] == 'before_killpg']
        for item in signal_events:
            for member in item['snapshot']['group']:
                if member['pid'] not in own_members:
                    record['unexpected_process_effects'].append(member)
        record['killpg_outcome'] = ('not_called' if not signal_events else
            'PermissionError' if any(x.get('exception') == 'PermissionError' and x.get('line') == 111 for x in events) else
            'ProcessLookupError' if any(x.get('exception') == 'ProcessLookupError' and x.get('line') == 111 for x in events) else 'returned')
        record['expected_result'] = expected
        record['qualification_pass'] = bool(expected and record['output_bound_pass'] and
            record['wait_oracle']['reaped_by_runner'] and record['cached_returncode'] is not None and
            record['after_return']['leader'] is None and not record['final_group'] and
            record.get('descendant_after') is None and not record.get('harness_error') and
            record['stdout_closed'] and not record['warnings'] and not record['unexpected_process_effects'] and
            (kind != 'normal' or not signal_events))
        # Rescue only after a failure has been irrevocably recorded. Never turns failure into PASS.
        if record['wait_oracle'].get('waitpid') == [0, 0]:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
            process.poll()
            record['external_rescue'] = 'owned-direct-child-only'
        del references['process']
        del process
        gc.collect()
        record['warnings'] = [str(w.message) for w in captured]
        record['qualification_pass'] = record['qualification_pass'] and not record['warnings']
    return record


def main():
    subject = verify_subject()
    OUT.mkdir(parents=True, exist_ok=True, mode=0o700)
    emit('SUBJECT_JSON', subject)
    emit('PLAN_JSON', PLAN)
    records = []
    with (OUT / 'iterations.jsonl').open('x') as output:
        for kind, count in PLAN.items():
            for iteration in range(count):
                record = experiment(kind, iteration)
                records.append(record)
                raw = json.dumps(record, sort_keys=True)
                output.write(raw + '\n')
                output.flush()
                emit('ITERATION_JSON', record)
    summary = {'subject': subject, 'cases': {}, 'unreaped_children': 0,
               'surviving_groups': 0, 'resourcewarnings': 0, 'hangs': 0,
               'unrelated_process_signals': 0, 'qualification_pass': False}
    for kind in PLAN:
        subset = [r for r in records if r['kind'] == kind]
        summary['cases'][kind] = {'repetitions': len(subset),
            'expected': sum(r.get('expected_result', False) for r in subset),
            'pass': sum(r['qualification_pass'] for r in subset),
            'permission_errors': sum(r['result']['class'] == 'PermissionError' for r in subset),
            'other_errors': sum(not r['qualification_pass'] and r['result']['class'] != 'PermissionError' for r in subset),
            'result_classes': dict(Counter(r['result']['class'] for r in subset))}
    summary['unreaped_children'] = sum(not r.get('wait_oracle', {}).get('reaped_by_runner', False) for r in records)
    summary['surviving_groups'] = sum(bool(r.get('final_group', [None])) for r in records)
    summary['resourcewarnings'] = sum(len(r['warnings']) for r in records)
    summary['hangs'] = sum(r['result']['class'] == 'DiagnosticHang' for r in records)
    summary['unrelated_process_signals'] = sum(bool(r['unexpected_process_effects']) for r in records)
    summary['qualification_pass'] = all(r['qualification_pass'] for r in records) and len(records) == 450
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    emit('SUMMARY_JSON', summary)
    return 0 if summary['qualification_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
