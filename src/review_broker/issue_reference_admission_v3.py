"""Ordered stable-object admission for mutable GitHub Issue references."""
from .github_issue_reference_v3 import GitHubIssueReferenceReaderV3
class IssueReferenceAdmissionV3Error(ValueError): pass

def acquire_issue_reference_admissions_v3(request,subject,readers,authority_evidence_id,installation_id):
    observed=[]
    for ref in request["references"]:
        source=ref["source"]; kind=source["kind"]
        if kind not in {"github_issue_body","github_issue_comment"}: continue
        reader=None if readers is None else readers.get(ref["id"])
        if type(reader) is not GitHubIssueReferenceReaderV3: raise IssueReferenceAdmissionV3Error("ISSUE_REFERENCE_TRUSTED_READER_REQUIRED")
        if (reader.repository!=subject["repository"] or reader.repository_id!=subject["repository_id"]
                or reader.authority_evidence_id!=authority_evidence_id or reader.installation_id!=installation_id
                or reader.qualification_only): raise IssueReferenceAdmissionV3Error("ISSUE_REFERENCE_AUTHORITY_MISMATCH")
        try:
            item=(reader.observe_issue_body(source["issue"],source.get("expected_sha256")) if kind=="github_issue_body"
                  else reader.observe_issue_comment(source["comment_id"],source.get("expected_sha256")))
        except Exception: raise IssueReferenceAdmissionV3Error("ISSUE_REFERENCE_OBSERVATION_UNAVAILABLE") from None
        if (item.qualification!="AUTHENTICATED_READ_ONLY" or item.authority_evidence_id!=authority_evidence_id
                or item.installation_id!=installation_id or item.repository!=subject["repository"]
                or item.repository_id!=subject["repository_id"]): raise IssueReferenceAdmissionV3Error("ISSUE_REFERENCE_AUTHORITY_MISMATCH")
        observed.append(item)
    return tuple(observed)
