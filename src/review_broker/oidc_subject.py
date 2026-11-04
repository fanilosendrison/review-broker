"""Pure immutable GitHub subject construction from independently trusted context."""
import re

BROKER_REPOSITORY = "fanilosendrison/review-broker"
BROKER_REPOSITORY_ID = "1433701208"
BROKER_OWNER_ID = "30498238"
BROKER_REF = "refs/heads/dev"


def immutable_repository_subject(
    repository: str,
    repository_id: str,
    owner_id: str,
    ref: str,
) -> str:
    """Reject ambiguous context; never normalize names or infer identity from a JWT."""
    if (any(type(value) is not str for value in (repository, repository_id, owner_id, ref))
        or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository)
        or not re.fullmatch(r'[1-9][0-9]*', repository_id)
        or not re.fullmatch(r'[1-9][0-9]*', owner_id)
        or ref != BROKER_REF):
        raise ValueError("OIDC_IMMUTABLE_SUBJECT_CONTEXT_INVALID")
    owner, name = repository.split('/')
    return f'repo:{owner}@{owner_id}/{name}@{repository_id}:ref:{ref}'
