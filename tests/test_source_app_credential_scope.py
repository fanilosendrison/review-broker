"""Closed declared-scope inventory; no claim about live installation grants."""
from collections import Counter
from functools import lru_cache
import hashlib
from pathlib import Path
import re
import unittest
import yaml

ROOT = Path(__file__).parents[1]
decoded_workflow = lru_cache(maxsize=256)(lambda text: tuple(e.value for e in yaml.parse(text) if isinstance(e, yaml.events.ScalarEvent)))
ACTION = "actions/create-github-app-token@fee1f7d63c2ff003460e3d139729b119787bc349"
APP_ID = "${{ vars.REVIEW_BROKER_SOURCE_APP_ID }}"
PRIVATE_KEY = "${{ secrets.REVIEW_BROKER_SOURCE_APP_PRIVATE_KEY }}"
TOKEN = "${{ steps.source_auth.outputs.token }}"
LEGACY_PERMISSIONS = {
    "permission-contents": "read", "permission-pull-requests": "read", "permission-metadata": "read",
}
LEGACY_SITES = {
    "review-request.yml": ("review", "${{ github.repository_owner }}", 2, (2, 0, 0)),
    "review-reconciler.yml": ("reconcile", "${{ github.repository_owner }}", 1, (1, 0, 0)),
    "private-source-qualification.yml": ("qualify", "fanilosendrison", 0, (1, 1, 1)),
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
SOURCE_OUTPUTS = re.compile(r"\$\{\{\s*steps\.(source|source_auth)\.outputs\.(token|app-slug|installation-id)\s*\}\}")
# Detect the reserved object FIRST, independently of any child selector/function.
SOURCE_REFERENCE = re.compile(
    r"\bsteps\s*(?:\.\s*(?:source_auth|source)\b|\[\s*['\"](?:source_auth|source)['\"]\s*\])"
    r"\s*(?:\.\s*outputs\b|\[\s*['\"]outputs['\"]\s*\])", re.IGNORECASE)
OPERATIONAL_SITES = {
    V3_CONTROLLER_SITE: ("controller", ("run", 'reviewctl internal-v3-pre-model-controller --issue "$REQUEST_ISSUE" --request-id "$REQUEST_ID"')),
    V3_WORKER_SITE: ("worker", ("uses", "./.github/actions/v3-pre-model-worker-launch")),
}
# Raw snapshots also constrain legacy consumer scripts, including indirect aliases.
WORKFLOW_SHA256 = {
    "review-request.yml": "a331d51c6a8e77c38f0576180d9fb0a2838ab43ffab9d371c0deea9b10989cab",
    "review-reconciler.yml": "4adcaa48f3f63ae037c300d85b9a86b29ac05f4e8d64f4409beae130faa3f390",
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
                       permissions=LEGACY_PERMISSIONS, repositories=None, outputs=outputs)
             for name, (job, owner, count, outputs) in LEGACY_SITES.items()}
    for name in (V3_SITE, V3_ADAPTER_SITE):
        sites[name] = dict(job="qualify", owner="fanilosendrison", count=1, step="source_auth",
                           token=TOKEN, permissions=V3_PERMISSIONS, repositories="review-broker", outputs=(1, 1, 1))
    for name, (job, invocation) in OPERATIONAL_SITES.items():
        sites[name] = dict(job=job, owner="fanilosendrison", count=1, step="source", token=V3_TOKEN,
                           permissions=V3_PERMISSIONS, repositories="review-broker", outputs=(1, 1, 1), invocation=invocation)
    return sites


def enclosing_job(text, block):
    jobs = re.findall(r"^  ([\w-]+):\s*$", text[:text.index(block)], re.MULTILINE)
    return jobs[-1] if jobs else None


