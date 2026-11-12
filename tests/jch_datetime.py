"""Offline RFC3339 leap-event adapter; never an observation-time authenticator."""
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import re

DATA=Path(__file__).parent/'fixtures'/'iana-leap-seconds.list'
DATA_SHA256='db5a895f16853b03bfc865e8d68f9fc8710ef1740e3400c701cd46a5bbbc3433'
NTP_EPOCH=datetime(1900,1,1,tzinfo=timezone.utc)
# Only the missing leap-second branch. Ordinary grammar remains library-owned.
LEAP=re.compile(r'([0-9]{4})-([0-9]{2})-([0-9]{2})[Tt]'
                r'([0-9]{2}):([0-9]{2}):60(?:[.][0-9]+)?'
                r'([Zz]|[+-][0-9]{2}:[0-9]{2})')


class LeapSecondCoverageError(ValueError):
    """The pinned external facts cannot establish this leap-event assertion."""


def leap_seconds():
    """Read the exact public-domain IANA/IERS NTP table, without network refresh."""
    try:
        raw=DATA.read_bytes()
    except OSError as exc:
        raise LeapSecondCoverageError('LEAP_SECOND_DATA_UNAVAILABLE') from exc
    if hashlib.sha256(raw).hexdigest()!=DATA_SHA256:
        raise LeapSecondCoverageError('LEAP_SECOND_DATA_IDENTITY')
    rows=[];expires=None
    for line in raw.decode('ascii').splitlines():
        if line.startswith('#@'):expires=int(line[2:].strip())
        fields=line.partition('#')[0].split()
        if fields:
            if len(fields)!=2 or not all(v.isascii() and v.isdecimal() for v in fields):
                raise LeapSecondCoverageError('LEAP_SECOND_DATA_SHAPE')
            rows.append(tuple(map(int,fields)))
    if not rows or rows[0]!=(2272060800,10) or expires is None or expires<=rows[-1][0]:
        raise LeapSecondCoverageError('LEAP_SECOND_DATA_COVERAGE')
    positive=set();negative=set()
    for (previous,offset),(instant,next_offset) in zip(rows,rows[1:]):
        if instant<=previous or instant%86400 or abs(next_offset-offset)!=1:
            raise LeapSecondCoverageError('LEAP_SECOND_DATA_TRANSITION')
        (positive if next_offset>offset else negative).add(instant)
    return rows[0][0],expires,frozenset(positive),frozenset(negative)


def complete_date_time(value, ordinary):
    """Preserve the input; compare an explicit :60 event, not a substituted date."""
    if not isinstance(value,str):return ordinary(value)
    if '\n' in value:return False
    if ordinary(value):return True
    match=LEAP.fullmatch(value)
    if match is None:return False
    year,month,day,hour,minute=map(int,match.groups()[:5]);zone=match[6]
    try:
        # This is the start of the containing minute, not a parsed/normalized
        # replacement timestamp. :60 and all fraction digits remain untouched.
        minute_start=datetime(year,month,day,hour,minute,tzinfo=timezone.utc)
        offset=0
        if zone not in ('Z','z'):
            hours=int(zone[1:3]);minutes=int(zone[4:6])
            if hours>23 or minutes>59:return False
            offset=(hours*60+minutes)*(1 if zone[0]=='+' else -1)
        boundary=minute_start-timedelta(minutes=offset)+timedelta(minutes=1)
    except (ValueError,OverflowError):return False
    seconds=int((boundary-NTP_EPOCH).total_seconds())
    start,expires,positive,negative=leap_seconds()
    if negative:
        # This adapter has no qualified negative-leap ordinary-second path.
        raise LeapSecondCoverageError('NEGATIVE_LEAP_SUPPORT_UNQUALIFIED')
    if not start<seconds<=expires:
        raise LeapSecondCoverageError('LEAP_SECOND_OUTSIDE_PINNED_COVERAGE')
    return seconds in positive


def qualify_complete_checker(checker):
    """Require known positive and negative evidence on the actual local checker."""
    for value in ('1990-12-31T23:59:60Z','1990-12-31T15:59:60-08:00',
                  '1991-01-01T00:59:60+01:00','1990-12-31t23:59:60.123z'):
        if not checker.conforms(value,'date-time'):
            raise ValueError('DATE_TIME_ASSERTION_INCOMPLETE')
    for value in ('1990-12-30T23:59:60Z','1990-12-31T12:00:60Z',
                  '1990-12-31T23:59:61Z','1990-12-31T15:59:60+08:00',
                  '1990-12-31T23:59:60Z\n'):
        if checker.conforms(value,'date-time'):
            raise ValueError('DATE_TIME_ASSERTION_PERMISSIVE')
