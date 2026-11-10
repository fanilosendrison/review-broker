"""Independent schema, ZIP, budget and pagination adversaries for RWP-04."""
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from review_broker.artifact_locator import ArtifactLocatorError
from review_broker.github_http_live_v3 import HttpResponseV3
from review_broker.identity import canonical_bytes
from review_broker.prepared_artifact_transport_v3 import PreparedArtifactBudgetV3, PreparedMetadataReaderV3
from review_broker.prepared_packet_archive_v3 import extract_prepared_packet_v3
from review_broker.remote_prepared_receipt_v3 import RemotePreparedReceiptV3, api_decimal_v3
from tests.issue70_rwp04_test_support import BUDGET

STORAGE = dict(backend="github-actions-artifact", repository="example/broker", repository_id=17,
    workflow_run_id=29, workflow_run_attempt=1, workflow_id=31,
    workflow_path=".github/workflows/v3-pre-model-worker.yml", execution_ref="refs/heads/frozen",
    executable_sha="a"*40, verified_worker_job_id="9007199254740993", artifact_id="9007199254740995",
    artifact_name="rb-v3-prepared-"+"b"*64+"-29-1", artifact_digest="sha256:"+"c"*64,
    artifact_size_in_bytes=100, created_at="2026-11-05T00:00:00+00:00", expires_at="2026-12-05T00:00:00Z")
VALUE = dict(schema_version=1, evidence_type="remote-v3-prepared-packet-binding",
             offline_preparation_receipt_id="artifact:sha256:"+"d"*64, storage=STORAGE)


def raw(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()+b"\n"


def archive(entries):
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, data, mode in entries:
            # zipfile truncates NUL on creation: preserve the hostile wire name
            # by editing both equal-length local/central names after serialization.
            info = zipfile.ZipInfo(name.replace("\x00", "@"))
            info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, data)
    value = result.getvalue()
    for name, _, _ in entries:
        if "\x00" in name:
            value = value.replace(name.replace("\x00", "@").encode(), name.encode())
    return value


class ReceiptTests(unittest.TestCase):
    def test_Q03_exact_canonical_identity_and_large_decimal_ids(self):
        receipt = RemotePreparedReceiptV3(raw(VALUE))
        self.assertEqual(receipt.evidence_id, "artifact:sha256:"+hashlib.sha256(raw(VALUE)).hexdigest())
        self.assertEqual(receipt.canonical_receipt_bytes, canonical_bytes(VALUE)+b"\n")
        self.assertEqual(api_decimal_v3(9007199254740993), "9007199254740993")
        self.assertEqual(receipt.value["storage"]["created_at"], STORAGE["created_at"])

    def test_Q03_builder_rejects_floats_before_canonicalization(self):
        for key in ("repository_id", "workflow_run_id", "workflow_id", "artifact_size_in_bytes", "workflow_run_attempt"):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "REMOTE_RECEIPT_INTEGER_INVALID"):
                RemotePreparedReceiptV3.build({}, {**STORAGE, key: 1.0})

    def test_Q03_every_unknown_and_missing_field_is_rejected(self):
        for level in ("top", "storage"):
            base = json.loads(raw(VALUE))
            fields = list(base if level == "top" else base["storage"])
            for field in fields+["unknown"]:
                value = json.loads(raw(VALUE))
                target = value if level == "top" else value["storage"]
                if field == "unknown": target[field] = True
                else: del target[field]
                with self.subTest(level=level, field=field), self.assertRaises(ValueError):
                    RemotePreparedReceiptV3(raw(value))

    def test_Q03_strict_json_integers_and_decimals(self):
        for key in ("repository_id", "workflow_run_id", "workflow_id", "artifact_size_in_bytes", "workflow_run_attempt"):
            for bad in (True, False, 1.0, 0, -1, 9007199254740992, "1", None):
                value = json.loads(raw(VALUE)); value["storage"][key] = bad
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    RemotePreparedReceiptV3(raw(value))
        for key in ("artifact_id", "verified_worker_job_id"):
            for bad in ("01", "0", "+1", "-1", " 1", "1 ", "1.0", "١", 1, True, None):
                value = json.loads(raw(VALUE)); value["storage"][key] = bad
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    RemotePreparedReceiptV3(raw(value))

    def test_Q03_canonical_lf_constants_dates_and_order(self):
        for bad in (raw(VALUE).rstrip(), raw(VALUE)+b"\n", b" "+raw(VALUE)):
            with self.assertRaises(ValueError): RemotePreparedReceiptV3(bad)
        for key, bad in (("created_at", "2026-11-05"), ("expires_at", STORAGE["created_at"]),
                         ("artifact_digest", "sha256:"+"C"*64), ("workflow_path", ".github/workflows/other.yml")):
            value = json.loads(raw(VALUE)); value["storage"][key] = bad
            with self.subTest(key=key), self.assertRaises((ValueError, ArtifactLocatorError)): RemotePreparedReceiptV3(raw(value))
        for bad in (True, 1.0, 0, 2):
            with self.assertRaises(ValueError): RemotePreparedReceiptV3(raw({**VALUE, "schema_version": bad}))


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.root.chmod(0o700)
        self.regular = stat.S_IFREG | 0o600

    def extract(self, entries, budget=BUDGET):
        return extract_prepared_packet_v3(archive(entries), self.root/"new", budget, lambda: None)

    def test_Q02_Q12_private_modes_at_creation_and_empty_structural_directory(self):
        opens, original = [], os.open
        def observe(path, flags, mode=0o777, **kwargs):
            opens.append(mode)
            return original(path, flags, mode, **kwargs)
        with patch("os.open", observe):
            inventory = self.extract([("packet/a", b"bytes", self.regular)])
        self.assertEqual(opens, [0o600])
        self.assertTrue((self.root/"new/evidence/admitted-references").is_dir())
        for path in [self.root/"new", *(self.root/"new").rglob("*")]:
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700 if path.is_dir() else 0o600)
        self.assertEqual(inventory["files"], [dict(path="packet/a", byte_length=5,
                                                sha256=hashlib.sha256(b"bytes").hexdigest())])

    def test_Q12_paths_aliases_symlinks_special_members_and_collisions(self):
        cases = [([(name, b"x", self.regular)]) for name in (
            "/packet/x", "packet/../x", "packet//x", "packet/./x", "packet\\x", "packet/x\x00evil",
            "outer/packet/x", "packet/C:x")]
        cases += [[("packet/x", b"x", kind|0o600)] for kind in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFSOCK)]
        cases += [[("packet/x", b"x", self.regular), ("packet/x/y", b"y", self.regular)],
                  [("packet/x/", b"", stat.S_IFDIR|0o700), ("packet/x", b"x", self.regular)]]
        for index, entries in enumerate(cases):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                extract_prepared_packet_v3(archive(entries), self.root/f"bad-{index}", BUDGET, lambda: None)

    def test_Q11_all_budget_types_and_zip_budgets(self):
        for key in BUDGET.__dataclass_fields__:
            for bad in (0, -1, True, 1.0, float("inf"), "5"):
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError): replace(BUDGET, **{key: bad})
        entries = [("packet/a", b"a"*200, self.regular), ("packet/b", b"b", self.regular)]
        for index, budget in enumerate((replace(BUDGET, max_members=1),
                replace(BUDGET, max_archive_bytes=10), replace(BUDGET, max_uncompressed_bytes=10))):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                extract_prepared_packet_v3(archive(entries), self.root/f"limit-{index}", budget, lambda: None)

    def test_Q11_actual_expansion_is_checked_before_writing(self):
        data = archive([("packet/a", b"ok", self.regular)])
        original = zipfile.ZipExtFile.read
        def inflated(stream, *args):
            chunk = original(stream, *args)
            return chunk + b"unexpected expansion" if chunk else chunk
        with patch.object(zipfile.ZipExtFile, "read", inflated), self.assertRaises(ValueError):
            extract_prepared_packet_v3(data, self.root/"inflated", replace(BUDGET, max_uncompressed_bytes=5), lambda: None)
        self.assertEqual((self.root/"inflated/packet/a").stat().st_size, 0)

    def test_Q13_closed_inventory_refuses_extra_missing_or_changed_bytes(self):
        expected = {"schema_version": 1, "files": [dict(path="packet/a", byte_length=1,
                                                       sha256=hashlib.sha256(b"a").hexdigest())]}
        for index, entries in enumerate(([("packet/a", b"b", self.regular)],
                [("packet/z", b"a", self.regular)], [("packet/a", b"a", self.regular), ("evidence/z", b"x", self.regular)])):
            with self.subTest(index=index), self.assertRaises(ValueError):
                extract_prepared_packet_v3(archive(entries), self.root/f"inventory-{index}", BUDGET,
                                           lambda: None, expected_inventory=expected)


