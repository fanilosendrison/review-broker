"""Closed declared-scope inventory; no claim about live installation grants."""
import hashlib
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).parents[1]
ACTION = "actions/create-github-app-token@fee1f7d63c2ff003460e3d139729b119787bc349"
APP_ID = "${{ vars.REVIEW_BROKER_SOURCE_APP_ID }}"
PRIVATE_KEY = "${{ secrets.REVIEW_BROKER_SOURCE_APP_PRIVATE_KEY }}"
TOKEN = "${{ steps.source_auth.outputs.token }}"
LEGACY_PERMISSIONS = {
    "permission-contents": "read", "permission-pull-requests": "read", "permission-metadata": "read",
}
LEGACY_SITES = {
    "review-request.yml": ("review", "${{ github.repository_owner }}", 2),
    "review-reconciler.yml": ("reconcile", "${{ github.repository_owner }}", 1),
    "private-source-qualification.yml": ("qualify", "fanilosendrison", 0),
}
V3_SITE = "v3-source-app-read-qualification.yml"
V3_ADAPTER_SITE = "v3-source-adapter-qualification.yml"
V3_CONTROLLER_SITE = "v3-pre-model-controller.yml"
V3_WORKER_SITE = "v3-pre-model-worker.yml"
V3_PERMISSIONS = {**LEGACY_PERMISSIONS, "permission-issues": "read"}
V3_TOKEN = "${{ steps.source.outputs.token }}"
V3_IDENTITY_BINDINGS = {
    "REVIEW_BROKER_SOURCE_APP_SLUG": "${{ steps.source.outputs.app-slug }}",
    "REVIEW_BROKER_SOURCE_INSTALLATION_ID": "${{ steps.source.outputs.installation-id }}",
}
SOURCE_KEYS = ("REVIEW_BROKER_SOURCE_TOKEN", *V3_IDENTITY_BINDINGS)
OPERATIONAL_SITES = {
    V3_CONTROLLER_SITE: ("controller", ("run", 'reviewctl internal-v3-pre-model-controller --issue "$REQUEST_ISSUE" --request-id "$REQUEST_ID"')),
    V3_WORKER_SITE: ("worker", ("uses", "./.github/actions/v3-pre-model-worker-launch")),
}
# Independently frozen raw-byte snapshots: qualification gates and exact consumers.
WORKFLOW_SHA256 = {
    V3_SITE: "f761c4d838c4249497ff205e7130a06c0d09f26be654228e0f2c43688e5d4e3e",
    V3_ADAPTER_SITE: "9ae51909cdc6eb62d1e03b02848c28a2b346bfb2b2cdca65a16b8093b3824490",
    V3_CONTROLLER_SITE: "7b546de7c97c37fb8a6d0069f6527f1f4596fb90c401aa1bfd77d86515900242",
    V3_WORKER_SITE: "dcc9b01c44e14ae29b7279aac413553dd18a0a574cf7152b3ba71b2103b7233b",
}
QUALIFICATION_HEADER = """name: Private source qualification

on:
  repository_dispatch:
    types: [review-broker-private-source-qualification]

permissions: {}

concurrency:
  group: review-broker-private-source-qualification
  cancel-in-progress: false

jobs:
  qualify:
    if: >-
      github.repository == 'fanilosendrison/review-broker' &&
      github.event_name == 'repository_dispatch' &&
      github.event.action == 'review-broker-private-source-qualification' &&
      github.ref == format('refs/heads/{0}', github.event.repository.default_branch) &&
      github.event.sender.id == 30498238 &&
      github.actor == 'fanilosendrison' &&
      github.triggering_actor == 'fanilosendrison'
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    steps:
"""
QUALIFICATION_STEPS_SHA256 = "51f378720f91b47597116eaabe6003ce98b160f1db0ae34947271bd080e04dc7"


def audit_private_source_dispatch(text):
    """Preserve the independently accepted admission prefix and entire steps body."""
    if not text.startswith(QUALIFICATION_HEADER):
        raise AssertionError("private-source dispatch admission changed")
    if hashlib.sha256(text[len(QUALIFICATION_HEADER):].encode()).hexdigest() != QUALIFICATION_STEPS_SHA256:
        raise AssertionError("private-source secret/acquisition steps changed")


