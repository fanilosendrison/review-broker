"""RB91 standalone NON-NORMATIVE journal core qualification model.

No GitHub requests, production refs, OIDC, Codespace or Codex.
The implementation is intentionally restricted to core fields and excludes
embedded publication/retention/admission payloads pending a normative contract.
"""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import re
from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parents[1] / 'docs/architecture/qualification/rb91-jch-journal-v2-core.schema.json'
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
Draft202012Validator.check_schema(SCHEMA)
VALIDATOR = Draft202012Validator(SCHEMA)

try:
    from review_broker.identity import canonical_bytes as _canonical
    from review_broker.identity import attempt_identity as _attempt
    from review_broker.input_capacity import validate_capacity_receipt
    REAL_REPO_CONTRACT = True
except ImportError:
    # Offline fixture fallback restricted to strings, integers, lists, and maps.
    # Production comparisons and CI must use the actual pinned rfc8785 module.
    REAL_REPO_CONTRACT = False
    def _canonical(value):
        return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
    def _attempt(request_id, ordinal):
        return 'attempt:sha256:' + hashlib.sha256(_canonical({'ordinal':ordinal,'request_id':request_id})).hexdigest()
    def validate_capacity_receipt(value):
        # The schema plus exact domain checks below are synthetic-only offline.
        return 'artifact:sha256:' + hashlib.sha256(_canonical(value)+b'\n').hexdigest()

class ContractViolation(ValueError):
    pass

def fail(code):
    raise ContractViolation(code)

def digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()

def artifact(value):
    return 'artifact:sha256:' + hashlib.sha256(_canonical(value)+b'\n').hexdigest()

def parse_strict(raw:bytes):
    if not isinstance(raw,bytes) or len(raw)>524288:
        fail('J02_BAD_RAW_SIZE')
    def no_dups(pairs):
        x={}
        for key,value in pairs:
            if key in x:fail('J02_DUPLICATE_KEY')
            x[key]=value
        return x
    def bad_const(_):fail('J02_NONFINITE')
    try:
        value=json.loads(raw.decode('utf-8','strict'),object_pairs_hook=no_dups,parse_constant=bad_const)
    except (UnicodeError,ValueError,TypeError) as e:
        fail('J02_PARSE_FAILURE')
    if not isinstance(value,dict) or raw!=_canonical(value)+b'\n':
        fail('J02_NOT_CANONICAL')
    return value

TRANS={
    'REQUESTED':{'ADMITTED','INDETERMINATE'},
    'ADMITTED':{'PREPARED','INDETERMINATE'},
    'PREPARED':{'INDETERMINATE'},
    'ARMED':{'TERMINAL_CAPTURED','INDETERMINATE'},
    'TERMINAL_CAPTURED':{'VALIDATED','INDETERMINATE'},
    'VALIDATED':{'REPORTED','INDETERMINATE'},
    'REPORTED':{'STOPPED','INDETERMINATE'},
    'INDETERMINATE':{'STOPPED'},
    'STOPPED':set(),
}
ALLOWED_EVENTS={
    'INPUT_CAPACITY_ASSESSED':{'PREPARED'},
    'EVIDENCE_LOCATOR_PLANNED':{'TERMINAL_CAPTURED'},
    'EVIDENCE_LOCATOR_RECORDED':{'TERMINAL_CAPTURED','VALIDATED'},
    'PUBLICATION_RESERVED':{'VALIDATED'},
}


