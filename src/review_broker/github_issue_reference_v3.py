"""Authenticated read-only mutable GitHub Issue reference observations."""
from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib, json, re
from typing import Callable, Mapping
from urllib.parse import quote, urlparse
from urllib.request import Request
from .github_http_live_v3 import HttpExecutorV3, HttpResponseV3, urllib_executor_bounded
from .identity import artifact_identity, canonical_bytes
from .physical import PhysicalLineError, decode_physical_lines

_API="https://api.github.com"; _VERSION="2022-11-28"; _MAX=2_000_000; _RESP=3_000_000
_REPO=re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
class GitHubIssueReferenceV3Error(RuntimeError): pass

@dataclass(frozen=True)
class GitHubIssueReferenceObservationV3:
    source_kind: str; repository: str; repository_id: int; selector_id: int
    issue_id: int; issue_number: int; comment_id: int | None; author_id: int
    original_bytes: bytes; original_byte_length: int; sha256: str
    observed_at: str; updated_at: str; api_source: str
    qualification: str; authority_evidence_id: str; installation_id: int | None; evidence_id: str
    def provenance_basis(self):
        return {"schema_version":1,"evidence_type":"github-issue-reference-observation",
            "source_kind":self.source_kind,"repository":self.repository,"repository_id":self.repository_id,
            "selector_id":self.selector_id,"issue_id":self.issue_id,"issue_number":self.issue_number,
            "comment_id":self.comment_id,"author_id":self.author_id,
            "original_byte_length":self.original_byte_length,"sha256":self.sha256,
            "observed_at":self.observed_at,"updated_at":self.updated_at,"api_source":self.api_source,
            "qualification":self.qualification,"authority_evidence_id":self.authority_evidence_id,
            "installation_id":self.installation_id}

def _positive(v,m):
    if type(v) is not int or v<1: raise GitHubIssueReferenceV3Error(m)
    return v
def _object(response,marker):
    if len(response.body)>_RESP: raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_RESPONSE_TOO_LARGE")
    try: value=json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError,json.JSONDecodeError): raise GitHubIssueReferenceV3Error(marker) from None
    if not isinstance(value,dict): raise GitHubIssueReferenceV3Error(marker)
    return value

