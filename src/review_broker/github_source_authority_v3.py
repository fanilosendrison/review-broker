"""Production-compatible GitHub source-App repository-scope authority."""
from __future__ import annotations
from dataclasses import dataclass,replace
import hashlib,json,re
from typing import Mapping
from urllib.parse import quote
from urllib.request import Request
from .admission_v3 import SourceRepositoryAuthorizationV3
from .github_http_live_v3 import HttpExecutorV3,HttpResponseV3,urllib_executor_bounded
from .identity import artifact_identity,canonical_bytes

_API="https://api.github.com";_VERSION="2022-11-28";_MAX=2_000_000
_REPO=re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_REQUIRED=frozenset({"contents:read","pull_requests:read","metadata:read","issues:read"})
class GitHubSourceAuthorityV3Error(RuntimeError): pass
@dataclass(frozen=True)
class SourceAppScopeObservationV3:
 app_slug:str;installation_id:int;repository:str;repository_id:int
 approved_permissions:tuple[str,...];authorized_repositories:tuple[str,...]
 observed_repository_count:int;api_source:str;evidence_id:str
 def basis(self)->dict[str,object]:
  return {"schema_version":1,"evidence_type":"github-source-app-scope-observation",
   "app_slug":self.app_slug,"installation_id":self.installation_id,
   "repository":self.repository,"repository_id":self.repository_id,
   "approved_permissions":list(self.approved_permissions),
   "authorized_repositories":list(self.authorized_repositories),
   "observed_repository_count":self.observed_repository_count,"api_source":self.api_source}