def validate(value):
    if not isinstance(value,dict) or type(value.get('schema_version')) is not int or value.get('schema_version')!=2:
        fail('J01_SCHEMA_DISPATCH_INVALID')
    err=next(iter(VALIDATOR.iter_errors(value)),None)
    if err is not None:
        fail('J02_SCHEMA_CLOSED_INVALID')
    if value['attempt_id']!=_attempt(value['request_id'],1):
        fail('J04_ATTEMPT_BINDING_INVALID')
    history=value['history']
    if history[0]!={'state':'REQUESTED','evidence_ids':[]}:
        fail('J12_HISTORY_ORIGIN_INVALID')
    stage='REQUESTED';flatten=[];arm_events=0;arm_seen=False
    for entry in history[1:]:
        if 'state' in entry:
            target=entry['state']
            if target not in TRANS.get(stage,set()) or not entry['evidence_ids']:
                fail('J12_ILLEGAL_STATE_EDGE')
            stage=target
        else:
            event=entry['event']
            if event=='ATOMIC_ARM_CONSUMED':
                if stage!='PREPARED' or arm_events:
                    fail('J09_DUPLICATE_OR_WRONG_ATOMIC_ARM')
                arm_events+=1
                stage='ARMED'
                binding=value['arm_binding']
                if binding is None or entry['binding_sha256']!=digest(binding):
                    fail('J12_ARM_HISTORY_BINDING_MISMATCH')
            elif event not in ALLOWED_EVENTS or stage not in ALLOWED_EVENTS[event]:
                fail('J12_ILLEGAL_EVENT_AT_STAGE')
        flatten.extend(entry['evidence_ids'])
    if value['state']!=stage or value['evidence_ids']!=flatten:
        fail('J12_HISTORY_STATE_EVIDENCE_MISMATCH')
    if arm_events not in (0,1):fail('J12_ARM_EVENT_COUNT_INVALID')
    if arm_events==0:
        if value['invocation_count']!=0 or value['arm_binding'] is not None:
            fail('J08_PREARM_CONSUMED_INVALID')
    else:
        if value['invocation_count']!=1 or value['arm_binding'] is None:
            fail('J08_ARMED_COUNT_BINDING_INVALID')
    cp=value.get('input_capacity')
    if cp is not None:
        if cp['request_id']!=value['request_id'] or cp['attempt_id']!=value['attempt_id']:
            fail('J04_CAPACITY_ID_MISMATCH')
        if cp['capacity_units']!=max(cp[k] for k in ('unicode_scalar_characters','utf16_code_units','utf8_bytes')):
            fail('J11_CAPACITY_UNITS_INVALID')
        expected_status='PASS' if cp['capacity_units']<=cp['max_chars'] else 'REJECTED'
        if cp['status']!=expected_status:fail('J11_CAPACITY_STATUS_INVALID')
        try:validate_capacity_receipt(cp)
        except Exception:fail('J11_EXISTING_CAPACITY_VALIDATION_FAILED')
        if not any(e.get('event')=='INPUT_CAPACITY_ASSESSED' and artifact(cp) in e['evidence_ids'] for e in history):
            fail('J12_CAPACITY_EVIDENCE_MISSING')
    if arm_events:
        b=value['arm_binding']
        if cp is None or cp['status']!='PASS':fail('J09_CAPACITY_NOT_PASS')
        if any(b[k]!=value[k] for k in ('request_id','attempt_id')):
            fail('J06_BINDING_REQUEST_MISMATCH')
        if b['input_sha256']!=cp['input_sha256'] or b['packet_id']!=cp['packet_id'] or b['capacity_receipt_id']!=artifact(cp):
            fail('J06_BINDING_CAPACITY_MISMATCH')
        if b['workflow_sha']!=cp['executing_broker_sha']:
            fail('J06_BINDING_WORKFLOW_MISMATCH')
    else:
        if cp is not None and value['state'] in ('REQUESTED','ADMITTED'):
            fail('J11_PREMATURE_CAPACITY')
    return value


def validate_transition(parent,child, *, parent_sha, operation):
    validate(parent);validate(child)
    if parent==child:fail('J13_WRITE_NOOP_FORBIDDEN')
    for f in ['schema_version','protocol_id','request_id','attempt_id']:
        if child[f]!=parent[f]:fail('J04_IDENTITY_CHANGED')
    if parent.get('input_capacity') is not None and child.get('input_capacity')!=parent['input_capacity']:
        fail('J11_CAPACITY_REPLACED')
    if parent.get('input_capacity') is None and child.get('input_capacity') is not None:
        if operation!='capacity' or parent['state']!='PREPARED' or child['state']!='PREPARED':
            fail('J11_CAPACITY_ADDED_WRONG_PHASE')
    if child['history'][:len(parent['history'])]!=parent['history'] or len(child['history'])!=len(parent['history'])+1:
        fail('J12_HISTORY_NOT_ONE_APPEND')
    if child['evidence_ids'][:len(parent['evidence_ids'])]!=parent['evidence_ids']:
        fail('J12_EVIDENCE_NOT_PREFIX')
    if operation=='atomic_arm':
        if parent['state']!='PREPARED' or parent['invocation_count']!=0 or parent['arm_binding'] is not None:
            fail('J09_NOT_PREPARED')
        if child['state']!='ARMED' or child['invocation_count']!=1:
            fail('J09_NOT_ATOMIC_COUNT1')
        if child['arm_binding']['prepared_parent_sha']!=parent_sha:
            fail('J07_PARENT_SHA_MISMATCH')
        if child['history'][-1].get('event')!='ATOMIC_ARM_CONSUMED':
            fail('J09_MISSING_ARM_EVENT')
    else:
        if parent['invocation_count']!=child['invocation_count']:
            fail('J08_UNAUTHORIZED_COUNT_CHANGE')
        if parent['arm_binding']!=child['arm_binding']:
            fail('J05_BINDING_CHANGED')
        last=child['history'][-1]
        if operation=='capacity' and last.get('event')!='INPUT_CAPACITY_ASSESSED':
            fail('J11_WRONG_CAPACITY_EVENT')
        if operation=='transition' and 'state' not in last:
            fail('J10_WRONG_TRANSITION_KIND')
        if operation=='metadata' and last.get('event') not in ALLOWED_EVENTS:
            fail('J12_WRONG_METADATA_EVENT')
        if operation not in {'capacity','transition','metadata'}:
            fail('J09_FORBIDDEN_OPERATION')
    for f in ['evidence_locator_plan','evidence_locator','publication_intent','publication_receipt']:
        if parent[f]!=child[f]:fail('CORE_SCOPE_METADATA_MUTATION_NOT_QUALIFIED')
    return True