def step_blocks(text):
    """Restrictive existing block-style oracle, not a general YAML parser."""
    starts = list(re.finditer(r"^      - .+$", text, re.MULTILINE))
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        boundary = re.search(r"^  [A-Za-z_][\w-]*:\s*$", text[start.end():end], re.MULTILINE)
        if boundary:
            end = start.end() + boundary.start()
        yield text[start.start():end]


def literal_fields(block, indent):
    fields = {}
    for line in block.splitlines():
        match = re.fullmatch(r" " * indent + r"([\w-]+):(?: (.*))?", line)
        if match:
            key, value = match.groups()
            if key in fields:
                raise AssertionError(f"duplicate field: {key}")
            fields[key] = value or ""
    return fields


def site_contracts():
    sites = {name: dict(job=job, owner=owner, count=count, step="source_auth", token=TOKEN,
                       permissions=LEGACY_PERMISSIONS, repositories=None)
             for name, (job, owner, count) in LEGACY_SITES.items()}
    for name in (V3_SITE, V3_ADAPTER_SITE):
        sites[name] = dict(job="qualify", owner="fanilosendrison", count=1, step="source_auth",
                           token=TOKEN, permissions=V3_PERMISSIONS, repositories="review-broker")
    for name, (job, invocation) in OPERATIONAL_SITES.items():
        sites[name] = dict(job=job, owner="fanilosendrison", count=1, step="source", token=V3_TOKEN,
                           permissions=V3_PERMISSIONS, repositories="review-broker", invocation=invocation)
    return sites


def enclosing_job(text, block):
    jobs = re.findall(r"^  ([\w-]+):\s*$", text[:text.index(block)], re.MULTILINE)
    return jobs[-1] if jobs else None


def audit_workflows(workflows):
    sites, seen = site_contracts(), set()
    for name, text in workflows.items():
        blocks = list(step_blocks(text))
        action_lines = [line for line in text.splitlines() if "uses:" in line and "actions/create-github-app-token" in line]
        mint_blocks = [block for block in blocks if "actions/create-github-app-token" in block]
        if len(action_lines) != len(mint_blocks):
            raise AssertionError(f"unclassified action serialization: {name}")
        source_blocks = [block for block in blocks if APP_ID in block or PRIVATE_KEY in block]
        for block in blocks:
            if block not in mint_blocks and block not in source_blocks:
                continue
            if name not in sites or name in seen:
                raise AssertionError(f"unclassified source mint: {name}")
            seen.add(name)
            site, fields, inputs = sites[name], literal_fields(block, 8), literal_fields(block, 10)
            if fields.get("uses") != ACTION or fields.get("id") != site["step"]:
                raise AssertionError(f"source action/identifier changed: {name}")
            if fields.get("with") != "":
                raise AssertionError(f"missing block input mapping: {name}")
            permissions = {k: v for k, v in inputs.items() if k.startswith("permission-")}
            if permissions != site["permissions"]:
                raise AssertionError(f"incorrect classified permission subset: {name}")
            expected = {"app-id": APP_ID, "private-key": PRIVATE_KEY, "owner": site["owner"], **site["permissions"]}
            if site["repositories"] is not None:
                expected["repositories"] = site["repositories"]
            if inputs != expected:
                raise AssertionError(f"source inputs changed: {name}")
            for line in block.split("        with:\n", 1)[1].splitlines():
                if line.strip() and not re.fullmatch(r"          [\w-]+: .+", line):
                    raise AssertionError(f"unaudited source input syntax: {name}")
            if enclosing_job(text, block) != site["job"]:
                raise AssertionError(f"source mint moved to another job: {name}")
        if name not in sites:
            if any(key in text for key in SOURCE_KEYS) or re.search(r"steps\.(?:source|source_auth)\.outputs\.(?:token|app-slug|installation-id)", text):
                raise AssertionError(f"unclassified source-token consumer: {name}")
            continue
        site = sites[name]
        bindings = {"REVIEW_BROKER_SOURCE_TOKEN": [site["token"]] * site["count"]}
        if name in OPERATIONAL_SITES:
            bindings.update({key: [value] for key, value in V3_IDENTITY_BINDINGS.items()})
        for key in SOURCE_KEYS:
            if re.findall(rf"^          {key}: (.+)$", text, re.MULTILINE) != bindings.get(key, []):
                raise AssertionError(f"source consumer binding changed: {name}: {key}")
        if name in OPERATIONAL_SITES:
            consumers = [b for b in blocks if "REVIEW_BROKER_SOURCE_TOKEN:" in b]
            key, value = site["invocation"]
            if (len(consumers) != 1 or literal_fields(consumers[0], 8).get(key) != value
                    or enclosing_job(text, consumers[0]) != site["job"]):
                raise AssertionError(f"source consumer invocation changed: {name}")
            if any(text.count(value) != 1 for values in bindings.values() for value in values):
                raise AssertionError(f"source output consumer count changed: {name}")
        if name == "private-source-qualification.yml":
            consumers = [literal_fields(b, 10) for b in blocks if "      - name: Qualify exact read-only source acquisition\n" in b]
            if len(consumers) != 1 or consumers[0].get("GH_TOKEN") != TOKEN:
                raise AssertionError("qualification token binding changed")
    if seen != set(sites):
        raise AssertionError("source mint inventory incomplete")
    audit_private_source_dispatch(workflows["private-source-qualification.yml"])
    for name, expected in WORKFLOW_SHA256.items():
        if hashlib.sha256(workflows[name].encode()).hexdigest() != expected:
            raise AssertionError(f"v3 approved-SHA workflow structure changed: {name}")
    return seen


