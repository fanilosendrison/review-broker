"""Bounded observational audit, not a validator or authorization to amend domains."""
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from jch_patterns import JCHValidator

ROOT=Path(__file__).resolve().parents[1]
SAMPLES={
    r'^[0-9a-f]{32}$':'a'*32,r'^[0-9a-f]{40}$':'a'*40,r'^[0-9a-f]{64}$':'a'*64,
    r'^[1-9][0-9]*$':'1',r'^[1-9][0-9]{0,19}$':'1',
    r'^[A-Za-z0-9-]{1,200}$':'sample',r'^[a-zA-Z0-9-]{1,200}$':'sample',
    r'^[A-Za-z0-9_-]+[.][A-Za-z0-9_-]+[.][A-Za-z0-9_-]+$':'a.b.c',
    r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$':'sample/broker',
    r'^[A-Za-z0-9_.-]{1,255}$':'sample',r'^[a-z][a-z0-9-]{0,63}$':'sample',
    r'^[a-z][a-z0-9_]*$':'sample',
    r'^[.]github/workflows/[A-Za-z0-9-]+[.]yml$':'.github/workflows/sample.yml',
    r'^(?!/)(?!.*(?:^|/)\.\.?/)(?!.*\\)[^\u0000-\u001f]+$':'sample.json',
    r'^https://github.com/[^/]+/[^/]+/issues/[1-9][0-9]*#issuecomment-[1-9][0-9]*$':
        'https://github.com/sample/broker/issues/1#issuecomment-1',
}
for prefix in ('artifact','attempt','mission','packet','policy','publication','request',
               'result','review-intent','subject'):
    SAMPLES['^'+prefix+':sha256:[0-9a-f]{64}$']=prefix+':sha256:'+'a'*64
SAMPLES['^sha256:[0-9a-f]{64}$']='sha256:'+'a'*64


def audit():
    entries=[];hashes={}
    def walk(value,pointer,name):
        if isinstance(value,dict):
            if 'pattern' in value:
                pattern=value['pattern'];sample=SAMPLES.get(pattern)
                if sample is None:raise ValueError('UNCLASSIFIED_PATTERN:'+pattern)
                validator=JCHValidator(value)
                historical=Draft202012Validator(value)
                if not validator.is_valid(sample):raise ValueError('INVALID_POSITIVE:'+pointer)
                outcomes={label:validator.is_valid(sample+suffix) for label,suffix in
                          [('LF','\n'),('CRLF','\r\n'),('TAB','\t'),('NUL','\x00')]}
                entries.append({'schema':name,'pointer':pointer,'constraints':value,
                                'positive':sample,'suffix_accepted':outcomes,
                                'historical_suffix_accepted':{label:historical.is_valid(sample+suffix)
                                    for label,suffix in [('LF','\n'),('CRLF','\r\n'),('TAB','\t'),('NUL','\x00')]},
                                'classification':'confirmed-lexical-gap' if any(outcomes.values())
                                else 'exact-against-tested-terminal-suffixes'})
            for key,item in value.items():walk(item,pointer+'/'+key.replace('~','~0').replace('/','~1'),name)
        elif isinstance(value,list):
            for index,item in enumerate(value):walk(item,pointer+'/'+str(index),name)
    for path in sorted((ROOT/'schemas').glob('jch-*.schema.json')):
        raw=path.read_bytes();hashes[path.name]=hashlib.sha256(raw).hexdigest()
        walk(json.loads(raw),'',path.name)
    gaps=sum(e['classification']=='confirmed-lexical-gap' for e in entries)
    return {'scope':'all pattern occurrences in eight proposed J-CH schema resources',
            'boundary':'26 qualified ECMA-262 expressions only; not semantic/authentication bypass evidence.',
            'dialect':'ECMA-262, no flags; local closed-catalogue adapter qualified against native Node RegExp',
            'distinct_patterns':len({e['constraints']['pattern'] for e in entries}),
            'overall':'FAIL_NON_CHALLENGE_LEXICAL_DOMAINS' if gaps else 'NO_TESTED_SUFFIX_GAP',
            'schema_sha256':hashes,'occurrences':len(entries),'confirmed_gaps':gaps,'entries':entries}


if __name__=='__main__':
    print(json.dumps(audit(),indent=2,ensure_ascii=True))
