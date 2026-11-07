import os
import unittest
from unittest import mock
import qualify_update_refs as q

class Q3Tests(unittest.TestCase):
    def test_synthetic_scoped_ref_accept(self):
        with mock.patch.object(q,'graphql',return_value={'ok':True,'value':{'data':{'updateRefs':{'clientMutationId':'x'}}}}) as g:
            x=q.update_ref('repoNode','refs/heads/qualification/rb91-q3-data-123-1-abcd-race','a'*40,'b'*40,'x')
            self.assertTrue(x['ok']);self.assertEqual(g.call_args[0][1]['input']['refUpdates'][0]['force'],False)
    def test_prod_ref_rejected(self):
        for ref in ['refs/heads/dev','refs/heads/review-claims/'+'a'*64,'refs/heads/main']:
            with self.subTest(ref=ref),self.assertRaises(q.Q3Stop):q.update_ref('id',ref,'a'*40,'b'*40,'x')
    def test_oid_required(self):
        with self.assertRaises(q.Q3Stop):q.update_ref('id',q.PREFIX+'123-race','BAD','b'*40,'x')
    def test_controllers_must_be_action_on_test_ref(self):
        env={'GITHUB_REPOSITORY':q.REPO,'GITHUB_REF':'refs/heads/dev','GITHUB_EVENT_NAME':'push',
             'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'a'*40}
        with mock.patch.dict(os.environ,env,clear=True),self.assertRaises(q.Q3Stop):q.validated_context()
        env['GITHUB_REF']='refs/heads/'+q.RUN_BRANCH
        with mock.patch.dict(os.environ,env,clear=True):
            base,name,run,attempt=q.validated_context()
            self.assertEqual(base,'a'*40);self.assertTrue(name.startswith(q.PREFIX));self.assertEqual(run,'123')
    def test_get_ref_404_fails_closed(self):
        with mock.patch.object(q,'get_ref',return_value={'ok':False,'class':'HTTP_403'}),self.assertRaises(q.Q3Stop):
            q.make_case('a'*40,q.PREFIX+'123-1-abcd','race','aa')
    def test_graphql_errors_are_failures(self):
        with mock.patch.object(q,'_gh',return_value={'ok':False,'class':'GRAPHQL_ERRORS'}):
            self.assertFalse(q.graphql(q.MUTATE, {})['ok'])

if __name__=='__main__':unittest.main()