class GitHubSourceAuthorityV3:
 """Exercise one trusted minted token and authorize one selected repository."""
 def __init__(self,token:str,*,expected_app_slug:str,expected_installation_id:int,
              repository:str,repository_id:int,approved_permissions:frozenset[str],
              authorized_repositories:frozenset[str],executor:HttpExecutorV3|None=None):
  if not token or token.strip()!=token or any(c in token for c in "\r\n"): raise ValueError("SOURCE_TOKEN_INVALID")
  if not expected_app_slug or type(expected_installation_id) is not int or expected_installation_id<1: raise ValueError("SOURCE_MINT_CONTEXT_INVALID")
  if _REPO.fullmatch(repository) is None or type(repository_id) is not int or repository_id<1: raise ValueError("SOURCE_REPOSITORY_IDENTITY_INVALID")
  if authorized_repositories!=frozenset({repository}): raise ValueError("SOURCE_REPOSITORY_SELECTION_NOT_EXACT")
  if approved_permissions!=_REQUIRED: raise ValueError("SOURCE_APP_PERMISSION_SET_NOT_EXACT_READ_ONLY")
  self.repository,self.repository_id=repository,repository_id;self.app_slug=expected_app_slug
  self.installation_id=expected_installation_id;self.approved_permissions=approved_permissions
  self.authorized_repositories=authorized_repositories;self._token=token
  self._token_digest=hashlib.sha256(token.encode()).digest();self._executor=executor or (lambda request:urllib_executor_bounded(request,_MAX))
  self._scope:SourceAppScopeObservationV3|None=None
 def permits_token(self,token:str,repository:str,repository_id:int)->bool:
  return (repository==self.repository and repository_id==self.repository_id
   and hashlib.sha256(token.encode()).digest()==self._token_digest and self._scope is not None)
 def _get_page(self,page:int)->tuple[Mapping[str,object],Mapping[str,str]]:
  request=Request(f"{_API}/installation/repositories?per_page=100&page={page}",headers={"Accept":"application/vnd.github+json","Authorization":f"Bearer {self._token}","X-GitHub-Api-Version":_VERSION},method="GET")
  try: response=self._executor(request)
  except Exception: raise GitHubSourceAuthorityV3Error("SOURCE_SCOPE_UNAVAILABLE") from None
  if not isinstance(response,HttpResponseV3): raise GitHubSourceAuthorityV3Error("SOURCE_SCOPE_RESPONSE_INVALID")
  if response.status in {401,403,404}: raise GitHubSourceAuthorityV3Error("SOURCE_SCOPE_AUTHORITY_AMBIGUOUS")
  if response.status!=200 or len(response.body)>_MAX: raise GitHubSourceAuthorityV3Error("SOURCE_SCOPE_UNAVAILABLE")
  try:value=json.loads(response.body)
  except (UnicodeError,json.JSONDecodeError): raise GitHubSourceAuthorityV3Error("SOURCE_SCOPE_RESPONSE_INVALID") from None
  if not isinstance(value,dict): raise GitHubSourceAuthorityV3Error("SOURCE_SCOPE_RESPONSE_INVALID")
  return value,response.headers
 @staticmethod
 def _has_next(headers:Mapping[str,str])->bool:
  link=next((value for key,value in headers.items() if key.lower()=="link"),"")
  return any('rel="next"' in part for part in link.split(","))
 def observe_scope(self)->SourceAppScopeObservationV3:
  repositories=[];total=None;page=1
  while True:
   value,headers=self._get_page(page)
   if type(value.get("total_count")) is not int or value["total_count"]<0 or not isinstance(value.get("repositories"),list): raise GitHubSourceAuthorityV3Error("SOURCE_SCOPE_RESPONSE_INVALID")
   if total is None: total=value["total_count"]
   elif value["total_count"]!=total: raise GitHubSourceAuthorityV3Error("SOURCE_SCOPE_COUNT_DRIFT")
   batch=value["repositories"]
   if len(batch)>100: raise GitHubSourceAuthorityV3Error("SOURCE_SCOPE_PAGE_INVALID")
   repositories.extend(batch);has_next=self._has_next(headers)
   if has_next and not batch: raise GitHubSourceAuthorityV3Error("SOURCE_SCOPE_PAGINATION_INCOMPLETE")
   if not has_next: break
   page+=1
   if page>100: raise GitHubSourceAuthorityV3Error("SOURCE_SCOPE_PAGINATION_EXCEEDED")
  if len(repositories)!=total: raise GitHubSourceAuthorityV3Error("SOURCE_SCOPE_PAGINATION_INCOMPLETE")
  identities=[]
  for item in repositories:
   if not isinstance(item,dict) or not isinstance(item.get("full_name"),str) or type(item.get("id")) is not int: raise GitHubSourceAuthorityV3Error("SOURCE_SCOPE_REPOSITORY_INVALID")
   identities.append((item["full_name"],item["id"]))
  if len(identities)!=len(set(identities)) or len({name for name,_ in identities})!=len(identities): raise GitHubSourceAuthorityV3Error("SOURCE_SCOPE_REPOSITORY_DUPLICATE")
  if identities!=[(self.repository,self.repository_id)]: raise GitHubSourceAuthorityV3Error("SOURCE_SCOPE_NOT_EXACT_REPOSITORY")
  provisional=SourceAppScopeObservationV3(self.app_slug,self.installation_id,self.repository,self.repository_id,tuple(sorted(self.approved_permissions)),tuple(sorted(self.authorized_repositories)),len(identities),f"{_API}/installation/repositories","")
  self._scope=replace(provisional,evidence_id=artifact_identity(canonical_bytes(provisional.basis())+b"\n"));return self._scope
 @property
 def scope_observation(self)->SourceAppScopeObservationV3:
  if self._scope is None: raise GitHubSourceAuthorityV3Error("SOURCE_SCOPE_NOT_OBSERVED")
  return self._scope
 def authorize(self,repository:str,repository_id:int)->SourceRepositoryAuthorizationV3|None:
  if repository!=self.repository or repository_id!=self.repository_id or self._scope is None:return None
  basis={"schema_version":1,"evidence_type":"v3-source-repository-authorization","repository":repository,"repository_id":repository_id,"principal_id":self.app_slug,"installation_id":self.installation_id}
  return SourceRepositoryAuthorizationV3(repository,repository_id,self.app_slug,self.installation_id,artifact_identity(canonical_bytes(basis)+b"\n"))
