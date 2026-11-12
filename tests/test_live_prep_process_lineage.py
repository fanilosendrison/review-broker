"""Actual provider-child parentage and metadata-Git environment, without an upload."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from review_broker.actions_artifact_child_v3 import (
    run_artifact_child_v3,verify_upload_helper_v3,UPLOAD_ACTION_COMMIT,UPLOAD_ACTION_DIST_BLOB,
)


class ProcessLineageTests(unittest.TestCase):
    def test_LP02_13_actual_helper_supervisor_keeps_original_python_as_parent(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'private-log';started=[]
            status=run_artifact_child_v3([sys.executable,'-c',
                'import os,sys;sys.stdout.write(str(os.getppid()))'],{},path,
                timeout=10,max_log_bytes=100,on_started=lambda pid:started.append(pid))
            self.assertEqual(status,0)
            self.assertEqual(int(path.read_text()),os.getpid())
            self.assertEqual(len(started),1);self.assertNotEqual(started[0],os.getpid())
            self.assertEqual(path.stat().st_mode&0o777,0o600)

    def test_pin_git_subprocesses_do_not_inherit_source_or_control_credentials(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();root.chmod(0o700)
            target=root/'dist/upload/index.js';target.parent.mkdir(parents=True);target.write_bytes(b'wrong bytes')
            replies=[subprocess.CompletedProcess([],0,(UPLOAD_ACTION_COMMIT+'\n').encode()),
                subprocess.CompletedProcess([],0,('100644 blob '+UPLOAD_ACTION_DIST_BLOB+'\tdist/upload/index.js\n').encode())]
            with patch.dict(os.environ,{'GITHUB_TOKEN':'fixture-control','REVIEW_BROKER_SOURCE_TOKEN':'fixture-source',
                    'NODE_OPTIONS':'unwanted-loader','REVIEW_BROKER_SOURCE_APP_PRIVATE_KEY':'fixture-key'}), \
                    patch('review_broker.actions_artifact_child_v3.subprocess.run',side_effect=replies) as run:
                with self.assertRaisesRegex(ValueError,'BYTES_MISMATCH'):verify_upload_helper_v3(root)
                for call in run.call_args_list:
                    env=call.kwargs['env']
                    for key in ('GITHUB_TOKEN','REVIEW_BROKER_SOURCE_TOKEN','NODE_OPTIONS','REVIEW_BROKER_SOURCE_APP_PRIVATE_KEY'):
                        self.assertNotIn(key,env)
