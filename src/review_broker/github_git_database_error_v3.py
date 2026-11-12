"""Shared typed Git Database failure, without activating any live transport."""


class GitHubTransportLiveV3Error(RuntimeError):
    """Fail-closed transport or authenticated observation failure."""
