"""Read reuse never substitutes for fresh mutable state or a lost mutation response."""
from urllib.request import Request
import unittest

from review_broker.github_conditional_reads_v3 import GitHubConditionalReadsV3
from review_broker.github_http_live_v3 import HttpResponseV3
from review_broker.github_observed_journal_transport_v3 import GitHubObservedJournalTransportV3
from tests.github_transport_live_v3_support import FakeGitHubApi,REF,REPOSITORY


class ObservationReuseTests(unittest.TestCase):
    def test_conditional_response_is_fresh_and_errors_never_fall_back(self):
        calls=[];response=[HttpResponseV3(200,b'original',{'ETag':'"one"'})]
        def execute(request):calls.append(request);return response[0]
        client=GitHubConditionalReadsV3(execute)
        req=Request('https://api.github.com/repos/'+REPOSITORY,headers={'Authorization':'Bearer fake-A'})
        self.assertEqual(client(req).body,b'original')
        response[0]=HttpResponseV3(304,b'',{})
        self.assertEqual(client(req).body,b'original')
        self.assertEqual(calls[-1].get_header('If-none-match'),'"one"')
        response[0]=HttpResponseV3(403,b'{}',{})
        self.assertEqual(client(req).status,403)
        response[0]=HttpResponseV3(304,b'',{})
        with self.assertRaises(ValueError):client(req)
        self.assertEqual(len(calls),4)

    def test_credentials_partition_cache_and_post_is_never_cached(self):
        response=[HttpResponseV3(200,b'data',{'ETag':'"one"'})];calls=[]
        def execute(req):calls.append(req);return response[0]
        client=GitHubConditionalReadsV3(execute)
        url='https://api.github.com/repos/'+REPOSITORY
        client(Request(url,headers={'Authorization':'Bearer fake-A'}))
        response[0]=HttpResponseV3(304,b'',{})
        with self.assertRaises(ValueError):client(Request(url,headers={'Authorization':'Bearer fake-B'}))
        response[0]=HttpResponseV3(200,b'write-ack',{'ETag':'"write"'})
        request=Request(url+'/git/refs',method='POST',data=b'{}')
        client(request);client(request)
        self.assertEqual(len(calls),4)
        self.assertIsNone(calls[-1].get_header('If-none-match'))

    def test_immutable_snapshot_cache_still_reads_ref_and_sees_movement_or_403(self):
        api=FakeGitHubApi();old,_=api.install_journal()
        transport=GitHubObservedJournalTransportV3('fake-control',before_effect=lambda:None,executor=api)
        first=transport.read_claim(REF)
        before=len(api.calls);again=transport.read_claim(REF)
        self.assertEqual(first,again)
        self.assertEqual(len(api.calls)-before,1)
        self.assertIn('/git/ref/',api.calls[-1][1])
        after=api.install_successor(old);api.refs[REF]=after
        self.assertEqual(transport.read_claim(REF).snapshot.commit_sha,after)
        api.raise_on=('GET','https://api.github.com/repos/'+REPOSITORY+'/git/ref/'+REF.removeprefix('refs/'))
        with self.assertRaises(RuntimeError):transport.read_claim(REF)