class GitHubIssueReferenceReaderV3:
    def __init__(self,token,repository,repository_id,*,authority_evidence_id,
                 expected_installation_id=None,source_authority=None,qualification_only=False,executor=None,clock=None):
        if (type(authority_evidence_id) is not str
            or re.fullmatch(r"artifact:sha256:[0-9a-f]{64}",authority_evidence_id) is None):
            raise ValueError("GITHUB_SOURCE_AUTHORITY_INVALID")
        if not token or token.strip()!=token or any(c in token for c in "\r\n"): raise ValueError("GITHUB_TOKEN_INVALID")
        if _REPO.fullmatch(repository) is None: raise ValueError("GITHUB_REPOSITORY_INVALID")
        _positive(repository_id,"GITHUB_REPOSITORY_ID_INVALID")
        if not qualification_only:
            from .github_source_authority_v3 import GitHubSourceAuthorityV3
            if type(source_authority) is not GitHubSourceAuthorityV3: raise ValueError("GITHUB_SOURCE_AUTHORITY_REQUIRED")
        self.repository,self.repository_id,self._token=repository,repository_id,token
        self.authority_evidence_id=authority_evidence_id;self.source_authority=source_authority
        self.installation_id=expected_installation_id if qualification_only else getattr(source_authority,"installation_id",None)
        if not qualification_only:_positive(self.installation_id,"GITHUB_INSTALLATION_ID_INVALID")
        self.qualification_only=qualification_only; self._owner,self._name=repository.split("/",1)
        self._executor=executor or (lambda req: urllib_executor_bounded(req,_RESP))
        self._clock=clock or (lambda:datetime.now(timezone.utc))
    def _get(self,suffix):
        root=f"/repos/{quote(self._owner,safe='')}/{quote(self._name,safe='')}"
        allowed=(suffix=="" or re.fullmatch(r"/issues/[1-9][0-9]*",suffix)
                 or re.fullmatch(r"/issues/comments/[1-9][0-9]*",suffix))
        if not allowed: raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_ENDPOINT_INVALID")
        url=_API+root+suffix
        request=Request(url,headers={"Accept":"application/vnd.github+json","Authorization":f"Bearer {self._token}","X-GitHub-Api-Version":_VERSION},method="GET")
        try: response=self._executor(request)
        except Exception: raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_AUTHORITY_UNAVAILABLE") from None
        if not isinstance(response,HttpResponseV3): raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_RESPONSE_INVALID")
        if response.status in {403,404}: raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_AUTHORITY_AMBIGUOUS")
        if response.status!=200: raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_UNAVAILABLE")
        return response
    def _authority(self) -> str:
        supplied_evidence_id=self.authority_evidence_id
        if (type(supplied_evidence_id) is not str
            or re.fullmatch(r"artifact:sha256:[0-9a-f]{64}",supplied_evidence_id) is None):
            raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_SOURCE_AUTHORIZATION_EVIDENCE_MISMATCH")
        if not self.qualification_only:
            from .admission_v3 import SourceRepositoryAuthorizationV3
            from .github_source_authority_v3 import GitHubSourceAuthorityV3
            if (type(self.source_authority) is not GitHubSourceAuthorityV3
                or not self.source_authority.permits_token(self._token,self.repository,self.repository_id)):
                raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_SOURCE_AUTHORITY_MISMATCH")
            authorization=self.source_authority.authorize(self.repository,self.repository_id)
            if type(authorization) is not SourceRepositoryAuthorizationV3:
                raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_SOURCE_AUTHORIZATION_EVIDENCE_MISMATCH")
            actual_evidence_id=authorization.evidence_id
            if (type(actual_evidence_id) is not str
                or authorization.repository!=self.repository
                or type(authorization.repository_id) is not int or authorization.repository_id!=self.repository_id
                or type(authorization.installation_id) is not int or authorization.installation_id!=self.installation_id
                or re.fullmatch(r"artifact:sha256:[0-9a-f]{64}",actual_evidence_id) is None
                or supplied_evidence_id!=actual_evidence_id):
                raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_SOURCE_AUTHORIZATION_EVIDENCE_MISMATCH")
            return actual_evidence_id
        return supplied_evidence_id
    def _repo(self):
        value=_object(self._get(""),"ISSUE_REFERENCE_REPOSITORY_INVALID")
        if value.get("full_name")!=self.repository or _positive(value.get("id"),"ISSUE_REFERENCE_REPOSITORY_INVALID")!=self.repository_id: raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_REPOSITORY_MISMATCH")
    def _issue(self,number):
        value=_object(self._get(f"/issues/{_positive(number,'ISSUE_REFERENCE_NUMBER_INVALID')}"),"ISSUE_REFERENCE_ISSUE_INVALID")
        if value.get("number")!=number or "pull_request" in value: raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_PARENT_INVALID")
        return value
    def _finish(self,kind,selector,issue,comment,body,author,updated,source,expected):
        if not isinstance(body,str): raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_BODY_INVALID")
        try: data=body.encode("utf-8"); decode_physical_lines(data)
        except (UnicodeEncodeError,PhysicalLineError): raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_UTF8_INVALID") from None
        if len(data)>_MAX: raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_BODY_TOO_LARGE")
        if self._token.encode("utf-8") in data: raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_SOURCE_CREDENTIAL_IN_CONTENT")
        digest=hashlib.sha256(data).hexdigest()
        if expected is not None and digest!=expected: raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_EXPECTED_SHA256_MISMATCH")
        author_id=_positive(author,"ISSUE_REFERENCE_AUTHOR_INVALID"); issue_id=_positive(issue.get("id"),"ISSUE_REFERENCE_ISSUE_ID_INVALID")
        if not isinstance(updated,str) or not updated: raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_UPDATED_AT_INVALID")
        now=self._clock();
        if now.tzinfo is None: raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_OBSERVATION_TIME_INVALID")
        observed=now.astimezone(timezone.utc).isoformat().replace("+00:00","Z")
        q="SAME_REPOSITORY_ACTIONS_QUALIFICATION" if self.qualification_only else "AUTHENTICATED_READ_ONLY"
        verified_authority_evidence_id=self._authority()
        provisional=GitHubIssueReferenceObservationV3(kind,self.repository,self.repository_id,selector,
            issue_id,issue["number"],None if comment is None else selector,author_id,data,len(data),digest,
            observed,updated,source,q,verified_authority_evidence_id,self.installation_id,"")
        return replace(provisional,evidence_id=artifact_identity(canonical_bytes(provisional.provenance_basis())+b"\n"))
    def observe_issue_body(self,issue_number,expected_sha256=None):
        self._authority(); self._repo(); issue=self._issue(issue_number); self._repo()
        user=issue.get("user");
        if not isinstance(user,dict): raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_AUTHOR_INVALID")
        return self._finish("github_issue_body",issue_number,issue,None,issue.get("body"),user.get("id"),issue.get("updated_at"),f"{_API}/repos/{self.repository}/issues/{issue_number}",expected_sha256)
    def observe_issue_comment(self,comment_id,expected_sha256=None):
        self._authority(); self._repo(); comment=_object(self._get(f"/issues/comments/{_positive(comment_id,'ISSUE_REFERENCE_COMMENT_ID_INVALID')}"),"ISSUE_REFERENCE_COMMENT_INVALID")
        if comment.get("id")!=comment_id: raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_COMMENT_ID_MISMATCH")
        issue_url=comment.get("issue_url")
        if not isinstance(issue_url,str) or not issue_url.startswith(f"{_API}/repos/{self.repository}/issues/"): raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_PARENT_URL_INVALID")
        try: number=int(issue_url.rsplit("/",1)[1])
        except ValueError: raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_PARENT_URL_INVALID") from None
        issue=self._issue(number); user=comment.get("user")
        if not isinstance(user,dict): raise GitHubIssueReferenceV3Error("ISSUE_REFERENCE_AUTHOR_INVALID")
        self._repo(); return self._finish("github_issue_comment",comment_id,issue,comment,comment.get("body"),user.get("id"),comment.get("updated_at"),f"{_API}/repos/{self.repository}/issues/comments/{comment_id}",expected_sha256)