class PaginationTests(unittest.TestCase):
    def reader(self, responses, budget=BUDGET):
        self.calls = []
        def execute(request, *, max_bytes):
            self.calls.append(request.full_url)
            return responses[len(self.calls)-1]
        return PreparedMetadataReaderV3(token="fixture", repository="example/broker", executor=execute, budget=budget)

    def response(self, count, items, links=None):
        return HttpResponseV3(200, json.dumps(dict(total_count=count, artifacts=items)).encode(),
                              {} if links is None else {"Link": links})

    def link(self, page, relation="next", scope="https://api.github.com/repos/example/broker/actions/runs/29/artifacts"):
        return f'<{scope}?name=frozen&per_page=100&page={page}>; rel="{relation}"'

    def listing(self, responses, budget=BUDGET):
        return self.reader(responses, budget).listing("/actions/runs/29/artifacts", {"name": "frozen"}, "artifacts", lambda: None)

    def test_Q07_complete_last_page_prev_first_is_valid(self):
        self.assertEqual(self.listing([self.response(2, [{"id": 1}], self.link(2)),
            self.response(2, [{"id": 2}], self.link(1, "prev")+", "+self.link(1, "first"))]), [{"id": 1}, {"id": 2}])
        self.assertEqual(len(self.calls), 2)

    def test_Q07_incomplete_duplicate_cycle_scope_count_and_bad_ids(self):
        for responses in ([self.response(2, [{"id": 1}])],
                [self.response(2, [{"id": 1}], self.link(2)), self.response(2, [{"id": 1}])],
                [self.response(2, [{"id": 1}], self.link(1))],
                [self.response(2, [{"id": 1}], self.link(2, scope="https://evil.invalid/x"))],
                [self.response(True, [{"id": 1}])], [self.response(1, [{"id": True}])],
                [self.response(2, [{"id": 1}], self.link(2)), self.response(3, [{"id": 2}])]):
            with self.subTest(responses=responses), self.assertRaises(ValueError): self.listing(responses)

    def test_Q11_metadata_page_and_response_budgets(self):
        with self.assertRaises(ValueError):
            self.listing([self.response(2, [{"id": 1}], self.link(2))], replace(BUDGET, max_metadata_pages=1))
        with self.assertRaises(ValueError):
            self.listing([self.response(1, [{"id": 1}])], replace(BUDGET, max_metadata_response_bytes=1))
