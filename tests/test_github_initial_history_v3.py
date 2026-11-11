"""Provider-shaped initial-history acceptance and fail-closed completeness oracles."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from review_broker.github_initial_history_v3 import GitHubInitialHistoryAuthorityV3
from review_broker.github_journal_transport_v3 import ReadResultV3, ReadStatusV3, TransportSnapshotV3
from review_broker.journal_record_v3 import initial_record, encode_journal_v2
from tests.journal_v3_test_support import ADMISSION, REQUEST_ID

NAMESPACE = "refs/heads/review-claims-v3/"  # independent expected namespace
BOUNDARY = "b" * 40
INTENT = "review-intent:sha256:" + "c" * 64
QUALIFICATION = "qualification-20261030T200256Z-513925f0bf09"
FIXTURES = Path(__file__).parent / "fixtures" / "initial-history"


def node(name=QUALIFICATION, oid="d" * 40):
    return {"name": name, "target": {"oid": oid, "__typename": "Commit"}}


def page(nodes, *, total=None, more=False, cursor=None):
    return {"repository": {"databaseId": 1433701208,
            "nameWithOwner": "fanilosendrison/review-broker", "refs": {
                "totalCount": len(nodes) if total is None else total,
                "nodes": nodes, "pageInfo": {"hasNextPage": more, "endCursor": cursor}}}}


class Provider:
    def __init__(self, pages):
        self.pages = deepcopy(pages)
        self.calls = []

    def query(self, query, variables):
        self.calls.append((query, variables))
        if not self.pages:
            raise AssertionError("unexpected extra inventory query")
        return self.pages.pop(0)


class JournalReader:
    def __init__(self, values=None):
        self.values = values or {}
        self.calls = []

    def read_journal_commit(self, sha):
        self.calls.append(sha)
        return self.values.get(sha, ReadResultV3(ReadStatusV3.MISSING))


def history(pages, reader=None):
    provider = Provider(pages)
    reader = reader or JournalReader()
    return GitHubInitialHistoryAuthorityV3(provider, reader, BOUNDARY), provider, reader


def journal_read(intent=INTENT):
    # Real journal-v2 encoding/decoding, not a patched decoder or claimed match.
    raw = encode_journal_v2(initial_record(REQUEST_ID, {**ADMISSION, "review_intent_id": intent}))
    return ReadResultV3(ReadStatusV3.FOUND, TransportSnapshotV3("d" * 40, BOUNDARY, raw))


class InitialHistoryProviderTests(unittest.TestCase):
    def test_H01_relative_qualification_reconstructed(self):
        h, provider, _ = history([page([node()])])
        self.assertEqual(h.inventory(), [(NAMESPACE + QUALIFICATION, "d" * 40)])
        self.assertIn('refPrefix:"refs/heads/review-claims-v3/"', provider.calls[0][0])

    def test_H02_relative_64hex_claim_reconstructed(self):
        h, _, _ = history([page([node("a" * 64)])])
        self.assertEqual(h.inventory(), [(NAMESPACE + "a" * 64, "d" * 40)])

    def test_H03_qualification_is_inventory_only(self):
        p = page([node()]); h, provider, reader = history([p, p])
        decision = h.decide(REQUEST_ID, INTENT, NAMESPACE)
        self.assertEqual(decision.matching_request_ids, ())
        self.assertEqual(reader.calls, [])
        self.assertEqual(len(provider.calls), 2)

    def test_H04_64hex_claim_decoded_for_intent(self):
        p = page([node("a" * 64)]); reader = JournalReader({"d" * 40: journal_read()})
        h, _, _ = history([p, p], reader)
        self.assertEqual(h.decide(REQUEST_ID, INTENT, NAMESPACE).matching_request_ids,
                         (REQUEST_ID,))
        self.assertEqual(reader.calls, ["d" * 40])

    def test_H05_full_names_and_unsafe_relative_names_rejected(self):
        invalid = ("", NAMESPACE + "a" * 64, "refs/heads/x", "/a", "a/", "a//b",
                   ".", "..", "a/./b", "a/../b", "a\x00b", "a\nb", "a\x7fb",
                   "a\x85b", "a..b", "a.lock",
                   "a/b.lock", "a@{b", "a b", "a?b", "a*b", "a[b", "a\\b", "a:b")
        for name in invalid:
            with self.subTest(name=repr(name)):
                h, _, _ = history([page([node(name)])])
                with self.assertRaisesRegex(ValueError, "INITIAL_HISTORY_REF_INVALID"):
                    h.inventory()
        h, _, _ = history([page([node("nested/qualification-valid_1.0")])])
        self.assertEqual(h.inventory()[0][0], NAMESPACE + "nested/qualification-valid_1.0")

    def test_H06_duplicate_name_rejected_in_or_across_pages(self):
        cases = [[page([node(), node()])],
                 [page([node()], total=2, more=True, cursor="next"), page([node()], total=2)]]
        for pages in cases:
            h, _, _ = history(pages)
            with self.assertRaisesRegex(ValueError, "INITIAL_HISTORY_REF_INVALID"):
                h.inventory()

    def test_H07_commit_target_required(self):
        n = node(); n["target"]["__typename"] = "Tag"
        h, _, _ = history([page([n])])
        with self.assertRaisesRegex(ValueError, "INITIAL_HISTORY_REF_INVALID"):
            h.inventory()

    def test_H08_exact_lowercase_40hex_oid_required(self):
        for oid in ("a" * 39, "a" * 41, "A" * 40, "g" * 40, "a" * 40 + "\n"):
            h, _, _ = history([page([node(oid=oid)])])
            with self.assertRaisesRegex(ValueError, "INITIAL_HISTORY_REF_INVALID"):
                h.inventory()

    def test_H09_complete_pagination_and_finite_budget(self):
        pages = [page([node("first")], total=2, more=True, cursor="next"),
                 page([node("second")], total=2)]
        h, provider, _ = history(pages)
        self.assertEqual(h.inventory(), [(NAMESPACE + n, "d" * 40) for n in ("first", "second")])
        self.assertEqual([v for _, v in provider.calls], [{"cursor": None}, {"cursor": "next"}])
        cases = [[page([], total=1)], [page([], total=1, more=True, cursor="x")],
                 [page([node()], total=2, more=True)],
                 [page([node("a")], total=3, more=True, cursor="x"),
                  page([node("b")], total=3, more=True, cursor="x")]]
        for pages in cases:
            h, _, _ = history(pages)
            with self.assertRaisesRegex(ValueError, "INITIAL_HISTORY_INCOMPLETE"):
                h.inventory()
        pages = [page([node(f"qualification-{i}")], total=101, more=True, cursor=str(i))
                 for i in range(100)]
        h, provider, _ = history(pages)
        with self.assertRaisesRegex(ValueError, "INITIAL_HISTORY_PAGE_BUDGET"):
            h.inventory()
        self.assertEqual(len(provider.calls), 100)

    def test_H10_total_count_drift_rejected(self):
        h, _, _ = history([page([node("a")], total=2, more=True, cursor="x"),
                           page([node("b")], total=3)])
        with self.assertRaisesRegex(ValueError, "INITIAL_HISTORY_INCOMPLETE"):
            h.inventory()
        for count in (-1, True, "1"):
            h, _, _ = history([page([node()], total=count)])
            with self.assertRaisesRegex(ValueError, "INITIAL_HISTORY_INCOMPLETE"):
                h.inventory()

    def test_H11_second_inventory_difference_including_qualification_oid(self):
        for second in (node(oid="e" * 40), node("different-qualification")):
            h, _, reader = history([page([node()]), page([second])])
            with self.assertRaisesRegex(ValueError, "INITIAL_HISTORY_CHANGED"):
                h.decide(REQUEST_ID, INTENT, NAMESPACE)
            self.assertEqual(reader.calls, [])

    def test_H12_exact_initial_decision_without_prior_intent(self):
        request_id = "request:sha256:f433cd757dbd6a4b39e852d057cb64e8cfd05baa38a37f34600004240a80238f"
        intent = "review-intent:sha256:79f214c47b33d0f2cc0faba9f3aaa943d19d5af71d749857f195b16d95535072"
        observed = json.loads((FIXTURES / "github-relative-graphql.json").read_text())
        h, _, reader = history([{"repository": observed}, {"repository": observed}])
        d = h.decide(request_id, intent, NAMESPACE)
        self.assertTrue(d.complete)
        self.assertEqual((d.request_id, d.review_intent_id, d.namespace, d.scan_boundary),
                         (request_id, intent, NAMESPACE, BOUNDARY))
        self.assertEqual(d.matching_request_ids, ())
        self.assertEqual(reader.calls, [])

    def test_H13_existing_matching_intent_still_detected(self):
        p = page([node("a" * 64), node("b" * 64, "e" * 40)])
        reader = JournalReader({"d" * 40: journal_read(), "e" * 40: journal_read("other")})
        h, _, _ = history([p, p], reader)
        self.assertEqual(h.decide(REQUEST_ID, INTENT, NAMESPACE).matching_request_ids, (REQUEST_ID,))
        self.assertEqual(reader.calls, ["d" * 40, "e" * 40])

    def test_H14_unrelated_refs_and_nonexact_claim_names_do_not_match(self):
        names = [QUALIFICATION, "qualification-actions-41125852909-1",
                 "qualification-transport-41146147719-1", "a" * 63, "A" * 64,
                 "nested/" + "a" * 64, "a" * 65]
        p = page([node(name) for name in names]); h, _, reader = history([p, p])
        self.assertEqual(h.decide(REQUEST_ID, INTENT, NAMESPACE).matching_request_ids, ())
        self.assertEqual(reader.calls, [])

    def test_H15_projected_provider_graphql_and_rest_agree(self):
        g = json.loads((FIXTURES / "github-relative-graphql.json").read_text())
        rest = json.loads((FIXTURES / "github-matching-refs.json").read_text())
        h, _, _ = history([{"repository": g}])
        self.assertEqual(dict(h.inventory()), {r["ref"]: r["object"]["sha"] for r in rest})
        self.assertEqual(len(rest), g["refs"]["totalCount"])
        self.assertFalse(g["refs"]["pageInfo"]["hasNextPage"])

    def test_repository_identity_namespace_and_unavailable_journal_fail_closed(self):
        for field, value in (("databaseId", 1), ("nameWithOwner", "other/repo")):
            p = page([]); p["repository"][field] = value; h, _, _ = history([p])
            with self.assertRaisesRegex(ValueError, "INITIAL_HISTORY_REPOSITORY_MISMATCH"):
                h.inventory()
        h, _, _ = history([])
        with self.assertRaisesRegex(ValueError, "INITIAL_HISTORY_NAMESPACE_INVALID"):
            h.decide(REQUEST_ID, INTENT, "refs/heads/other/")
        h, _, _ = history([page([node("a" * 64)])])
        with self.assertRaisesRegex(ValueError, "INITIAL_HISTORY_UNAVAILABLE"):
            h.decide(REQUEST_ID, INTENT, NAMESPACE)
