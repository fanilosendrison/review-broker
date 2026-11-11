"""One bounded Git-object journal read; never moves or substitutes the claim head."""
from .github_journal_transport_v3 import ReadResultV3, ReadStatusV3, TransportSnapshotV3


def read_journal_commit_v3(transport, commit_sha: str) -> ReadResultV3:
    from .github_git_database_error_v3 import GitHubTransportLiveV3Error
    expected = transport._sha(commit_sha)
    try:
        transport._establish_repository_identity(refresh=True)
        commit = transport._get_commit(expected, require_one_parent=True)
        raw = transport._read_journal_blob(commit["tree"]["sha"])
        return ReadResultV3(ReadStatusV3.FOUND, TransportSnapshotV3(
            expected, commit["parents"][0]["sha"], raw))
    except GitHubTransportLiveV3Error:
        return ReadResultV3(ReadStatusV3.UNAVAILABLE)
