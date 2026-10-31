"""Fixed-origin, redirect-rejecting HTTP execution for the live v3 transport."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class GitHubHttpLiveV3Error(RuntimeError):
    """A sanitized HTTP transport failure."""


@dataclass(frozen=True)
class HttpResponseV3:
    status: int
    body: bytes
    headers: Mapping[str, str]


HttpExecutorV3 = Callable[[Request], HttpResponseV3]


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        raise GitHubHttpLiveV3Error("GITHUB_REDIRECT_REJECTED")


def urllib_executor_bounded(request: Request, maximum_body_bytes: int) -> HttpResponseV3:
    failed = False
    result: HttpResponseV3 | None = None
    try:
        with build_opener(_RejectRedirects()).open(request, timeout=30) as response:
            body = response.read(maximum_body_bytes + 1)
            if len(body) > maximum_body_bytes: raise GitHubHttpLiveV3Error("GITHUB_RESPONSE_TOO_LARGE")
            result = HttpResponseV3(response.status, body, dict(response.headers.items()))
    except HTTPError as exc:
        body = exc.read(maximum_body_bytes + 1)
        if len(body) > maximum_body_bytes: raise GitHubHttpLiveV3Error("GITHUB_RESPONSE_TOO_LARGE")
        result = HttpResponseV3(exc.code, body, dict(exc.headers.items()) if exc.headers else {})
    except (URLError, OSError, GitHubHttpLiveV3Error):
        failed = True
    if failed or result is None:
        raise GitHubHttpLiveV3Error("GITHUB_TRANSPORT_UNAVAILABLE")
    return result


def urllib_executor(request: Request) -> HttpResponseV3:
    return urllib_executor_bounded(request, 16_000_000)
