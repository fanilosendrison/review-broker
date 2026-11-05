"""Explicit PREPARED transport budgets and scoped complete metadata pagination."""
from __future__ import annotations

from dataclasses import dataclass, fields
import json
import re
from typing import Callable, Iterable, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit
from urllib.request import Request

from .github_http_live_v3 import HttpResponseV3
from .remote_prepared_receipt_v3 import api_decimal_v3

BeforeEffectV3 = Callable[[], None]


@dataclass(frozen=True)
class PreparedArtifactBudgetV3:
    max_archive_bytes: int
    max_uncompressed_bytes: int
    max_members: int
    max_metadata_pages: int
    max_metadata_response_bytes: int

    def __post_init__(self):
        if any(type(getattr(self, f.name)) is not int or getattr(self, f.name) < 1 for f in fields(self)):
            raise ValueError("PREPARED_TRANSPORT_BUDGET_INVALID")


class PreparedMetadataExecutorV3(Protocol):
    """Injected authenticated HTTP boundary must stop reading at max_bytes, not truncate."""
    def __call__(self, request: Request, *, max_bytes: int) -> HttpResponseV3: ...


class PreparedStorageExecutorV3(Protocol):
    """HTTPS response stream, no redirect following, cookies, auth or network fallback."""
    def __call__(self, request: Request, *, max_bytes: int) -> Iterable[bytes]: ...


class PreparedMetadataReaderV3:
    def __init__(self, *, token: str, repository: str, executor: PreparedMetadataExecutorV3,
                 budget: PreparedArtifactBudgetV3):
        if (not isinstance(token, str) or not token or token.strip() != token
                or any(c in token for c in "\r\n")
                or re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is None
                or ".." in repository or type(budget) is not PreparedArtifactBudgetV3
                or not callable(executor)):
            raise ValueError("PREPARED_METADATA_CONFIGURATION_INVALID")
        self._token, self.repository, self.executor, self.budget = token, repository, executor, budget
        self.root = f"https://api.github.com/repos/{repository}"

    def get(self, suffix: str, before_effect: BeforeEffectV3) -> HttpResponseV3:
        if (suffix and not suffix.startswith("/")) or ".." in suffix or "#" in suffix or "//" in suffix:
            raise ValueError("PREPARED_METADATA_ENDPOINT_INVALID")
        request = Request(self.root + suffix, method="GET", headers={
            "Authorization": f"Bearer {self._token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        before_effect()
        try:
            response = self.executor(request, max_bytes=self.budget.max_metadata_response_bytes)
        except Exception:
            raise ValueError("PREPARED_METADATA_UNAVAILABLE") from None
        if (type(response) is not HttpResponseV3 or type(response.body) is not bytes
                or len(response.body) > self.budget.max_metadata_response_bytes):
            raise ValueError("PREPARED_METADATA_RESPONSE_BUDGET")
        before_effect()
        return response

    @staticmethod
    def object(response: HttpResponseV3) -> dict[str, object]:
        if response.status != 200:
            raise ValueError("PREPARED_METADATA_HTTP_FAILURE")
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result: raise ValueError("PREPARED_METADATA_DUPLICATE_FIELD")
                result[key] = value
            return result
        value = json.loads(response.body, object_pairs_hook=unique)
        if type(value) is not dict:
            raise ValueError("PREPARED_METADATA_OBJECT_REQUIRED")
        return value

    def listing(self, path: str, query: dict[str, str], field: str,
                before_effect: BeforeEffectV3) -> list[dict[str, object]]:
        """Every link is scope checked, including prev/first on a complete last page."""
        page, total, items, identifiers = 1, None, [], set()
        for _ in range(self.budget.max_metadata_pages):
            params = {**query, "per_page": "100", "page": str(page)}
            response = self.get(path + "?" + urlencode(params), before_effect)
            body = self.object(response)
            count, values = body.get("total_count"), body.get(field)
            if (type(count) is not int or count < 0 or type(values) is not list
                    or len(values) > 100 or any(type(v) is not dict for v in values)
                    or total is not None and total != count):
                raise ValueError("PREPARED_LIST_COUNT_INVALID")
            total = count
            for value in values:
                identifier = api_decimal_v3(value.get("id"))
                if identifier in identifiers:
                    raise ValueError("PREPARED_LIST_DUPLICATE")
                identifiers.add(identifier)
            items.extend(values)
            links = self._links(response.headers, path, query, page)
            next_page = links.get("next")
            if len(items) == total and next_page is None:
                return items
            if len(items) >= total or not values or next_page != page + 1:
                raise ValueError("PREPARED_LIST_INCOMPLETE")
            page = next_page
        raise ValueError("PREPARED_METADATA_PAGE_BUDGET")

    def _links(self, headers, path, query, current):
        values = [v for k, v in headers.items() if k.lower() == "link"]
        if len(values) > 1: raise ValueError("PREPARED_LINK_DUPLICATE")
        result = {}
        if not values: return result
        for part in values[0].split(","):
            match = re.fullmatch(r'\s*<([^>]+)>;\s*rel="(next|prev|first|last)"\s*', part)
            if match is None or match[2] in result:
                raise ValueError("PREPARED_LINK_INVALID")
            parsed = urlsplit(match[1])
            pairs = parse_qsl(parsed.query, keep_blank_values=True)
            params = dict(pairs)
            page = params.pop("page", None)
            if (parsed.scheme != "https" or parsed.netloc != "api.github.com"
                    or parsed.path != urlsplit(self.root + path).path or parsed.fragment
                    or len(pairs) != len(dict(pairs))
                    or params != {**query, "per_page": "100"}
                    or page is None or re.fullmatch(r"[1-9][0-9]*", page) is None):
                raise ValueError("PREPARED_LINK_SCOPE_INVALID")
            number = int(page)
            if ((match[2] == "next" and number != current + 1)
                    or (match[2] == "prev" and number != current - 1)
                    or (match[2] == "first" and number != 1)
                    or (match[2] == "last" and number < current)):
                raise ValueError("PREPARED_LINK_ORDER_INVALID")
            result[match[2]] = number
        return result
