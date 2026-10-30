"""STATIC access-surface qualification at immutable dev SHA.

Never asserts real deployed worker isolation, credentials, resource ownership
or an actually enabled v3 journal/Codespace gate. All reads are local CI.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
INVENTORY=json.loads((ROOT/"tests/fixtures/pre_model_v3/codespace_effect_surface_inventory.v1.json").read_text())
PATTERNS=tuple(re.compile(x,re.IGNORECASE|re.MULTILINE) for x in (
    r"user/codespaces/",
    r"\bgh\s+(?:codespace|cs)\s+(?:ssh|cp|stop|start|view)\b",
    r"\[\s*['\"]gh['\"]\s*,\s*['\"]codespace['\"]",
    r"\[\s*['\"]ssh['\"]\s*,\s*['\"]-F['\"]",
    r"\bCodespaceController\s*\(",
    r"\bcontroller\.(?:stop|start|recover|transfer|execute)\s*\(",
    r"\blifecycle\.(?:start|stop)\s*\(",
    r"\btransport\.(?:prepare|shutdown|preflight|emit_once)\s*\(",
    r"\bCodespaceLiteralCopier\s*\(",
    r"\bproxycommand\b",
    r"\btransport_factory\s*\(",
    r"\brun_pilot03_controller\s*\(",
    r"\binternal-(?:reconcile|stop-codespace|recover)(?![-A-Za-z0-9_])",
))


def detect(text):
    return any(p.search(text) for p in PATTERNS)


def discover(overrides=None):
    overrides=overrides or {}
    seen=set()
    for directory,exts in (
        (ROOT/".github/workflows",(".yml",".yaml")),
        (ROOT/"src/review_broker",(".py",)),
        (ROOT/"scripts",(".py",".sh")),
    ):
        if directory.exists():
            for path in directory.rglob("*"):
                if not path.is_file() or path.suffix not in exts:
                    continue
                key=path.relative_to(ROOT).as_posix()
                if detect(overrides.get(key,path.read_text(encoding="utf-8"))):
                    seen.add(key)
    for key,text in overrides.items():
        if detect(text):
            seen.add(key)
    return seen


class CodespaceEffectSurfaceTests(unittest.TestCase):
    def test_a01_exhaustive_static_pattern_surface_equals_pinned_inventory(self):
        discovered=discover()
        recorded={x["path"] for x in INVENTORY["scanned_effect_surfaces"]}
        self.assertEqual(discovered,recorded,
            f"New or stale Codespace path: unregistered={sorted(discovered-recorded)};"
            f" missing={sorted(recorded-discovered)}")

    def test_a02_pinned_source_sha_and_all_recorded_git_blobs(self):
        self.assertEqual(INVENTORY["source_commit_sha"],
                         "f9e902ee577d3a22330c3bf2fb04dcae28ed3034")
        effect=INVENTORY["scanned_effect_surfaces"]
        support=INVENTORY["supporting_boundaries"]
        self.assertEqual((len(effect),len(support)),(16,3))
        paths=[x["path"] for x in effect+support]
        self.assertEqual(len(paths),len(set(paths)))
        for item in effect+support:
            with self.subTest(path=item["path"]):
                path=ROOT/item["path"]
                self.assertTrue(path.is_file())
                got=subprocess.check_output(
                    ["git","hash-object",str(path)],text=True,cwd=ROOT
                ).strip()
                self.assertEqual(got,item["blob_sha"])

    def test_a03_injected_unknown_gh_codespace_stop_is_detected(self):
        key="src/review_broker/new_unvetted_path.py"
        self.assertIn(key,discover({key:'subprocess.run(["gh","codespace","stop","-c",name])'}))
        self.assertNotIn(key,{x["path"] for x in INVENTORY["scanned_effect_surfaces"]})

    def test_a04_injected_unknown_native_ssh_bypass_is_detected(self):
        key="src/review_broker/new_native_ssh.py"
        self.assertIn(key,discover({key:'runner(["ssh","-F",config,alias,"id"])'}))
        self.assertNotIn(key,{x["path"] for x in INVENTORY["scanned_effect_surfaces"]})

    def test_a05_qualification_workflow_uses_distinct_concurrency_group(self):
        r=(ROOT/".github/workflows/review-request.yml").read_text()
        c=(ROOT/".github/workflows/review-reconciler.yml").read_text()
        q=(ROOT/".github/workflows/codespace-control-qualification.yml").read_text()
        self.assertIn("group: review-broker-single-reviewer",r)
        self.assertIn("group: review-broker-single-reviewer",c)
        self.assertIn("group: review-broker-codespace-control-qualification",q)
        self.assertNotIn("group: review-broker-single-reviewer",q)
        self.assertIn("user/codespaces/",q)
        self.assertIn("gh codespace stop",q)

    def test_a06_live_codespace_name_equality_not_established_by_source(self):
        r=(ROOT/".github/workflows/review-request.yml").read_text()
        q=(ROOT/".github/workflows/codespace-control-qualification.yml").read_text()
        self.assertIn("vars.REVIEW_BROKER_CODESPACE_NAME",r)
        self.assertIn("CODESPACE_NAME: review-broker-reviewer-4q4v769jr65hjww9",q)
        self.assertEqual(INVENTORY["codespace_name_equality_to_runtime_variable"],
                         "UNVERIFIED")

    def test_a07_pilot_controller_accepts_arbitrary_codespace_selector(self):
        cli=(ROOT/"src/review_broker/pilot_cli.py").read_text()
        t=(ROOT/"src/review_broker/pilot03_transport.py").read_text()
        auth=(ROOT/"src/review_broker/pilot03_authorization.py").read_text()
        self.assertIn('controller.add_argument("--codespace", required=True)',cli)
        self.assertIn("self.lifecycle.start()",t)
        self.assertIn("self.lifecycle.stop()",t)
        self.assertIn("codespace_identity",auth)
        self.assertNotIn("PREPARED",t)

    def test_a08_pilot_independent_copy_native_ssh_and_proxy(self):
        pre=(ROOT/"src/review_broker/pilot03_remote_preflight.py").read_text()
        art=(ROOT/"src/review_broker/pilot03_remote_artifacts.py").read_text()
        ret=(ROOT/"src/review_broker/pilot_private_retention.py").read_text()
        proxy=(ROOT/"src/review_broker/pilot03_ssh_config.py").read_text()
        self.assertIn('"codespace", "cp"',pre)
        self.assertIn('"ssh", "-F"',art)
        self.assertIn('"codespace", "cp"',ret)
        self.assertIn("proxycommand",proxy.lower())

    def test_a09_cli_reconciler_and_cleanup_have_other_access_routes(self):
        cli=(ROOT/"src/review_broker/cli.py").read_text()
        rec=(ROOT/"src/review_broker/reconciliation.py").read_text()
        cleanup=(ROOT/"src/review_broker/execution_recovery.py").read_text()
        for name in ("internal-stop-codespace","internal-reconcile","internal-recover"):
            self.assertIn(name,cli)
        self.assertIn("controller.stop()",rec)
        self.assertIn("controller.stop()",cleanup)

    def test_a10_source_only_qualification_and_publication_are_negative_controls(self):
        src=(ROOT/".github/workflows/private-source-qualification.yml").read_text()
        publication=(ROOT/".github/workflows/publication-recovery.yml").read_text()
        self.assertIn('REVIEW_BROKER_CODESPACE_TOKEN: ""',src)
        self.assertFalse(detect(src))
        self.assertFalse(detect(publication))

    def test_a11_no_deployed_v3_universal_gate_is_claimed(self):
        self.assertFalse(INVENTORY["full_runtime_prepared_gate_qualified"])
        self.assertFalse(INVENTORY["old_workers_excluded"])
        self.assertFalse(INVENTORY["resource_owner_exclusivity_qualified"])
        self.assertTrue(all(x["gate_v3_present"] is False for x in
                            INVENTORY["scanned_effect_surfaces"]))

    def test_a12_detector_positive_and_negative_fixtures(self):
        self.assertFalse(detect("Codespace mentioned in a document."))
        self.assertTrue(detect("gh codespace stop -c name"))
        self.assertTrue(detect('gh api --method POST "user/codespaces/name/start"'))
        self.assertTrue(detect("controller.stop()"))

    def test_a13_different_qualification_group_is_not_global_resource_lease(self):
        rows={x["path"]:x for x in INVENTORY["scanned_effect_surfaces"]}
        a=rows[".github/workflows/review-request.yml"]
        b=rows[".github/workflows/codespace-control-qualification.yml"]
        self.assertNotEqual(a["concurrency_group"],b["concurrency_group"])
        self.assertEqual(b["review_request_target_overlap"],"NOT_QUALIFIED")

    def test_a14_source_scan_not_equivalent_to_full_security_attestation(self):
        self.assertIn("STATIC",INVENTORY["interpretation"].upper())
        self.assertEqual(INVENTORY["codespace_name_equality_to_runtime_variable"],"UNVERIFIED")
        self.assertFalse(INVENTORY["full_runtime_prepared_gate_qualified"])


if __name__=="__main__":
    unittest.main()