def classify_get(*, return_code:int, http_status:int|None, body_valid:bool, authenticated:bool, repository_verified:bool):
    if return_code==0 and http_status==200 and body_valid and authenticated and repository_verified:
        return 'PRESENT_VERIFIED'
    if http_status==404 and authenticated and repository_verified:
        return 'ABSENT_AUTHENTICATED'
    return 'UNKNOWN'


def post_arm_gate(*, mutation_result, readback_ok:bool, exact_head:bool, original_live_controller:bool):
    # The only eligible path is a clean response PLUS a fresh exact readback by
    # the original controller. No attempt to categorize generic provider errors.
    if not isinstance(mutation_result,dict) or mutation_result.get('return_code')!=0 or mutation_result.get('errors'):
        return 'NO_MINT_NO_RETRY'
    data=mutation_result.get('data')
    if not isinstance(data,dict) or set(data)!={'updateRefs'}:
        return 'NO_MINT_NO_RETRY'
    update=data.get('updateRefs')
    if not isinstance(update,dict) or set(update)!={'clientMutationId'} or not isinstance(update.get('clientMutationId'),str):
        return 'NO_MINT_NO_RETRY'
    if not readback_ok or not exact_head or not original_live_controller:
        return 'NO_MINT_NO_RETRY'
    return 'ELIGIBLE_SINGLE_MINT'


def fixture_prepared():
    rid='request:sha256:'+'a'*64
    aid=_attempt(rid,1)
    intro=[{'state':'REQUESTED','evidence_ids':[]},{'state':'ADMITTED','evidence_ids':['artifact:sha256:'+'b'*64]},
           {'state':'PREPARED','evidence_ids':['artifact:sha256:'+'c'*64]}]
    return {'schema_version':2,'protocol_id':'j-ch-v1','request_id':rid,'attempt_id':aid,
        'state':'PREPARED','invocation_count':0,'history':intro,
        'evidence_ids':[i for e in intro for i in e['evidence_ids']],
        'arm_binding':None,'evidence_locator_plan':None,'evidence_locator':None,'publication_intent':None,'publication_receipt':None}


def fixture_capacity(prepared):
    x=deepcopy(prepared)
    raw=b'abc'
    cp={'schema_version':1,'evidence_type':'rendered-input-capacity-v1','request_id':x['request_id'],
        'attempt_id':x['attempt_id'],'packet_id':'packet:sha256:'+'d'*64,'executing_broker_sha':'e'*40,
        'runtime_distribution':'@openai/codex','runtime_version':'0.164.0','limit_policy':'codex-0.164.0-turn-input-v1',
        'max_chars':1048576,'counting_rule':'utf8-bytes-conservative-upper-bound-v1',
        'unicode_scalar_characters':3,'utf16_code_units':3,'utf8_bytes':3,'capacity_units':3,
        'input_sha256':hashlib.sha256(raw).hexdigest(),'status':'PASS'}
    x['input_capacity']=cp
    e={'event':'INPUT_CAPACITY_ASSESSED','evidence_ids':[artifact(cp)]}
    x['history'].append(e);x['evidence_ids'].extend(e['evidence_ids'])
    return x


def fixture_armed(prepared, *, parent_sha='1'*40):
    x=deepcopy(prepared)
    cp=x['input_capacity'];aid=x['attempt_id']
    b={
      'binding_version':1,'prepared_parent_sha':parent_sha,'challenge':'f'*64,
      'request_id':x['request_id'],'attempt_id':aid,'packet_id':cp['packet_id'],
      'input_sha256':cp['input_sha256'],'capacity_receipt_id':artifact(cp),
      'subject_id':'subject:sha256:'+'2'*64,'reviewer_policy_sha256':'3'*64,
      'reviewer_executable_sha256':'4'*64,'broker_repository_id':'1433701208',
      'workflow_ref':'fanilosendrison/review-broker/.github/workflows/review-request.yml@refs/heads/dev',
      'workflow_sha':cp['executing_broker_sha'],'controller_run_id':'42372558711',
      'controller_run_attempt':'1','codespace_name':'synthetic-codespace',
      'codespace_id':'53561573','launcher_program_sha256':'5'*64,'recipient_preflight_sha256':'6'*64
    }
    x['arm_binding']=b;x['state']='ARMED';x['invocation_count']=1
    e={'event':'ATOMIC_ARM_CONSUMED','protocol_id':'j-ch-v1','binding_sha256':digest(b),'invocation_count':1,
        'evidence_ids':['artifact:sha256:'+'7'*64]}
    x['history'].append(e);x['evidence_ids'].extend(e['evidence_ids'])
    return x


def fixture_transition(parent, target):
    x=deepcopy(parent);x['state']=target
    e={'state':target,'evidence_ids':['artifact:sha256:'+'8'*64]}
    x['history'].append(e);x['evidence_ids'].extend(e['evidence_ids'])
    return x