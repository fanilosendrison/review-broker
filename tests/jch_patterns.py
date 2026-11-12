"""Local Draft2020-12 pattern adapter for the closed, qualified J-CH catalogue.

No general ECMA-to-Python translator is claimed. The 26 exact expressions use
ASCII classes/ranges, literal escapes, quantifiers, anchors and negative lookahead.
The catalogue's path guard and comment URL use wildcard dots; those exclude
all four ECMAScript LineTerminators. Fullmatch supplies ECMAScript's non-multiline
end assertion rather than Python dollar's extra before-final-LF match.
"""
from copy import deepcopy
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator, ValidationError, validators
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

CATALOGUE=tuple(json.loads((Path(__file__).parent/'fixtures'/'jch-pattern-catalogue.json').read_text()))
PATH_PATTERN=r'^(?!/)(?!.*(?:^|/)\.\.?/)(?!.*\\)[^\u0000-\u001f]+$'
if len(CATALOGUE)!=26 or len(set(CATALOGUE))!=26:
    raise ValueError('JCH_PATTERN_CATALOGUE_INVALID')
COMMENT_PATTERN=r'^https://github.com/[^/]+/[^/]+/issues/[1-9][0-9]*#issuecomment-[1-9][0-9]*$'
JS_DOT=r'[^\n\r\u2028\u2029]'
COMPILED={pattern:re.compile(
          pattern.replace('.*',JS_DOT+'*') if pattern==PATH_PATTERN else
          pattern.replace('github.com','github'+JS_DOT+'com') if pattern==COMMENT_PATTERN else
          pattern,re.ASCII) for pattern in CATALOGUE}


def matches(pattern,value):
    if pattern not in COMPILED:raise ValueError('JCH_PATTERN_NOT_QUALIFIED')
    return COMPILED[pattern].fullmatch(value) is not None


def pattern_keyword(validator,pattern,instance,schema):
    if pattern not in COMPILED:raise ValueError('JCH_PATTERN_NOT_QUALIFIED')
    if validator.is_type(instance,'string') and not matches(pattern,instance):
        yield ValidationError(f'{instance!r} does not match qualified pattern {pattern!r}')


JCHValidator=validators.extend(Draft202012Validator,{'pattern':pattern_keyword})


def qualified_resources(resources):
    """Pin each dialect, preserving constraints and local keyword evaluation at refs.

jsonschema's evolve selects its global validator for an explicit $schema. The
private evaluation copies omit ONLY that already-checked root dialect marker,
with referencing explicitly bound to the same DRAFT202012 specification. Original
public bytes, IDs, annotations and every validation constraint remain unchanged.
No global validator registration or historical resource mutation takes place.
"""
    def inspect(value):
        if isinstance(value,dict):
            if 'pattern' in value and value['pattern'] not in COMPILED:
                raise ValueError('JCH_PATTERN_NOT_QUALIFIED')
            if '$schema' in value:
                raise ValueError('JCH_NESTED_DIALECT_NOT_QUALIFIED')
            for item in value.values():inspect(item)
        elif isinstance(value,list):
            for item in value:inspect(item)
    evaluated={}
    for name,source in resources.items():
        Draft202012Validator.check_schema(source)
        value=deepcopy(source)
        if value.pop('$schema',None)!='https://json-schema.org/draft/2020-12/schema':
            raise ValueError('JCH_DIALECT_NOT_QUALIFIED')
        inspect(value);evaluated[name]=value
    registry=Registry().with_resources((value['$id'],Resource.from_contents(value,
                      default_specification=DRAFT202012)) for value in evaluated.values())
    return evaluated,registry
