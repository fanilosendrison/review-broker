"""Fresh mutable-reference capture before candidate packet materialization."""
from .github_issue_reference_v3 import GitHubIssueReferenceReaderV3
from .identity import artifact_identity,canonical_bytes
from .physical import decode_physical_lines
class IssueReferencePreparationV3Error(ValueError): pass
def _same(a,b):
 return (a.source_kind,a.repository,a.repository_id,a.selector_id,a.issue_id,a.issue_number,a.comment_id,a.author_id,a.authority_evidence_id,a.qualification,a.installation_id)==(b.source_kind,b.repository,b.repository_id,b.selector_id,b.issue_id,b.issue_number,b.comment_id,b.author_id,b.authority_evidence_id,b.qualification,b.installation_id)
def _valid_evidence(item): return item.evidence_id==artifact_identity(canonical_bytes(item.provenance_basis())+b"\n")
def prepare_ordered_remote_observations_v3(request,admission,readers):
 git_iter=iter(admission.git_file_observations); issue_iter=iter(admission.issue_reference_observations); remote=[]; rendered=0
 for ref in request["references"]:
  kind=ref["source"]["kind"]
  if kind=="git_file": remote.append(next(git_iter))
  if kind in {"github_issue_body","github_issue_comment"}:
   reader=None if readers is None else readers.get(ref["id"])
   if type(reader) is not GitHubIssueReferenceReaderV3: raise IssueReferencePreparationV3Error("PACKET_V2_ISSUE_REFERENCE_READER_REQUIRED")
   selector=ref["source"]; admitted=next(issue_iter)
   if (reader.repository,reader.repository_id,reader.authority_evidence_id,reader.installation_id,reader.qualification_only)!=(admitted.repository,admitted.repository_id,admitted.authority_evidence_id,admitted.installation_id,False): raise IssueReferencePreparationV3Error("PACKET_V2_ISSUE_REFERENCE_AUTHORITY_MISMATCH")
   fresh=(reader.observe_issue_body(selector["issue"],selector.get("expected_sha256")) if kind=="github_issue_body" else reader.observe_issue_comment(selector["comment_id"],selector.get("expected_sha256")))
   if not _same(fresh,admitted) or not _valid_evidence(fresh): raise IssueReferencePreparationV3Error("PACKET_V2_ISSUE_REFERENCE_IDENTITY_CHANGED")
   rendered+=sum(len(line.encode("utf-8"))+9 for line in decode_physical_lines(fresh.original_bytes)[1])
   if rendered>8_000_000: raise IssueReferencePreparationV3Error("PACKET_V2_ISSUE_REFERENCE_RENDERED_LIMIT")
   remote.append(fresh)
 return tuple(remote)
def retained_ordered_remote_observations_v3(request,admission,issue_observations):
 git_iter=iter(admission.git_file_observations); issue_iter=iter(issue_observations); admitted_iter=iter(admission.issue_reference_observations); remote=[]
 for ref in request["references"]:
  kind=ref["source"]["kind"]
  if kind=="git_file": remote.append(next(git_iter))
  if kind in {"github_issue_body","github_issue_comment"}:
   item,admitted=next(issue_iter),next(admitted_iter)
   selector=ref["source"].get("issue",ref["source"].get("comment_id"))
   expected=ref["source"].get("expected_sha256")
   if item.source_kind!=kind or item.selector_id!=selector or not _same(item,admitted) or not _valid_evidence(item) or (expected is not None and item.sha256!=expected): raise IssueReferencePreparationV3Error("PACKET_V2_RETAINED_ISSUE_PROVENANCE_INVALID")
   remote.append(item)
 return tuple(remote)
