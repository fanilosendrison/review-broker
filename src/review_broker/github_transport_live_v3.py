"""Historical experimental transport import surface; implementation is shared Git Database I/O.

Legacy v1/v2 callers still do not import this module. Explicit pre-model live
composition imports the shared provider directly, only after CLI selection.
"""
from .github_git_database_transport_v3 import (
    GitHubTransportLiveV3, GitHubJournalEvidenceTransportV3, GitHubTransportLiveV3Error,
    HttpExecutorV3, HttpResponseV3, _RejectRedirects, urllib_executor,
)
