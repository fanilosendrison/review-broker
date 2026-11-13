"""Read-only validation/rendering of the repository ADR convention.

This is documentation governance tooling, not broker execution or adoption.
Heterogeneous YAML/JSON values are admitted only after closed-schema checks.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
import yaml


class ADRProfileError(ValueError):
    pass


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node):
    pairs=loader.construct_pairs(node,deep=True);value={}
    for key,item in pairs:
        if key in value:raise ADRProfileError('DUPLICATE_YAML_KEY')
        value[key]=item
    return value


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,unique_mapping)


@dataclass(frozen=True)
class ADR:
    path: Path
    metadata: dict
    decision_body: bytes


def calendar_checker():
    checker=FormatChecker()
    if 'date' not in checker.checkers:raise ADRProfileError('DATE_ASSERTION_UNAVAILABLE')
    if not checker.conforms('2024-02-29','date'):raise ADRProfileError('DATE_ASSERTION_BROKEN')
    for invalid in ('2025-02-29','2026-02-30','2026-13-01','2026-00-01','2026-01-00'):
        if checker.conforms(invalid,'date'):raise ADRProfileError('DATE_ASSERTION_PERMISSIVE')
    return checker


def read_adr(path, validator, profile):
    raw=path.read_bytes()
    if raw.startswith(b'\xef\xbb\xbf') or b'\r' in raw or not raw.startswith(b'---\n'):
        raise ADRProfileError('ADR_BYTES_INVALID')
    text=raw.decode('utf-8','strict');parts=text.split('---\n',2)
    if len(parts)!=3:raise ADRProfileError('ADR_FRONTMATTER_INVALID')
    metadata=yaml.load(parts[1],Loader=UniqueLoader)
    validator.validate(metadata)
    match=re.search(rb'^## Context(?: |$)',raw,re.M)
    if match is None:raise ADRProfileError('ADR_CONTEXT_MISSING')
    body=raw[match.start():]
    if hashlib.sha256(body).hexdigest()!=metadata['decision_body_sha256']:
        raise ADRProfileError('ADR_BODY_HASH_MISMATCH')
    identifier=metadata['id'];number=identifier.split('-')[1]
    if not re.fullmatch(profile['filename_pattern'],path.name) or not path.name.startswith('adr-'+number+'-'):
        raise ADRProfileError('ADR_FILENAME_INVALID')
    expected='# '+identifier+profile['h1_separator']+metadata['name']
    headings=[line for line in parts[2].splitlines() if line.startswith('# ')]
    if headings!=[expected]:raise ADRProfileError('ADR_H1_INVALID')
    return ADR(path,metadata,body)


def load_adrs(root):
    directory=Path(root)/'docs/adr';profile=yaml.load((directory/'adr-profile.yaml').read_text(),Loader=UniqueLoader)
    source=profile['shared_profile'];base_raw=(directory/source['vendored_path']).read_bytes()
    if hashlib.sha256(base_raw).hexdigest()!=source['sha256']:raise ADRProfileError('ADR_SCHEMA_PROVENANCE')
    if source['commit']!='aa84e816385f082ea353b6254e490d85fe17bceb' or source['version']!='0.1.0':
        raise ADRProfileError('ADR_SCHEMA_PIN_CHANGED')
    base=json.loads(base_raw);local=json.loads((directory/profile['local_schema']).read_text())
    if base['$id']!=source['id']:raise ADRProfileError('ADR_SCHEMA_ID')
    for schema in (base,local):Draft202012Validator.check_schema(schema)
    registry=Registry().with_resource(base['$id'],Resource.from_contents(base))
    validator=Draft202012Validator(local,registry=registry,format_checker=calendar_checker())
    records=[read_adr(path,validator,profile) for path in sorted(directory.glob(profile['records']))]
    ids=[record.metadata['id'] for record in records]
    if len(ids)!=len(set(ids)):raise ADRProfileError('ADR_DUPLICATE_ID')
    if ids!=['ADR-'+str(i).zfill(3) for i in range(1,len(ids)+1)]:raise ADRProfileError('ADR_ID_RETENTION_GAP')
    for record in records:
        for targets in record.metadata['relations'].values():
            if any(target not in ids or target==record.metadata['id'] for target in targets):
                raise ADRProfileError('ADR_RELATION_TARGET')
    if profile['legacy_without_frontmatter'] or profile['legacy_null_dates']:
        raise ADRProfileError('UNAUTHORIZED_LEGACY_ALLOWLIST')
    return profile,records


def assert_transition(previous, current, profile):
    before,after=previous.metadata,current.metadata
    if before['id']!=after['id']:raise ADRProfileError('ADR_ID_REUSE')
    if before['status']!=after['status'] and after['status'] not in profile['lifecycle'][before['status']]:
        raise ADRProfileError('ADR_LIFECYCLE_INVALID')
    if before['status']!='proposed':
        if previous.decision_body!=current.decision_body:
            raise ADRProfileError('ADR_ACCEPTED_BODY_CHANGED')
        if {k:v for k,v in before.items() if k!='status'}!={k:v for k,v in after.items() if k!='status'}:
            raise ADRProfileError('ADR_ACCEPTED_METADATA_CHANGED')


def render_index(root):
    profile,records=load_adrs(root)
    lines=['---','okf_version: "1.0"','kind: "KnowledgeAsset"','asset_type: "generated-index"',
        'domain: "independent-review"','severity: "guideline"','name: "Review Broker ADR Index"',
        'version: "0.1.0"','adoption_status: "'+profile['status']+'"','---','','# Review Broker ADRs','',
        'Generated from canonical outgoing metadata. Profile status: '+profile['status']+'.',
        'Validation/rendering performs no acceptance transition or runtime admission.',
        'Accepted metadata on the integration branch is a proposal until the',
        'owner-authorized merge into dev. It grants no operational admission.','',
        'After acceptance, identity/date/relations/governs and Context-through-EOF bytes',
        'are immutable. Only declared lifecycle transitions may change status. Retain',
        'all allocated records; never reuse IDs. Reverse relations below are derived.','',
        '| ID | Status | Decision | Date | Incoming |','| -- | ------ | -------- | ---- | -------- |']
    for record in records:
        m=record.metadata;incoming=[]
        for other in records:
            for relation,targets in other.metadata['relations'].items():
                if m['id'] in targets:incoming.append(other.metadata['id']+' '+relation)
        title=m['name'].replace('|',r'\|').replace('[',r'\[').replace(']',r'\]')
        lines.append('| '+m['id']+' | '+m['status']+' | ['+title+']('+record.path.name+') | '+m['date']+' | '+(', '.join(incoming) or 'None')+' |')
    return '\n'.join(lines)+'\n'
