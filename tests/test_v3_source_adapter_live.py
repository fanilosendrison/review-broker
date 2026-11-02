"""Blocking provenance regression against the exact, unmodified PR #72 tree.

The original probes went RED on the historical candidate and are retained.
They now exercise the separately reviewed correction. All acquisitions use
injected HTTP or temporary local Git, never production credentials.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SHA = "e65e4db932cb59d7a0fcfbd442ba19e548fc141d"
TREE = "420a18d006e421e197d23b8e93681376fbabc2db"
PROBE = r'''
import json,sys
from tests.issue69_test_support import source_authority,REPOSITORY,REPOSITORY_ID,TOKEN
from tests.test_github_git_file_v3 import Api as GitApi,COMMIT
from tests.test_github_issue_reference_v3 import Api as IssueApi
from review_broker.github_git_file_v3 import GitHubGitFileReaderV3
from review_broker.github_issue_reference_v3 import GitHubIssueReferenceReaderV3
source=source_authority()
expected=source.authorize(REPOSITORY,REPOSITORY_ID).evidence_id
supplied=expected if sys.argv[2]=='positive' else 'artifact:sha256:'+'0'*64
assert sys.argv[2]=='positive' or supplied!=expected
try:
    if sys.argv[1]=='git_file':
        reader=GitHubGitFileReaderV3(TOKEN,REPOSITORY,REPOSITORY_ID,
            authority_evidence_id=supplied,source_authority=source,
            qualification_only=False,executor=GitApi())
        observation=reader.observe(COMMIT,'contract.md')
    else:
        reader=GitHubIssueReferenceReaderV3(TOKEN,REPOSITORY,REPOSITORY_ID,
            authority_evidence_id=supplied,source_authority=source,
            qualification_only=False,executor=IssueApi())
        observation=(reader.observe_issue_body(43) if sys.argv[1]=='issue'
                     else reader.observe_issue_comment(99))
except (ValueError,RuntimeError):
    print(json.dumps({'rejected':True}))
else:
    print(json.dumps({'rejected':False,'qualification':observation.qualification,
        'bound_to_actual_authorization':observation.authority_evidence_id==expected,
        'propagated_supplied_identity':observation.authority_evidence_id==supplied}))
'''


def pinned_pr72_test_checkout():
    """Require an explicitly provisioned local Git fixture; never acquire code."""
    supplied = os.environ.get("REVIEW_BROKER_PR72_TEST_CHECKOUT")
    if not supplied:
        raise AssertionError("PR72_TEST_FIXTURE_REQUIRED")
    root = Path(supplied)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise AssertionError("PR72_TEST_FIXTURE_PATH_INVALID")
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update({"GIT_NO_REPLACE_OBJECTS": "1", "GIT_CONFIG_NOSYSTEM": "1",
                        "GIT_CONFIG_GLOBAL": os.devnull})

    def revision(expression):
        try:
            raw = subprocess.check_output(["git", "-C", str(root), "rev-parse", expression],
                                          env=environment, stderr=subprocess.PIPE, timeout=30)
        except (OSError, subprocess.SubprocessError):
            raise AssertionError("PR72_TEST_FIXTURE_GIT_INVALID") from None
        if not raw.endswith(b"\n"):
            raise AssertionError("PR72_TEST_FIXTURE_GIT_INVALID")
        return os.fsdecode(raw[:-1])

    if Path(revision("--show-toplevel")).resolve() != root.resolve():
        raise AssertionError("PR72_TEST_FIXTURE_GIT_INVALID")
    if revision("HEAD") != SHA:
        raise AssertionError("PR72_TEST_FIXTURE_SHA_MISMATCH")
    if revision("HEAD^{tree}") != TREE:
        raise AssertionError("PR72_TEST_FIXTURE_TREE_MISMATCH")
    return root


class PinnedAdapterAuthorizationBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        checkout = pinned_pr72_test_checkout()
        cls.temporary = tempfile.TemporaryDirectory(prefix="adapter-provenance-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.candidate = Path(cls.temporary.name)
        archive = subprocess.check_output(["git", "-C", str(checkout), "archive", SHA])
        subprocess.run(["tar", "-x", "-C", str(cls.candidate)], input=archive, check=True)

    def probe(self, adapter, mode):
        environment = {**os.environ, "PYTHONPATH": str(self.candidate / "src"),
                       "PYTHONDONTWRITEBYTECODE": "1", "GH_TOKEN": "", "GITHUB_TOKEN": "",
                       "REVIEW_BROKER_SOURCE_TOKEN": ""}
        result = subprocess.run([sys.executable, "-c", PROBE, adapter, mode],
                                cwd=self.candidate, env=environment, capture_output=True,
                                text=True, timeout=30, check=True)
        return json.loads(result.stdout)

    def test_actual_authorization_positive_control(self):
        for adapter in ("git_file", "issue", "comment"):
            with self.subTest(adapter=adapter):
                result = self.probe(adapter, "positive")
                self.assertFalse(result["rejected"])
                self.assertEqual(result["qualification"], "AUTHENTICATED_READ_ONLY")
                self.assertTrue(result["bound_to_actual_authorization"])

    def test_substituted_authorization_is_rejected(self):
        for adapter in ("git_file", "issue", "comment"):
            with self.subTest(adapter=adapter):
                result = self.probe(adapter, "substituted")
                self.assertTrue(result["rejected"],
                                f"{adapter}: actual pinned adapter accepted substituted authorization: {result}")


# The subprocess imports only the immutable candidate, never dev's package.
INTEGRATION = r'''
import base64,hashlib,importlib.util,json,os,subprocess,sys,tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('qualification_controller',sys.argv[1])
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
scenario=sys.argv[3];candidate=Path(sys.argv[2])
if scenario in ('sha','tree','origin'):
    if scenario=='sha': c.CANDIDATE_SHA='0'*40
    if scenario=='tree': c.CANDIDATE_TREE='0'*40
    original=c.importlib.import_module
    def wrong_origin(name):
        module=original(name)
        if name.endswith(c.MODULES[0]): module.__file__=str(candidate.parent/'foreign.py')
        return module
    with patch.object(c.importlib,'import_module',side_effect=wrong_origin):
        try: c.load_candidate(candidate)
        except c.QualificationError as error: print(json.dumps({'rejected':str(error)}))
        else: raise AssertionError('invalid candidate accepted')
    sys.exit(0)
modules=c.load_candidate(candidate)
from tests.issue69_test_support import git_graph,local_acquirer,PullApi,ScopeApi
from review_broker.github_http_live_v3 import HttpResponseV3
from review_broker import packet_v2 as packet
assert all(Path(m.__file__).resolve().is_relative_to(candidate/'src') for m in modules.values())
env={'REVIEW_BROKER_SOURCE_TOKEN':'offline-source-secret',
     'SOURCE_APP_SLUG':'review-broker-app','SOURCE_INSTALLATION_ID':'176619170',
     'GITHUB_SHA':'1'*40,'GITHUB_JOB':'qualify','GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1'}
with tempfile.TemporaryDirectory() as temporary:
    origin,base,head,merge,files=git_graph(Path(temporary))
    c.HEAD,c.BASE,c.FILE_COUNT=head,base,2
    c.FILE_PATH='review.md';data=b'feature\n'
    c.FILE_DIGEST=hashlib.sha256(data).hexdigest()
    c.FILE_OID=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    tree=subprocess.check_output(['git','-C',str(origin),'rev-parse',head+'^{tree}'],text=True).strip()
    pr=PullApi(base,head,merge,files,pr_id=c.PR_ID)
    scope_api=ScopeApi();roots=[];methods=[]
    if scenario=='repository': scope_api=ScopeApi(repositories=[{'full_name':c.REPOSITORY,'id':9}])
    if scenario=='scope_incomplete': scope_api=ScopeApi(total=2)
    if scenario=='initial_base': c.BASE='f'*40
    if scenario=='initial_head': pr.head='f'*40
    if scenario=='head': pr.drift_head='f'*40
    if scenario=='base': pr.drift_base='f'*40
    if scenario=='merge': pr.merge='f'*40
    if scenario=='files': pr.files_total=3
    if scenario=='pr_id': pr.pr_id+=1
    if scenario=='installation': env['SOURCE_INSTALLATION_ID']='123'
    def api(request):
        assert request.method=='GET';methods.append(request.method)
        assert request.get_header('Authorization')=='Bearer '+env['REVIEW_BROKER_SOURCE_TOKEN']
        url=request.full_url
        if '/installation/repositories?' in url: return scope_api(request)
        if '/pulls/' in url or '/compare/' in url:
            response=pr(request)
            if scenario=='pr_number' and url.endswith('/pulls/71'):
                value=json.loads(response.body);value['number']=72
                return HttpResponseV3(200,json.dumps(value).encode(),{})
            return response
        if url.endswith('/review-broker'): return pr(request)
        if '/git/commits/' in url: value={'sha':head,'tree':{'sha':tree}}
        elif '/git/trees/' in url:
            value={'sha':tree,'truncated':False,'tree':[{'path':'review.md','mode':'100644','type':'blob','sha':c.FILE_OID}]}
            if scenario=='missing_reference': value['tree']=[]
        elif '/git/blobs/' in url:
            value={'sha':c.FILE_OID,'encoding':'base64','size':len(data),'content':base64.b64encode(data).decode()}
            if scenario=='api_blob': value['content']=base64.b64encode(b'wrong bytes').decode()
        elif '/issues/comments/' in url:
            value={'id':6535094733,'body':'comment fixture text','updated_at':'2026-01-01Z',
                   'issue_url':'https://api.github.com/repos/'+c.REPOSITORY+'/issues/51','user':{'id':30498238}}
            if scenario=='comment': value['id']+=1
            if scenario=='author': value['user']['id']+=1
            if scenario=='comment_parent': value['issue_url']=value['issue_url'].replace('/51','/52')
            if scenario=='token_content': value['body']=env['REVIEW_BROKER_SOURCE_TOKEN']
        elif '/issues/' in url:
            number=int(url.rsplit('/',1)[1]);value={'id':6101161202 if number==43 else 6106789428,
                'number':number,'body':'issue fixture text','updated_at':'2026-01-01Z','user':{'id':30498238}}
            if scenario=='issue': value['id']+=1
            if scenario=='incomplete': value.pop('body')
        else: raise AssertionError('unexpected endpoint')
        if scenario=='ambiguous' and '/issues/' in url: return HttpResponseV3(403,b'{}',{})
        return HttpResponseV3(200,json.dumps(value).encode(),{})
    def acquire(destination,environment):
        roots.append(destination.parent)
        assert environment['GH_TOKEN']==env['REVIEW_BROKER_SOURCE_TOKEN']
        assert 'GITHUB_TOKEN' not in environment
        if scenario=='acquisition': raise RuntimeError('fixture acquisition failure')
        local_acquirer(origin)(destination,environment)
    capture_module=modules[c.MODULES[2]];real_capture=capture_module.capture_authenticated_subject_v3
    def capture(*args,**kwargs):
        value=real_capture(*args,**kwargs)
        if scenario=='images': value=replace(value,records=value.records[:-1])
        if scenario=='blob': value=replace(value,records=(replace(value.records[0],original_bytes=b'corrupt'),)+value.records[1:])
        if scenario=='diff': value=replace(value,diff=b'wrong diff')
        if scenario=='partial': value=replace(value,verification='INCOMPLETE')
        return replace(value,evidence_id=packet.subject_capture_evidence_id_v2(value))
    git_module=modules[c.MODULES[3]];real_reader=git_module.GitHubGitFileReaderV3
    class InvalidString(str): pass
    def reference_reader(*args,**kwargs):
        if scenario=='provenance': kwargs['authority_evidence_id']='artifact:sha256:'+'0'*64
        if scenario=='subclass': kwargs['authority_evidence_id']=InvalidString(kwargs['authority_evidence_id'])
        if scenario=='token': args=('different-source-token',)+args[1:]
        reader=real_reader(*args,**kwargs)
        if scenario=='reference_evidence':
            observe=reader.observe
            reader.observe=lambda *a,**k: replace(observe(*a,**k),evidence_id='issue fixture text')
        return reader
    with patch.object(capture_module,'capture_authenticated_subject_v3',side_effect=capture), \
         patch.object(git_module,'GitHubGitFileReaderV3',side_effect=reference_reader):
        try: receipt=c.qualify(env,modules,api,acquire_repository=acquire)
        except (ValueError,RuntimeError) as error:
            if scenario=='positive': raise
            result={'rejected':type(error).__name__}
        else:
            assert scenario=='positive','negative result accepted: '+scenario
            assert receipt['merge_base_sha']==merge and receipt['head_sha']==head and receipt['base_sha']==base
            assert receipt['changed_file_count']==2 and receipt['preimage_count']==1 and receipt['postimage_count']==2
            expected=[(head,'added.md',b'added\n'),(merge,'review.md',b'common\n'),(head,'review.md',b'feature\n')]
            assert len(receipt['images'])==len(expected)
            for image,(commit,path,raw) in zip(receipt['images'],expected):
                assert image=={'commit':commit,'path':path,'git_blob_oid':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),
                               'original_sha256':hashlib.sha256(raw).hexdigest(),'original_size':len(raw)}
            diff=subprocess.check_output(['git','-C',str(origin),'diff','--binary','--full-index','--no-ext-diff','--no-textconv',
                                          '--find-renames','--find-copies-harder',merge,head,'--'])
            assert receipt['binary_diff_sha256']==hashlib.sha256(diff).hexdigest()
            assert receipt['issue_sha256']==hashlib.sha256(b'issue fixture text').hexdigest()
            assert receipt['comment_sha256']==hashlib.sha256(b'comment fixture text').hexdigest()
            claimed=receipt.pop('receipt_sha256');encoded=packet.canonical_bytes(receipt)
            assert hashlib.sha256(encoded).hexdigest()==claimed
            for raw in (data,b'common\n',b'added\n',b'issue fixture text',b'comment fixture text',env['REVIEW_BROKER_SOURCE_TOKEN'].encode()):
                assert raw not in encoded
            assert receipt['github_mutations']==receipt['codespace_effects']==receipt['model_invocations']==0
            assert receipt['requester_authority']==receipt['packet_readiness']=='NOT_QUALIFIED'
            assert set(receipt['boundaries'].values())=={'PASS'}
            assert methods and set(methods)=={'GET'}
            result={'passed':True,'images':len(receipt['images'])}
    assert all(not root.exists() for root in roots),'capture directory retained'
    print(json.dumps(result))
'''


class ControllerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        checkout = pinned_pr72_test_checkout()
        cls.temporary = tempfile.TemporaryDirectory(prefix="adapter-controller-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.candidate = Path(cls.temporary.name).resolve() / "candidate"
        subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", str(checkout),
                        str(cls.candidate)], check=True)
        subprocess.run(["git", "-C", str(cls.candidate), "checkout", "-q", "--detach", SHA], check=True)
        with patch.dict(os.environ, {"REVIEW_BROKER_PR72_TEST_CHECKOUT": str(cls.candidate)}):
            if pinned_pr72_test_checkout() != cls.candidate:
                raise AssertionError("PR72_TEST_CLONE_INVALID")

    def run_case(self, scenario):
        environment = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run([sys.executable, "-c", INTEGRATION,
                                 str(ROOT / "scripts/qualification/v3_source_adapter_live.py"),
                                 str(self.candidate), scenario], cwd=self.candidate,
                                env=environment, text=True, capture_output=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_real_candidate_import_capture_references_and_sanitized_receipt(self):
        self.assertEqual(self.run_case("positive"), {"passed": True, "images": 3})

    def test_candidate_identity_and_import_origin_fail_closed(self):
        for scenario in ("sha", "tree", "origin"):
            with self.subTest(scenario=scenario):
                self.assertIn("rejected", self.run_case(scenario))

    def test_real_adapters_reject_invalid_authority_scope_and_api_results(self):
        for scenario in ("repository", "installation", "token", "provenance", "subclass",
                         "head", "base", "merge", "files", "pr_id", "api_blob", "comment",
                         "author", "issue", "incomplete", "ambiguous", "missing_reference",
                         "token_content", "scope_incomplete", "initial_base", "initial_head",
                         "pr_number", "comment_parent"):
            with self.subTest(scenario=scenario):
                self.assertIn("rejected", self.run_case(scenario))

    def test_controller_rejects_corrupted_results_and_cleans_capture_directory(self):
        # These are post-return fault injections, not defects attributed to PR72.
        for scenario in ("images", "blob", "diff", "partial", "acquisition", "reference_evidence"):
            with self.subTest(scenario=scenario):
                self.assertIn("rejected", self.run_case(scenario))

    def test_adapter_workflow_snapshot_rejects_behavior_changes(self):
        from tests.test_source_app_credential_scope import audit_workflows, V3_ADAPTER_SITE
        workflows = {p.name: p.read_text() for p in (ROOT / ".github/workflows").glob("*.yml")}
        original = workflows[V3_ADAPTER_SITE]
        for old, new in ((SHA, "0" * 40), ("repository_dispatch:", "workflow_dispatch:"),
                         ("permission-issues: read", "permission-issues: write"),
                         ("persist-credentials: false", "persist-credentials: true"),
                         ("github.event.sender.id == 30498238", "true")):
            with self.subTest(old=old):
                self.assertIn(old, original)
                workflows[V3_ADAPTER_SITE] = original.replace(old, new, 1)
                with self.assertRaises(AssertionError):
                    audit_workflows(workflows)


class PinnedFixturePreparationTests(unittest.TestCase):
    def test_explicit_fixture_positive_and_invalid_paths(self):
        self.assertEqual(str(pinned_pr72_test_checkout()),
                         os.environ["REVIEW_BROKER_PR72_TEST_CHECKOUT"])
        with tempfile.TemporaryDirectory(prefix="adapter-fixture-validation-") as temporary:
            root = Path(temporary)
            link = root / "link"
            link.symlink_to(os.environ["REVIEW_BROKER_PR72_TEST_CHECKOUT"], target_is_directory=True)
            for value in ("relative", str(root / "missing"), str(link)):
                with self.subTest(path=value), patch.dict(os.environ, {"REVIEW_BROKER_PR72_TEST_CHECKOUT": value}):
                    with self.assertRaisesRegex(AssertionError, "PR72_TEST_FIXTURE_PATH_INVALID"):
                        pinned_pr72_test_checkout()
            with patch.dict(os.environ, {"REVIEW_BROKER_PR72_TEST_CHECKOUT": str(root)}):
                with self.assertRaisesRegex(AssertionError, "PR72_TEST_FIXTURE_GIT_INVALID"):
                    pinned_pr72_test_checkout()

    def test_missing_fixture_is_preparation_failure_not_skip(self):
        with patch.dict(os.environ):
            os.environ.pop("REVIEW_BROKER_PR72_TEST_CHECKOUT", None)
            with self.assertRaisesRegex(AssertionError, "PR72_TEST_FIXTURE_REQUIRED"):
                pinned_pr72_test_checkout()

    def test_each_exact_revision_comparison_is_required(self):
        with patch.dict(os.environ, {"REVIEW_BROKER_PR72_TEST_CHECKOUT": str(ROOT)}):
            with self.assertRaisesRegex(AssertionError, "PR72_TEST_FIXTURE_SHA_MISMATCH"):
                pinned_pr72_test_checkout()
        # Independently vary each expected identity against the real Git fixture.
        for constant, marker in (("SHA", "SHA_MISMATCH"), ("TREE", "TREE_MISMATCH")):
            with self.subTest(constant=constant), patch(__name__ + "." + constant, "0" * 40):
                with self.assertRaisesRegex(AssertionError, "PR72_TEST_FIXTURE_" + marker):
                    pinned_pr72_test_checkout()


if __name__ == "__main__":
    unittest.main()