def audit_workflows(workflows):
    sites, seen = site_contracts(), set()
    for name, text in workflows.items():
        try:
            decoded = decoded_workflow(text)
        except (yaml.YAMLError, ValueError, TypeError, RecursionError) as exc:
            raise AssertionError(f"unsupported YAML serialization: {name}") from exc
        if name not in sites and any(key in value.casefold() for value in decoded for key in ("actions/create-github-app-token", "review_broker_source_app_id", "review_broker_source_app_private_key")):
            raise AssertionError(f"unclassified source mint: {name}")
        blocks = list(step_blocks(text))
        action_lines = [line for line in text.splitlines() if "uses:" in line and "actions/create-github-app-token" in line]
        mint_blocks = [block for block in blocks if "actions/create-github-app-token" in block]
        if len(action_lines) != len(mint_blocks) or sum(value.casefold().count("actions/create-github-app-token") for value in decoded) != len(mint_blocks):
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
            if any(key in value for value in decoded for key in SOURCE_KEYS) or any(SOURCE_REFERENCE.search(value.casefold()) for value in decoded):
                raise AssertionError(f"unclassified source-token consumer: {name}")
            continue
        site = sites[name]
        bindings = {"REVIEW_BROKER_SOURCE_TOKEN": [site["token"]] * site["count"]}
        if name in OPERATIONAL_SITES:
            bindings.update({key: [value] for key, value in V3_IDENTITY_BINDINGS.items()})
        for key in SOURCE_KEYS:
            if re.findall(rf"^          {key}: (.+)$", text, re.MULTILINE) != bindings.get(key, []):
                raise AssertionError(f"source consumer binding changed: {name}: {key}")
        expected_outputs = {f"${{{{ steps.{site['step']}.outputs.{field} }}}}": count for field, count in
                            zip(("token", "app-slug", "installation-id"), site["outputs"]) if count}
        reserved_scalars = [value for value in decoded if SOURCE_REFERENCE.search(value)]
        if Counter(reserved_scalars) != expected_outputs:
            raise AssertionError(f"reserved source output consumer count/scalar binding changed: {name}")
        if name in OPERATIONAL_SITES:
            consumers = [b for b in blocks if "REVIEW_BROKER_SOURCE_TOKEN:" in b]
            key, value = site["invocation"]
            if (len(consumers) != 1 or literal_fields(consumers[0], 8).get(key) != value
                    or enclosing_job(text, consumers[0]) != site["job"]):
                raise AssertionError(f"source consumer invocation changed: {name}")
        if name == "private-source-qualification.yml":
            consumers = [literal_fields(b, 10) for b in blocks if "      - name: Qualify exact read-only source acquisition\n" in b]
            if len(consumers) != 1 or consumers[0].get("GH_TOKEN") != TOKEN:
                raise AssertionError("qualification token binding changed")
    if seen != set(sites):
        raise AssertionError("source mint inventory incomplete")
    audit_private_source_dispatch(workflows["private-source-qualification.yml"])
    for name, expected in WORKFLOW_SHA256.items():
        if hashlib.sha256(workflows[name].encode()).hexdigest() != expected:
            raise AssertionError(f"approved-SHA workflow structure changed: {name}")
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
                      (mint, mint.replace("        with:\n", "        with: {}\n", 1), "block input mapping|serialization")]
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

    def test_known_site_consumers_and_legacy_invocations_are_closed(self):
        for name, site in site_contracts().items():
            for field in ("token", "app-slug", "installation-id"):
                value = f"${{{{ steps.{site['step']}.outputs.{field} }}}}"
                extra = f"      - name: Unclassified source consumer\n        env:\n          GH_TOKEN: {value}\n        run: untrusted-consumer\n"
                with self.subTest(workflow=name, consumer=field):
                    self.assert_rejected(name, self.workflows[name], self.workflows[name] + extra, "output consumer count")
            if name in LEGACY_SITES:
                for block in step_blocks(self.workflows[name]):
                    if SOURCE_OUTPUTS.search(block):
                        before, separator, body = block.partition("        run:")
                        self.assertTrue(separator)
                        with self.subTest(workflow=name, invocation=hashlib.sha256(block.encode()).hexdigest()):
                            self.assert_rejected(name, block, before + "        run: untrusted-consumer\n", "workflow structure|private-source secret")

    def test_exact_duplicate_mint_is_not_deduplicated(self):
        for name in sorted(self.expected):
            mint = next(b for b in step_blocks(self.workflows[name]) if ACTION in b)
            workflows = {**self.workflows, name: self.workflows[name] + mint}
            with self.subTest(workflow=name), self.assertRaisesRegex(AssertionError, "unclassified source mint"):
                audit_workflows(workflows)

    def test_decoded_unknown_mints_are_rejected(self):
        escaped = ACTION.replace("token", r"\u0074oken")
        text = f'jobs:\n  extra:\n    runs-on: ubuntu-24.04\n    steps:\n      - uses: "{escaped}"\n'
        with self.assertRaisesRegex(AssertionError, "unclassified source mint"):
            audit_workflows({**self.workflows, "escaped.yml": text})

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
        for step in ("source", "source_auth"):
            for root in (f"steps.{step}.outputs", f"steps['{step}'].outputs", f'steps["{step}"].outputs', f"steps.{step}['outputs']", f'steps["{step}"]["outputs"]'):
                bodies = (root, f"toJSON({root})", f"fromJSON(toJSON({root}))", f"contains(toJSON({root}), 'x')", f"{root}[format('{{0}}', 'token')]", *(f"{root}[{key}]" for key in ("inputs.name", "github.event.action", "env.KEY", "matrix.name")), f"{root}.*", f"format('{{0}}', {root}.token)", f"toJSON({root}.token)", f"{root}.token || {root}", f"{root}.unknown", *(f"{root}['{leaf}']" for leaf in ("token", "app-slug", "installation-id")))
                for body in bodies:
                    expression = "${{ " + body + " }}"
                    name = V3_CONTROLLER_SITE if step == "source" else "review-reconciler.yml"
                    with self.subTest(known_site=name, expression=expression):
                        self.assert_rejected(name, V3_TOKEN if step == "source" else TOKEN, expression, "binding|reserved source")
                    for text in (f"env:\n  GH_TOKEN: {expression}\n", "jobs:\n  extra:\n    runs-on: ubuntu-24.04\n    steps:\n      - run: '" + ("echo token: " + expression).replace("'", "''") + "'\n"):
                        workflows = {**self.workflows, "unknown.yml": text}
                        with self.subTest(reference=expression, scalar=text), self.assertRaisesRegex(AssertionError, "unclassified source-token consumer"):
                            audit_workflows(workflows)
        workflows = {**self.workflows, "serialized.yml": f"jobs:\n  other:\n    steps:\n    - uses: {ACTION}\n"}
        with self.assertRaisesRegex(AssertionError, "serialization|unclassified source mint"):
            audit_workflows(workflows)

    def test_private_source_dispatch_has_exact_admission_and_preserved_body(self):
        audit_private_source_dispatch(self.workflows["private-source-qualification.yml"])

    def test_private_source_dispatch_admission_and_body_mutations_are_rejected(self):
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
        cases.update({
            "extra mint": ("    steps:\n", "    steps:\n" + f"      - uses: {ACTION}\n"),
            "unguarded job": ("jobs:\n", "jobs:\n  unguarded:\n" + f"    env:\n      KEY: {PRIVATE_KEY}\n"),
            "issues permission": ("          permission-metadata: read\n", "          permission-metadata: read\n          permission-issues: read\n"),
            "job token": (TOKEN, "${{ github.token }}"),
            "isolation removed": ("                *) unset \"$variable\" ;;", ""),
        })
        for permission in LEGACY_PERMISSIONS:
            cases[permission] = (f"{permission}: read", f"{permission}: write")
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
