"""Reconstruct retained mutable observations from packet-bound provenance."""
from .github_issue_reference_v3 import GitHubIssueReferenceObservationV3
def reconstruct_issue_observations_v3(directory,entries,read_snapshot):
 retained=[]
 for entry in entries:
  if entry["source_kind"] not in {"github_issue_body","github_issue_comment"}: continue
  data,_=read_snapshot(directory,entry,git=False)
  retained.append(GitHubIssueReferenceObservationV3(entry["source_kind"],entry["repository"],entry["repository_id"],entry["selector_id"],entry["issue_id"],entry["issue_number"],entry["comment_id"],entry["author_id"],data,len(data),entry["sha256"],entry["observed_at"],entry["updated_at"],entry["api_source"],entry["qualification"],entry["authority_evidence_id"],entry["installation_id"],entry["provenance_evidence_id"]))
 return tuple(retained)
