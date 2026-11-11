"""External process-service shim: real timeout and termination, no consumer Git network."""
import subprocess
import sys


class SimulatedTransferProcess:
    def __init__(self, arguments, record, *, timeout=True):
        self.args, self.record, self.timeout = list(arguments), record, timeout
        code = 'import time; time.sleep(20)' if timeout else 'raise SystemExit(7)'
        # The injected process backend implements the requested clone/fetch as an
        # inert service process. Production _run still performs real communicate,
        # TimeoutExpired handling, process-group kill, reap and termination checks.
        self.delegate = subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,
            env={'LANG':'C','PYTHONDONTWRITEBYTECODE':'1'})
        self.pid,self.stdout,self.stderr = self.delegate.pid,self.delegate.stdout,self.delegate.stderr

    @property
    def returncode(self):return self.delegate.returncode

    def poll(self):return self.delegate.poll()
    def kill(self):return self.delegate.kill()

    def communicate(self, timeout=None):
        bound=0.02 if self.timeout and timeout is not None and not self.record['timed_out'] else timeout
        try:return self.delegate.communicate(timeout=bound)
        except subprocess.TimeoutExpired:
            self.record['timed_out']=True
            raise subprocess.TimeoutExpired(self.args,timeout) from None


class TransferService:
    def __init__(self, scenario, *, operation='GIT_FETCH', timeout=True):
        import review_broker.github_subject_capture_v3 as module
        self.original=module._popen
        self.scenario,self.operation,self.timeout=scenario,operation,timeout
        self.processes=[]

    def __call__(self, arguments, **kwargs):
        s=self.scenario
        clone=arguments[:3]==['gh','repo','clone']
        fetch=len(arguments)>4 and arguments[0]=='git' and arguments[3]=='fetch'
        selected=clone if self.operation=='GIT_CLONE' else fetch
        if not selected:return self.original(arguments,**kwargs)
        admitted=s.real.worker.admission.request['subject']['repository']
        if clone:
            assert arguments[3]=='https://github.com/'+admitted+'.git'
        else:
            assert arguments[2]==str(s.worker_root/'continued-source/source.git')
            assert arguments[4]=='origin'
        record=dict(phase='SOURCE_ACQUISITION',operation=self.operation,target=admitted,
            reference_id=None,artifact_id=None,fact={'kind':'TRANSFER_TIMEOUT','process_terminated':True},
            arguments=tuple(arguments),timed_out=False)
        process=SimulatedTransferProcess(arguments,record,timeout=self.timeout)
        record['process']=process;s.authority.records.append(record);self.processes.append(process)
        return process

    def close(self):
        for process in self.processes:
            if process.poll() is None:process.kill()
            process.delegate.communicate()
