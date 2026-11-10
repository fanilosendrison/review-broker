"""Bounded non-redirecting live Artifact reads; GitHub and storage openers are separate."""
from __future__ import annotations

from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .github_http_live_v3 import HttpResponseV3


class _ObserveRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Return the redirect response to the metadata reader, never follow it.
        return None


class GitHubActionsArtifactHttpV3:
    def __init__(self, *, before_effect, opener_factory=build_opener):
        if not callable(before_effect):
            raise ValueError("ARTIFACT_HTTP_GUARD_REQUIRED")
        self.before_effect, self.opener_factory = before_effect, opener_factory

    def metadata(self, request: Request, *, max_bytes: int) -> HttpResponseV3:
        parsed = urlsplit(request.full_url)
        if (parsed.scheme != "https" or parsed.netloc != "api.github.com"
                or request.get_method() != "GET" or request.data is not None
                or not parsed.path.startswith("/repos/fanilosendrison/review-broker")
                or type(max_bytes) is not int or max_bytes < 1):
            raise ValueError("ARTIFACT_HTTP_METADATA_REQUEST_INVALID")
        self.before_effect()
        response = None
        try:
            try:
                response = self.opener_factory(_ObserveRedirect()).open(request, timeout=30)
            except HTTPError as error:
                response = error
            with response:
                raw = response.read(max_bytes + 1)
                if len(raw) > max_bytes:
                    raise ValueError("ARTIFACT_HTTP_METADATA_BUDGET")
                return HttpResponseV3(response.code, raw, dict(response.headers.items()))
        except TimeoutError:
            raise TimeoutError("ARTIFACT_HTTP_TIMEOUT") from None
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise TimeoutError("ARTIFACT_HTTP_TIMEOUT") from None
            raise ValueError("ARTIFACT_HTTP_UNAVAILABLE") from None
        except Exception:
            raise ValueError("ARTIFACT_HTTP_UNAVAILABLE") from None

    def storage(self, request: Request, *, max_bytes: int):
        if (dict(request.header_items()) or request.get_method() != "GET"
                or request.data is not None or type(max_bytes) is not int or max_bytes < 1):
            raise ValueError("ARTIFACT_HTTP_STORAGE_REQUEST_INVALID")
        self.before_effect()
        try:
            # A new opener has no API credential, cookie store or redirect following.
            with self.opener_factory(_ObserveRedirect()).open(request, timeout=30) as response:
                if response.code != 200:
                    raise ValueError("ARTIFACT_HTTP_STORAGE_STATUS_INVALID")
                count = 0
                while True:
                    self.before_effect()
                    chunk = response.read(min(65536, max_bytes - count + 1))
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > max_bytes:
                        raise ValueError("ARTIFACT_HTTP_STORAGE_BUDGET")
                    yield chunk
        except TimeoutError:
            raise TimeoutError("ARTIFACT_HTTP_TIMEOUT") from None
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise TimeoutError("ARTIFACT_HTTP_TIMEOUT") from None
            raise ValueError("ARTIFACT_HTTP_UNAVAILABLE") from None
        except Exception:
            raise ValueError("ARTIFACT_HTTP_UNAVAILABLE") from None
