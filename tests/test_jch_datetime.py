"""Independent RFC3339 vectors against the actual six proposed schema sites."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from jch_normative_fixtures import workload, quiescence
from jch_normative_schemas import RESOURCES, check, qualified_format_checker
from jch_datetime import DATA, LeapSecondCoverageError, leap_seconds


class DateTimeConformanceTests(unittest.TestCase):
    def test_required_positive_and_negative_vectors_preserve_wire_bytes(self):
        receipt=quiescence(workload()[2])
        positives=('1990-12-31T23:59:60Z','1990-12-31T15:59:60-08:00',
                   '1991-01-01T00:59:60+01:00','2024-02-29T00:00:00Z',
                   '1985-04-12T23:20:50.52Z','1990-12-31t23:59:60.123z',
                   '1990-12-31T23:59:60-00:00')
        negatives=('1990-12-30T23:59:60Z','1990-12-31T12:00:60Z',
                   '1990-12-31T23:59:61Z','2026-11-12T23:59:60Z',
                   '2026-02-30T00:00:00Z','1990-12-31T23:59:60Z\n',
                   '1990-12-31T15:59:60+08:00','1991-01-01T00:59:60-01:00',
                   '1990-12-31T23:59:60+24:00','1990-12-31T23:59:60+00:60',
                   '1900-02-29T23:59:60Z','1990-13-31T23:59:60Z',
                   '1990-12-00T23:59:60Z','10000-12-31T23:59:60Z',
                   '1990-12-31T24:59:60Z','1990-12-31T23:60:60Z',
                   '1990-12-31T23:59:60.Z','1990-12-31T23:59:60,1Z',
                   '1990-12-31 23:59:60Z','1990-12-31T23:59:60',
                   '１９９０-12-31T23:59:60Z')
        for valid,values in ((True,positives),(False,negatives)):
            for value in values:
                wire=json.dumps(dict(receipt,observed_at=value));decoded=json.loads(wire)
                with self.subTest(value=value):
                    if valid:check('jch-quiescence-v1.schema.json',decoded)
                    else:
                        with self.assertRaises(ValidationError):check('jch-quiescence-v1.schema.json',decoded)
                    self.assertEqual(json.dumps(decoded),wire)

    def test_same_leap_event_at_every_minute_offset(self):
        checker=qualified_format_checker()
        utc_minute=datetime(1990,12,31,23,59)
        for minutes in range(-1439,1440):
            local=utc_minute+timedelta(minutes=minutes)
            sign='+' if minutes>=0 else '-';hours,minute=divmod(abs(minutes),60)
            value=local.strftime('%Y-%m-%dT%H:%M:')+f'60{sign}{hours:02}:{minute:02}'
            with self.subTest(offset=minutes):
                self.assertTrue(checker.conforms(value,'date-time'))
                wrong=(local+timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:')+f'60{sign}{hours:02}:{minute:02}'
                self.assertFalse(checker.conforms(wrong,'date-time'))

    def test_six_actual_schema_sites_types_lengths_and_suffixes(self):
        journal=RESOURCES['jch-journal-v2.schema.json']['$defs']
        sites=[journal[owner]['properties'][field] for owner,field in
               [('locator','created_at'),('locator','expires_at'),('intent','reserved_at'),
                ('receipt','comment_created_at'),('receipt','observed_at')]]
        sites.append(RESOURCES['jch-quiescence-v1.schema.json']['properties']['observed_at'])
        self.assertEqual(len(sites),6)
        checker=qualified_format_checker()
        for schema in sites:
            validator=Draft202012Validator(schema,format_checker=checker)
            for value in ('1990-12-31T23:59:60Z','1990-12-31T23:59:60.'+'1'*19+'Z'):
                self.assertLessEqual(len(value),40);validator.validate(value)
            for value in (None,True,1,1.0,[],{},'1990-12-31T23:59:60.'+'1'*20+'Z'):
                with self.subTest(value=value),self.assertRaises(ValidationError):validator.validate(value)
            for suffix in ('\n','\r\n','\r','\t',' ','\x00','\u2028','junk'):
                with self.subTest(suffix=suffix),self.assertRaises(ValidationError):
                    validator.validate('1990-12-31T23:59:60Z'+suffix)

    def test_all_established_positive_events_and_coverage(self):
        dates=('1972-06-30','1972-12-31','1973-12-31','1974-12-31','1975-12-31',
               '1976-12-31','1977-12-31','1978-12-31','1979-12-31','1981-06-30',
               '1982-06-30','1983-06-30','1985-06-30','1987-12-31','1989-12-31',
               '1990-12-31','1992-06-30','1993-06-30','1994-06-30','1995-12-31',
               '1997-06-30','1998-12-31','2005-12-31','2008-12-31','2012-06-30',
               '2015-06-30','2016-12-31')
        checker=qualified_format_checker();start,expires,positive,negative=leap_seconds()
        self.assertEqual((start,expires,len(positive),negative),(2272060800,4023129600,27,frozenset()))
        for date in dates:
            with self.subTest(date=date):
                self.assertTrue(checker.conforms(date+'T23:59:60.123456789Z','date-time'))
                self.assertFalse(checker.conforms(date+'T23:58:60Z','date-time'))
        for value in ('1971-12-31T23:59:60Z','2030-12-31T23:59:60Z'):
            with self.subTest(value=value),self.assertRaisesRegex(LeapSecondCoverageError,'COVERAGE'):
                checker.conforms(value,'date-time')
        # Future ordinary syntax is not narrowed to the external table horizon.
        self.assertTrue(checker.conforms('2030-12-31T23:59:59Z','date-time'))

    def test_missing_or_changed_leap_data_refuses_checker_qualification(self):
        raw=DATA.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'leap-seconds.list'
            with patch('jch_datetime.DATA',path):
                with self.assertRaisesRegex(LeapSecondCoverageError,'UNAVAILABLE'):qualified_format_checker()
                path.write_bytes(raw+b'\n')
                with self.assertRaisesRegex(LeapSecondCoverageError,'IDENTITY'):qualified_format_checker()

    def test_checker_registration_remains_local(self):
        before=deepcopy(FormatChecker.checkers)
        qualified_format_checker();qualified_format_checker()
        self.assertEqual(FormatChecker.checkers,before)
        for value in (None,True,1,[],{}):
            self.assertTrue(qualified_format_checker().conforms(value,'date-time'))

    def test_missing_permissive_and_incomplete_ordinary_checkers_refuse(self):
        for kind in ('missing','permissive','incomplete'):
            checker=FormatChecker()
            if kind=='missing':checker.checkers.pop('date-time',None)
            else:
                checker.checks('date-time')(lambda value: True if kind=='permissive' else value=='2024-02-29T00:00:00Z')
            with self.subTest(kind=kind),patch('jch_normative_schemas.FormatChecker',return_value=checker):
                with self.assertRaises(ValueError):qualified_format_checker()
