"""A fresh interpreter with provider observations but no original Worker/decision objects."""
import base64
from dataclasses import asdict
import json
from pathlib import Path
import sys

from tests.live_prep_actions_support import ActionsService
from tests.live_prep_provider_support import GitDatabaseService,TOKEN_B
from review_broker.github_live_runtime_v3 import REPOSITORY
from review_broker.live_pre_model_worker_v3 import run_live_worker_v3


def main():
    data=json.loads(Path(sys.argv[1]).read_bytes());root=Path(sys.argv[2])
    class Server(ActionsService):
        def __init__(self):
            super().__init__(data['request']);self.git=GitDatabaseService()
            self.git.refs=data['refs'];self.git.trees=data['trees']
            self.git.commits={k:(v[0],v[1]) for k,v in data['commits'].items()}
            self.git.blobs={k:base64.b64decode(v) for k,v in data['blobs'].items()}
        def __call__(self,req):
            if '/git/' in req.full_url or req.full_url=='https://api.github.com/graphql':return self.git(req)
            return super().__call__(req)
    service=Server();runtime=service.runtime('worker',data['inputs'])
    effects=[]
    def forbidden(*args,**kwargs):effects.append('forbidden');raise AssertionError('restarted Worker attempted an effect')
    before=service.git.mutation_calls
    result=run_live_worker_v3(runtime=runtime,source_token=TOKEN_B,app_slug='review-broker-app',
        installation_id=123,private_root=root,helper_root=Path('/unused/helper'),node=Path('/unused/node'),
        artifact_environment={},source_executor=forbidden,artifact_runner=forbidden,
        metadata_executor=forbidden,storage_executor=forbidden,sleeper=lambda seconds:None)
    assert result.status=='REJECTED' and not effects and service.git.mutation_calls==before
    sys.stdout.write(json.dumps({'result':asdict(result),'source_or_helper_effects':len(effects),'mutations':0})+'\n')


if __name__=='__main__':main()
