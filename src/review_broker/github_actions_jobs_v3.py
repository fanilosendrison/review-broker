"""Complete authenticated Actions jobs pagination; shared by supported events."""
from __future__ import annotations

import re
from typing import Mapping
from urllib.parse import urlparse, parse_qs


class GitHubActionsJobsReaderV3:
    """Pagination methods of the Actions reader, extracted without semantic changes."""
    def _next_page(self, headers: Mapping[str, str], run_id: int,
                   run_attempt: int) -> int | None:
        from .github_actions_identity_v3 import GitHubActionsIdentityV3Error, _positive
        link = next((value for key, value in headers.items() if key.lower() == "link"), None)
        if link is None:
            return None
        next_links = [part.strip() for part in link.split(",") if 'rel="next"' in part]
        if len(next_links) != 1:
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_PAGINATION_INVALID")
        match = re.fullmatch(r"<([^>]+)>;\s*rel=\"next\"", next_links[0])
        if match is None:
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_PAGINATION_INVALID")
        parsed = urlparse(match.group(1))
        expected_path = (
            f"/repos/{self.repository}/actions/runs/{run_id}/attempts/{run_attempt}/jobs"
        )
        if (parsed.scheme != "https" or parsed.netloc != "api.github.com"
                or parsed.path != expected_path
                or parse_qs(parsed.query).get("per_page") != ["100"]):
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_PAGINATION_INVALID")
        page_values = parse_qs(parsed.query).get("page")
        if page_values is None or len(page_values) != 1 or not page_values[0].isdigit():
            raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_PAGINATION_INVALID")
        return _positive(int(page_values[0]), "GITHUB_ACTIONS_PAGINATION_INVALID")
    def _jobs(self, run_id: int, run_attempt: int) -> list[Mapping[str, object]]:
        from .github_actions_identity_v3 import GitHubActionsIdentityV3Error
        page = 1
        total: int | None = None
        jobs: list[Mapping[str, object]] = []
        while True:
            response = self._get(
                f"/actions/runs/{run_id}/attempts/{run_attempt}/jobs?per_page=100&page={page}"
            )
            if response.status != 200:
                raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_JOBS_UNAVAILABLE")
            body = self._json(response)
            observed_total = body.get("total_count")
            raw_jobs = body.get("jobs")
            if type(observed_total) is not int or observed_total < 0 or not isinstance(raw_jobs, list):
                raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_JOBS_INVALID")
            if total is None:
                total = observed_total
            if total != observed_total or any(not isinstance(job, dict) for job in raw_jobs):
                raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_JOBS_INCONSISTENT")
            jobs.extend(raw_jobs)
            next_page = self._next_page(response.headers, run_id, run_attempt)
            if len(jobs) < total:
                if next_page != page + 1 or not raw_jobs:
                    raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_PAGINATION_INCOMPLETE")
                page = next_page
                continue
            if len(jobs) != total or next_page is not None:
                raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_PAGINATION_INCONSISTENT")
            identifiers = [job.get("id") for job in jobs]
            if any(type(identifier) is not int or identifier < 1 for identifier in identifiers):
                raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_JOB_ID_INVALID")
            if len(identifiers) != len(set(identifiers)):
                raise GitHubActionsIdentityV3Error("GITHUB_ACTIONS_JOB_ID_DUPLICATE")
            return jobs
