"""Ordered authenticated git_file acquisition for candidate v3 admission."""
from __future__ import annotations
from typing import Mapping

from .github_git_file_v3 import GitHubGitFileObservationV3, GitHubGitFileReaderV3
from .physical import decode_physical_lines


class GitFileAdmissionV3Error(ValueError):
    pass


def acquire_git_file_admissions_v3(request: Mapping[str, object], subject: Mapping[str, object],
                                   readers: Mapping[str, GitHubGitFileReaderV3] | None,
                                   authority_evidence_id: str, installation_id: int,
                                   rendered_budget: int
                                   ) -> tuple[GitHubGitFileObservationV3, ...]:
    observations: list[GitHubGitFileObservationV3] = [];rendered=0
    for reference in request["references"]:
        if reference["source"]["kind"] != "git_file": continue
        reader = None if readers is None else readers.get(reference["id"])
        if type(reader) is not GitHubGitFileReaderV3:
            raise GitFileAdmissionV3Error("GIT_FILE_TRUSTED_READER_REQUIRED")
        selector = reference["source"]
        try: observed = reader.observe(selector["commit"], selector["path"], selector.get("expected_sha256"))
        except Exception: raise GitFileAdmissionV3Error("GIT_FILE_OBSERVATION_UNAVAILABLE") from None
        if (observed.qualification != "AUTHENTICATED_READ_ONLY"
                or observed.authority_evidence_id != authority_evidence_id
                or observed.installation_id != installation_id):
            raise GitFileAdmissionV3Error("GIT_FILE_SOURCE_AUTHORITY_MISMATCH")
        if observed.repository != subject["repository"] or observed.repository_id != subject["repository_id"]:
            raise GitFileAdmissionV3Error("GIT_FILE_REPOSITORY_IDENTITY_MISMATCH")
        if request["atomicity"] is True and observed.commit_sha != subject["expected_head_commit"]:
            raise GitFileAdmissionV3Error("GIT_FILE_ATOMICITY_HEAD_MISMATCH")
        rendered+=sum(len(line.encode("utf-8"))+9 for line in decode_physical_lines(observed.original_bytes)[1])
        if rendered>rendered_budget: raise GitFileAdmissionV3Error("EVENTUAL_RENDERED_PACKET_EXCEEDED")
        observations.append(observed)
    return tuple(observations)
