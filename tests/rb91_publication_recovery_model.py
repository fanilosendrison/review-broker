"""Bounded publication-ownership model; no production journal/publisher changes.

The real GitHubPublisher supplies pagination/transport; the oracle intentionally
restates v2 creator-only semantics independently. Nothing here launches a model.
"""
from copy import deepcopy
import hashlib
import json
import threading

from review_broker.identity import canonical_bytes
from review_broker.publication import GitHubPublisher, render_result_comment
from rb91_full_abi_model import validate_transition
from rb91_jch_contract_model import artifact, fixture_transition
from rb91_storage_provenance_model import verify_storage, instant


def validate_comment_attribution(comment, repository, issue_number):
    try:
        identifier = comment['id']
        if type(identifier) is not int or identifier < 1:
            raise ValueError
        if not isinstance(comment['node_id'],str) or not comment['node_id']:
            raise ValueError
        expected = f'https://github.com/{repository}/issues/{issue_number}#issuecomment-{identifier}'
        if comment['html_url'] != expected:
            raise ValueError
        if 'issue_url' in comment and comment['issue_url'] != f'https://api.github.com/repos/{repository}/issues/{issue_number}':
            raise ValueError
        if 'url' in comment and comment['url'] != f'https://api.github.com/repos/{repository}/issues/comments/{identifier}':
            raise ValueError
        instant(comment['created_at'])
    except (KeyError,TypeError,ValueError,AttributeError):
        raise ValueError('PUBLICATION_ATTRIBUTION_CONTRADICTION') from None


class PublicationStore:
    def __init__(self, validated):
        self.record = deepcopy(validated)
        self.lock = threading.Lock()
        self.permissions = set()
        self.attempted = set()

    def reserve(self, candidate, policy, *, token, issuer_reader, runner, destination, lose_ack=False):
        candidate = deepcopy(candidate)
        with self.lock:
            if self.record['publication_intent'] is not None:
                return None
        verify_storage(candidate,policy,token=token,issuer_reader=issuer_reader,runner=runner,destination=destination)
        with self.lock:
            if self.record['publication_intent'] is not None:
                return None
            validate_transition(self.record,candidate,parent_sha='b'*40,operation='metadata')
            self.record = deepcopy(candidate)
            # Opaque in-process creator capability, never a journal nonce or a JWT.
            if lose_ack:
                return None
            permission = object()
            self.permissions.add(permission)
            return permission

    def post(self, permission, raw, runner):
        with self.lock:
            if permission not in self.permissions or permission in self.attempted:
                raise ValueError('NO_PUBLICATION_CREATOR_PERMISSION')
            intent = deepcopy(self.record['publication_intent'])
        if self.observe(raw,runner):
            return True
        with self.lock:
            if permission in self.attempted:
                raise ValueError('NO_PUBLICATION_CREATOR_PERMISSION')
            if self.record['state'] == 'REPORTED':
                raise ValueError('PUBLICATION_RECEIPT_UNOBSERVED')
            self.attempted.add(permission)
        publisher = GitHubPublisher(intent['result_artifact']['location']['broker_repository'],runner=runner)
        body = render_result_comment(json.loads(raw),publication_id=intent['publication_id'])
        if hashlib.sha256(body.encode()).hexdigest() != intent['comment_body_sha256']:
            raise ValueError('PUBLICATION_BYTES')
        # Attempt flag precedes effect. Lost reply, timeout or process death cannot reset it.
        publisher._json('POST',f"repos/{publisher.repository}/issues/{intent['issue_number']}/comments",{'body':body},check=False)
        return self.observe(raw,runner)

    def observe(self, raw, runner):
        intent = self.record['publication_intent']
        if intent is None:
            raise ValueError('NO_PUBLICATION_INTENT')
        publisher = GitHubPublisher(intent['result_artifact']['location']['broker_repository'],runner=runner)
        body = render_result_comment(json.loads(raw),publication_id=intent['publication_id'])
        if hashlib.sha256(body.encode()).hexdigest() != intent['comment_body_sha256']:
            raise ValueError('PUBLICATION_BYTES')
        matches = []
        for comment in publisher.comments(intent['issue_number']):
            actor = comment.get('user')
            if not isinstance(actor,dict):
                continue
            observed = {key:actor.get(key) for key in ('login','id')}
            if comment.get('body') == body and canonical_bytes(observed) == canonical_bytes(intent['publisher']):
                validate_comment_attribution(comment,publisher.repository,intent['issue_number'])
                matches.append(comment)
        if len(matches) > 1:
            raise ValueError('DUPLICATE_PUBLICATION_INCIDENT')
        if not matches:
            return False
        comment = matches[0]
        receipt = dict(schema_version=1,evidence_type='github-result-publication-observation',
            publication_id=intent['publication_id'],result_id=intent['result_id'],issue_number=intent['issue_number'],
            publisher=intent['publisher'],comment_id=comment['id'],comment_node_id=comment['node_id'],
            comment_url=comment['html_url'],comment_created_at=comment['created_at'],observed_at=comment['created_at'])
        with self.lock:
            if self.record['state'] == 'REPORTED':
                prior = self.record['publication_receipt']
                fields = tuple(key for key in receipt if key != 'observed_at')
                if canonical_bytes({k:receipt[k] for k in fields}) != canonical_bytes({k:prior[k] for k in fields}):
                    raise ValueError('PUBLICATION_RECEIPT_CHANGED')
                return True
            reported = fixture_transition(self.record,'REPORTED')
            reported['publication_receipt'] = receipt
            reported['history'][-1]['evidence_ids'] = [artifact(receipt)]
            reported['evidence_ids'][-1] = artifact(receipt)
            validate_transition(self.record,reported,parent_sha='c'*40,operation='transition')
            self.record = reported
        return True