class SourceAppCredentialScopeTests(unittest.TestCase):
    def setUp(self):
        self.workflows = {p.name: p.read_bytes().decode("utf-8") for p in (ROOT / ".github/workflows").iterdir() if p.suffix in {".yml", ".yaml"}}
        self.expected = set(LEGACY_SITES) | {V3_SITE, V3_ADAPTER_SITE, V3_CONTROLLER_SITE, V3_WORKER_SITE}
        self.assertEqual(audit_workflows(self.workflows), self.expected)

    def test_all_source_app_mints_have_explicit_classified_legacy_scope(self):
        self.assertEqual(len(self.expected), 7)
        self.assertEqual(audit_workflows(self.workflows), self.expected)

    def assert_rejected(self, name, old, new, reason=""):
        self.assertEqual(audit_workflows(self.workflows), self.expected)
        workflows = dict(self.workflows)
        self.assertIn(old, workflows[name])
        workflows[name] = workflows[name].replace(old, new, 1)
        with self.assertRaisesRegex(AssertionError, reason):
            audit_workflows(workflows)

    def test_legacy_scope_and_input_mutations_are_rejected(self):
        mutations = [(f"          {p}: read\n", "") for p in LEGACY_PERMISSIONS]
        mutations += [(f"{p}: read", f"{p}: write") for p in LEGACY_PERMISSIONS]
        mutations += [("          permission-metadata: read\n", "          permission-metadata: read\n" + addition)
                      for addition in [*(f"          permission-{p}: read\n" for p in ("issues", "actions", "workflows", "administration")),
                                       "          permission-metadata: write\n", "          <<: *unrestricted\n"]]
        mutations += [(ACTION, "actions/create-github-app-token@v2"), ("id: source_auth", "id: other_auth"),
                      (TOKEN, "${{ github.token }}"), (PRIVATE_KEY, "${{ secrets.OTHER_KEY }}")]
        for name in LEGACY_SITES:
            for old, new in mutations:
                with self.subTest(workflow=name, mutation=old, replacement=new):
                    self.assert_rejected(name, old, new)
            workflows = dict(self.workflows)
            for p in LEGACY_PERMISSIONS:
                workflows[name] = workflows[name].replace(f"          {p}: read\n", "")
            with self.subTest(workflow=name, mutation="all permissions"), self.assertRaises(AssertionError):
                audit_workflows(workflows)

    def test_operational_site_scope_and_bindings_are_rejected_independently(self):
        mutations = [(f"          {p}: read\n", "", "permission subset") for p in V3_PERMISSIONS]
        mutations += [(f"{p}: read", f"{p}: write", "permission subset") for p in V3_PERMISSIONS]
        mutations += [("          permission-issues: read\n", "          permission-issues: read\n          permission-actions: read\n", "permission subset"),
                      ("          repositories: review-broker\n", "", "source inputs"),
                      ("repositories: review-broker", "repositories: another-repository", "source inputs"),
                      ("owner: fanilosendrison", "owner: another-owner", "source inputs"),
                      (APP_ID, "${{ vars.OTHER_APP_ID }}", "source inputs"), (PRIVATE_KEY, "${{ secrets.OTHER_KEY }}", "source inputs"),
                      (ACTION, "actions/create-github-app-token@v2", "action/identifier"),
                      ("id: source\n", "id: other_source\n", "action/identifier")]
        for key, value in {"REVIEW_BROKER_SOURCE_TOKEN": V3_TOKEN, **V3_IDENTITY_BINDINGS}.items():
            mutations += [(f"          {key}: {value}\n", "", "consumer binding"),
                          (value, "${{ github.token }}", "consumer binding")]
            mutations += [(f"          {key}: {value}\n", f"          {key}: {value}\n          {key}: {value}\n", "consumer binding")]
        mutations += [(V3_TOKEN, TOKEN, "consumer binding")]
        for name, (job, invocation) in OPERATIONAL_SITES.items():
            cases = mutations + [(f"  {job}:\n", "  misplaced:\n", "another job"),
                                 (invocation[1], "untrusted-consumer", "consumer invocation")]
            mint = next(b for b in step_blocks(self.workflows[name]) if ACTION in b)
            cases += [(self.workflows[name], self.workflows[name] + mint, "unclassified source mint"),
                      (mint, mint.replace("        with:\n", "        with: {}\n", 1), "block input mapping")]
            for old, new, reason in cases:
                with self.subTest(workflow=name, mutation=old, reason=reason):
                    self.assert_rejected(name, old, new, reason)

    def test_qualification_sites_keep_exact_scope_and_snapshots(self):
        mutations = [(f"          {p}: read\n", "", "permission subset") for p in V3_PERMISSIONS]
        mutations += [(f"{p}: read", f"{p}: write", "permission subset") for p in V3_PERMISSIONS]
        mutations += [("          repositories: review-broker\n", "", "source inputs")]
        for name in (V3_SITE, V3_ADAPTER_SITE):
            for old, new, reason in mutations:
                with self.subTest(workflow=name, mutation=old):
                    self.assert_rejected(name, old, new, reason)
            self.assert_rejected(name, self.workflows[name], self.workflows[name] + "\n", "workflow structure")

    def test_exact_duplicate_mint_is_not_deduplicated(self):
        for name in sorted(self.expected):
            mint = next(b for b in step_blocks(self.workflows[name]) if ACTION in b)
            workflows = {**self.workflows, name: self.workflows[name] + mint}
            with self.subTest(workflow=name), self.assertRaisesRegex(AssertionError, "unclassified source mint"):
                audit_workflows(workflows)

    def test_unknown_mints_consumers_and_serializations_are_rejected(self):
        mint = f"      - uses: {ACTION}\n        with:\n          app-id: {APP_ID}\n          private-key: {PRIVATE_KEY}\n"
        for name in ("unclassified.yml", *LEGACY_SITES, V3_CONTROLLER_SITE, V3_WORKER_SITE):
            workflows = dict(self.workflows)
            workflows[name] = workflows.get(name, "jobs:\n  other:\n    steps:\n") + mint
            with self.subTest(workflow=name), self.assertRaisesRegex(AssertionError, "unclassified source mint"):
                audit_workflows(workflows)
        for field in (*SOURCE_KEYS, V3_TOKEN, *V3_IDENTITY_BINDINGS.values()):
            workflows = {**self.workflows, "unknown-consumer.yml": f"env:\n  {field}: untrusted\n"}
            with self.subTest(consumer=field), self.assertRaisesRegex(AssertionError, "unclassified source-token consumer"):
                audit_workflows(workflows)
        workflows = {**self.workflows, "serialized.yml": f"jobs:\n  other:\n    steps:\n    - uses: {ACTION}\n"}
        with self.assertRaisesRegex(AssertionError, "serialization"):
            audit_workflows(workflows)

    def test_private_source_dispatch_has_exact_admission_and_preserved_body(self):
        audit_private_source_dispatch(self.workflows["private-source-qualification.yml"])

    def test_private_source_dispatch_admission_mutations_are_rejected(self):
        text = self.workflows["private-source-qualification.yml"]
        guard = QUALIFICATION_HEADER.split("    if: >-\n", 1)[1].split("    runs-on:", 1)[0]
        cases = {
            "manual trigger": ("  repository_dispatch:\n", "  workflow_dispatch:\n"),
            "alternate trigger": ("on:\n", "on:\n  push:\n"),
            "repository": ("github.repository == 'fanilosendrison/review-broker'", "github.repository == 'other/repository'"),
            "event type": ("types: [review-broker-private-source-qualification]", "types: [other-event]"),
            "event name": ("github.event_name == 'repository_dispatch' &&\n", ""),
            "action": ("github.event.action == 'review-broker-private-source-qualification'", "github.event.action == 'other-event'"),
            "default ref": ("      github.ref == format('refs/heads/{0}', github.event.repository.default_branch) &&\n", ""),
            "sender": ("github.event.sender.id == 30498238", "github.event.sender.id == 1"),
            "actor": ("      github.actor == 'fanilosendrison' &&\n", ""),
            "triggering actor": ("      github.triggering_actor == 'fanilosendrison'\n", ""),
            "whole guard": ("    if: >-\n" + guard, ""),
            "payload authority": ("github.event.sender.id", "github.event.client_payload.id"),
            "job secret": ("    runs-on: ubuntu-24.04\n", "    env:\n      KEY: " + PRIVATE_KEY + "\n    runs-on: ubuntu-24.04\n"),
        }
        for label, (old, new) in cases.items():
            with self.subTest(mutation=label):
                self.assertIn(old, text)
                with self.assertRaises(AssertionError):
                    audit_private_source_dispatch(text.replace(old, new, 1))

    def test_private_source_key_relocation_to_job_environment_is_rejected(self):
        text = self.workflows["private-source-qualification.yml"]
        relocated = text.replace(f"          private-key: {PRIVATE_KEY}\n", "", 1)
        relocated = relocated.replace("jobs:\n", "jobs:\n  unguarded:\n" + f"    env:\n      KEY: {PRIVATE_KEY}\n", 1)
        self.assertNotEqual(text, relocated)
        with self.assertRaises(AssertionError):
            audit_private_source_dispatch(relocated)

    def test_private_source_dispatch_secret_body_mutations_are_rejected(self):
        text = self.workflows["private-source-qualification.yml"]
        cases = {
            "extra mint": ("    steps:\n", "    steps:\n" + f"      - uses: {ACTION}\n"),
            "unguarded job": ("jobs:\n", "jobs:\n  unguarded:\n" + f"    env:\n      KEY: {PRIVATE_KEY}\n"),
            "issues permission": ("          permission-metadata: read\n", "          permission-metadata: read\n          permission-issues: read\n"),
            "job token": (TOKEN, "${{ github.token }}"),
            "isolation removed": ("                *) unset \"$variable\" ;;", ""),
        }
        for permission in LEGACY_PERMISSIONS:
            cases[permission] = (f"{permission}: read", f"{permission}: write")
        for label, (old, new) in cases.items():
            with self.subTest(mutation=label):
                self.assertIn(old, text)
                with self.assertRaises(AssertionError):
                    audit_private_source_dispatch(text.replace(old, new, 1))

    def test_v3_workflow_trust_and_scope_mutations_are_rejected(self):
        mutations = [
            ("    permissions:\n      contents: read\n", ""),
            ("      contents: read\n", "      contents: write\n"),
            ("      contents: read\n", "      contents: read\n      issues: write\n"),
            ("      github.sha == vars.REVIEW_BROKER_V3_SOURCE_QUALIFICATION_SHA\n", ""),
            ("repository_dispatch:", "workflow_dispatch:"), ("on:\n", "on:\n  pull_request_target:\n"),
            ("          repositories: review-broker\n", ""), ("          permission-issues: read\n", ""),
            ("permission-contents: read", "permission-contents: write"),
            (ACTION, "actions/create-github-app-token@v2"), ("    steps:\n", f"    steps:\n      - uses: {ACTION}\n"),
            ("          ref: ${{ github.sha }}", "          ref: attacker-branch"),
            ("        env:\n", f"        env:\n          KEY: {PRIVATE_KEY}\n"),
            ("    runs-on:", f"    env:\n      KEY: {PRIVATE_KEY}\n    runs-on:"),
            ("python scripts/qualification/v3_source_app_read.py", "reviewctl internal-prepare"),
            ("github.event.repository.id", "github.event.client_payload.repository_id"),
        ]
        for old, new in mutations:
            with self.subTest(mutation=old):
                self.assert_rejected(V3_SITE, old, new)


if __name__ == "__main__":
    unittest.main()
