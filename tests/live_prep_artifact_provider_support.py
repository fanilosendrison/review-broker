"""External raw Artifact provider and independently observed broker policy Git objects."""
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit,parse_qs

from tests.live_prep_actions_support import response,SHA
from tests.live_prep_provider_support import LiveProviderService
from tests.issue70_rwp03_test_support import POLICY_BYTES
from review_broker.github_http_live_v3 import HttpResponseV3


class CompleteProviderService(LiveProviderService):
    def __init__(self,root):
        super().__init__(root)
        blob=hashlib.sha1(b'blob '+str(len(POLICY_BYTES)).encode()+b'\0'+POLICY_BYTES).hexdigest()
        self.git.blobs[blob]=POLICY_BYTES
        tree=self.git.commits[SHA][0]
        identifiers=['e1'*20,'e2'*20,'e3'*20]
        self.git.trees[tree].append({'path':'src','mode':'040000','type':'tree','sha':identifiers[0]})
        self.git.trees[identifiers[0]]=[{'path':'review_broker','mode':'040000','type':'tree','sha':identifiers[1]}]
        self.git.trees[identifiers[1]]=[{'path':'profiles','mode':'040000','type':'tree','sha':identifiers[2]}]
        self.git.trees[identifiers[2]]=[{'path':'pre-model-v3-expected-policy.json','mode':'100644','type':'blob','sha':blob}]
        self.uploads=[];self.objects={};self.metadata_calls=[];self.downloads=[];self.started=[]
        self.upload_unknown=False;self.metadata_failure=None

    def runner(self,argv,environment,log,**options):
        for forbidden in ('GITHUB_TOKEN','GH_TOKEN','REVIEW_BROKER_SOURCE_TOKEN','REVIEW_BROKER_SOURCE_APP_PRIVATE_KEY'):
            assert forbidden not in environment
        raw=Path(environment['INPUT_PATH']).read_bytes();name=Path(environment['INPUT_PATH']).name
        assert environment['INPUT_ARCHIVE']=='false' and environment['INPUT_OVERWRITE']=='false'
        assert environment['INPUT_RETENTION-DAYS']=='30'
        self.started.append((os.getpid(),argv))
        if options.get('on_started'):options['on_started'](os.getpid())
        self.uploads.append((name,raw))
        identifier=990+len(self.uploads);now=datetime.now(timezone.utc)
        self.objects[identifier]={'raw':raw,'id':identifier,'name':name,
            'digest':'sha256:'+hashlib.sha256(raw).hexdigest(),'size_in_bytes':len(raw),
            'created_at':now.isoformat().replace('+00:00','Z'),
            'expires_at':(now+timedelta(days=30)).isoformat().replace('+00:00','Z'),
            'expired':False,'workflow_run':{'id':70001,'repository_id':1433701208,
                'head_repository_id':1433701208,'head_sha':SHA}}
        if self.upload_unknown and name.startswith('rb-v3-prepared-'):raise TimeoutError('provider ACK lost')
        return 0

    def metadata(self,request,*,max_bytes):
        self.metadata_calls.append(request.full_url)
        path=urlsplit(request.full_url).path
        if path.endswith('/artifacts'):
            if self.metadata_failure is not None:return response({},self.metadata_failure)
            name=parse_qs(urlsplit(request.full_url).query)['name'][0]
            values=[{k:v for k,v in obj.items() if k!='raw'} for obj in self.objects.values() if obj['name']==name]
            return response({'total_count':len(values),'artifacts':values})
        if path.endswith('/zip'):
            identifier=int(path.split('/')[-2])
            assert identifier in self.objects
            return HttpResponseV3(302,b'',{'Location':f'https://fixture.blob.core.windows.net/raw/{identifier}?sig=fixture'})
        return self(request)

    def storage(self,request,*,max_bytes):
        assert not request.header_items()
        self.downloads.append(request.full_url)
        identifier=int(urlsplit(request.full_url).path.rsplit('/',1)[-1]);raw=self.objects[identifier]['raw']
        for offset in range(0,len(raw),65536):yield raw[offset:offset+65536]
