"""Static declared-scope guards; these do not prove live installation grants."""
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
    "permission-contents": "read",
    "permission-pull-requests": "read",
    "permission-metadata": "read",
}
# Independent expected scopes: legacy sites never inherit the v3 Issues grant.
LEGACY_SITES = {
    "review-request.yml": ("review", "${{ github.repository_owner }}", 2),
    "review-reconciler.yml": ("reconcile", "${{ github.repository_owner }}", 1),
    "private-source-qualification.yml": ("qualify", "fanilosendrison", 0),
}

V3_SITE = "v3-source-app-read-qualification.yml"
V3_PERMISSIONS = {**LEGACY_PERMISSIONS, "permission-issues": "read"}
# Exact, independently reviewed workflow snapshot: fixes trigger, one guarded
# job, preflight-before-key order, pins, repository selection and token consumers.
# Static current-tree evidence only; not a claim about live effective grants.
V3_WORKFLOW_SHA256 = "cf7ba54f654ac869843b27b75bd201a1ad301786f73348c357c3bf03b7b84fa2"

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
# Independent snapshot of the entire previously accepted steps block. Preserve
# mint order, exact permissions/output binding, source checks, isolation and
# receipts, not just selected strings. Any change requires an explicit audit.
QUALIFICATION_STEPS_SHA256 = (
    "51f378720f91b47597116eaabe6003ce98b160f1db0ae34947271bd080e04dc7"
)


def audit_private_source_dispatch(text):
    """Pin this credential-bearing workflow's admission and unchanged body.

    Exact serialization is intentional, like the existing lexical scope guard.
    This is not a YAML parser or proof of all repository-secret access paths.
    The prefix admits only the guarded qualify job, with no top/job-level env;
    the body snapshot excludes extra jobs/mints and payload-controlled behavior.
    Full YAML syntax is validated separately.
    """
    if not text.startswith(QUALIFICATION_HEADER):
        raise AssertionError("private-source dispatch admission changed")
    steps = text[len(QUALIFICATION_HEADER):]
    if hashlib.sha256(steps.encode("utf-8")).hexdigest() != QUALIFICATION_STEPS_SHA256:
        raise AssertionError("private-source secret/acquisition steps changed")


def step_blocks(text):
    """Select the repository's block-style job steps, not whole-file substrings.

    This is a deliberately restrictive lexical guard, not a YAML parser. Other
    serializations of credential steps require explicit audit before acceptance.
    Full YAML syntax validation is a separate qualification check.
    """
    starts = list(re.finditer(r"^      - .+$", text, re.MULTILINE))
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        # Do not accidentally absorb another job's metadata into the last step.
        boundary = re.search(r"^  [A-Za-z_][\w-]*:\s*$", text[start.end():end], re.MULTILINE)
        if boundary:
            end = start.end() + boundary.start()
        yield text[start.start():end]


def literal_fields(block, indent):
    """Read only direct, unique scalar fields at an audited indentation depth."""
    fields = {}
    for line in block.splitlines():
        match = re.fullmatch(r" " * indent + r"([\w-]+):(?: (.*))?", line)
        if match:
            key, value = match.groups()
            if key in fields:
                raise AssertionError(f"duplicate field: {key}")
            fields[key] = value or ""
    return fields


def audit_workflows(workflows):
    sites = {**LEGACY_SITES, V3_SITE: ("qualify", "fanilosendrison", 1)}
    seen = set()
    for name, text in workflows.items():
        blocks = list(step_blocks(text))
        action_lines = [line for line in text.splitlines()
                        if "uses:" in line and "actions/create-github-app-token" in line]
        mint_blocks = [block for block in blocks
                       if "actions/create-github-app-token" in block]
        if len(action_lines) != len(mint_blocks):
            raise AssertionError(f"unclassified action serialization: {name}")
        source_blocks = [block for block in blocks
                         if APP_ID in block or PRIVATE_KEY in block]
        # Every create-app-token use is inventoried, including an unknown App.
        for block in set(mint_blocks + source_blocks):
            if name not in sites or name in seen:
                raise AssertionError(f"unclassified source mint: {name}")
            seen.add(name)
            fields = literal_fields(block, 8)
            inputs = literal_fields(block, 10)
            if fields.get("uses") != ACTION or fields.get("id") != "source_auth":
                raise AssertionError(f"source action/identifier changed: {name}")
            if fields.get("with") != "":
                raise AssertionError(f"missing block input mapping: {name}")
            permissions = {key: value for key, value in inputs.items()
                           if key.startswith("permission-")}
            expected_permissions = V3_PERMISSIONS if name == V3_SITE else LEGACY_PERMISSIONS
            if permissions != expected_permissions:
                raise AssertionError(f"incorrect classified permission subset: {name}")
            job, owner, expected_bindings = sites[name]
            expected_inputs = {
                "app-id": APP_ID, "private-key": PRIVATE_KEY, "owner": owner,
                **expected_permissions,
            }
            if name == V3_SITE:
                expected_inputs["repositories"] = "review-broker"
            if inputs != expected_inputs:
                raise AssertionError(f"source inputs changed: {name}")
            # Reject anchors, merge keys, flow maps and nested input mappings;
            # they must not bypass the direct scalar-field oracle.
            input_text = block.split("        with:\n", 1)[1]
            for line in input_text.splitlines():
                if line.strip() and not re.fullmatch(r"          [\w-]+: .+", line):
                    raise AssertionError(f"unaudited source input syntax: {name}")
            before = text[:text.index(block)]
            jobs = re.findall(r"^  ([\w-]+):\s*$", before, re.MULTILINE)
            if not jobs or jobs[-1] != job:
                raise AssertionError(f"source mint moved to another job: {name}")
            bindings = re.findall(r"^          REVIEW_BROKER_SOURCE_TOKEN: (.+)$",
                                  text, re.MULTILINE)
            if bindings != [TOKEN] * expected_bindings:
                raise AssertionError(f"source token binding changed: {name}")
            if name == "private-source-qualification.yml":
                consumers = [literal_fields(candidate, 10) for candidate in blocks
                             if "      - name: Qualify exact read-only source acquisition\n"
                             in candidate]
                if len(consumers) != 1 or consumers[0].get("GH_TOKEN") != TOKEN:
                    raise AssertionError("qualification token binding changed")
        if name not in sites and "REVIEW_BROKER_SOURCE_TOKEN:" in text:
            raise AssertionError(f"unclassified source-token consumer: {name}")
    if seen != set(sites):
        raise AssertionError("source mint inventory incomplete")
    audit_private_source_dispatch(workflows["private-source-qualification.yml"])
    if hashlib.sha256(workflows[V3_SITE].encode()).hexdigest() != V3_WORKFLOW_SHA256:
        raise AssertionError("v3 approved-SHA workflow structure changed")
    return seen


class SourceAppCredentialScopeTests(unittest.TestCase):
    def setUp(self):
        self.workflows = {
            path.name: path.read_text(encoding="utf-8")
            for path in (ROOT / ".github" / "workflows").iterdir()
            if path.suffix in {".yml", ".yaml"}
        }

    def test_all_source_app_mints_have_explicit_classified_legacy_scope(self):
        self.assertEqual(audit_workflows(self.workflows), set(LEGACY_SITES) | {V3_SITE})

    def assert_rejected(self, name, old, new):
        workflows = dict(self.workflows)
        self.assertIn(old, workflows[name])
        workflows[name] = workflows[name].replace(old, new, 1)
        with self.assertRaises(AssertionError):
            audit_workflows(workflows)

    def test_removing_any_required_permission_is_rejected(self):
        for name in LEGACY_SITES:
            for permission in LEGACY_PERMISSIONS:
                with self.subTest(workflow=name, permission=permission):
                    self.assert_rejected(name, f"          {permission}: read\n", "")

    def test_removing_all_permissions_is_rejected(self):
        for name in LEGACY_SITES:
            workflows = dict(self.workflows)
            for permission in LEGACY_PERMISSIONS:
                workflows[name] = workflows[name].replace(
                    f"          {permission}: read\n", "")
            with self.subTest(workflow=name), self.assertRaises(AssertionError):
                audit_workflows(workflows)

    def test_issues_or_any_additional_permission_is_rejected(self):
        for name in LEGACY_SITES:
            for permission in ("issues", "actions", "workflows", "administration"):
                with self.subTest(workflow=name, permission=permission):
                    self.assert_rejected(
                        name, "          permission-metadata: read\n",
                        "          permission-metadata: read\n"
                        f"          permission-{permission}: read\n",
                    )

    def test_write_permission_is_rejected(self):
        for name in LEGACY_SITES:
            for permission in LEGACY_PERMISSIONS:
                with self.subTest(workflow=name, permission=permission):
                    self.assert_rejected(name, f"{permission}: read", f"{permission}: write")

    def test_unclassified_unrestricted_mint_in_new_workflow_is_rejected(self):
        workflows = dict(self.workflows)
        workflows["unclassified.yml"] = (
            "jobs:\n  other:\n    steps:\n"
            f"      - uses: {ACTION}\n        with:\n"
            f"          app-id: {APP_ID}\n          private-key: {PRIVATE_KEY}\n"
        )
        with self.assertRaises(AssertionError):
            audit_workflows(workflows)

    def test_added_mint_in_existing_workflow_is_rejected(self):
        for name in LEGACY_SITES:
            workflows = dict(self.workflows)
            workflows[name] += (
                f"      - uses: {ACTION}\n        with:\n"
                f"          app-id: {APP_ID}\n          private-key: {PRIVATE_KEY}\n"
            )
            with self.subTest(workflow=name), self.assertRaises(AssertionError):
                audit_workflows(workflows)

    def test_action_pin_and_token_identifier_cannot_change(self):
        for name in LEGACY_SITES:
            for old, new in ((ACTION, "actions/create-github-app-token@v2"),
                             ("id: source_auth", "id: other_auth")):
                with self.subTest(workflow=name, mutation=old):
                    self.assert_rejected(name, old, new)

    def test_source_token_cannot_be_replaced_by_job_token(self):
        for name in LEGACY_SITES:
            with self.subTest(workflow=name):
                self.assert_rejected(name, TOKEN, "${{ github.token }}")

    def test_source_credential_inputs_cannot_be_substituted(self):
        for name in LEGACY_SITES:
            with self.subTest(workflow=name):
                self.assert_rejected(name, PRIVATE_KEY, "${{ secrets.OTHER_KEY }}")

    def test_duplicate_or_merged_permissions_are_rejected(self):
        for name in LEGACY_SITES:
            for addition in ("          permission-metadata: write\n",
                             "          <<: *unrestricted\n"):
                with self.subTest(workflow=name, addition=addition):
                    self.assert_rejected(name, "          permission-metadata: read\n",
                                         "          permission-metadata: read\n" + addition)

    def test_private_source_dispatch_has_exact_admission_and_preserved_body(self):
        audit_private_source_dispatch(self.workflows["private-source-qualification.yml"])

    def test_private_source_dispatch_admission_mutations_are_rejected(self):
        text = self.workflows["private-source-qualification.yml"]
        guard = QUALIFICATION_HEADER.split("    if: >-\n", 1)[1].split(
            "    runs-on:", 1
        )[0]
        cases = {
            "manual trigger": ("  repository_dispatch:\n", "  workflow_dispatch:\n"),
            "alternate trigger": ("on:\n", "on:\n  push:\n"),
            "repository": ("github.repository == 'fanilosendrison/review-broker'",
                           "github.repository == 'other/repository'"),
            "event type": ("types: [review-broker-private-source-qualification]",
                           "types: [other-event]"),
            "event name": ("github.event_name == 'repository_dispatch' &&\n", ""),
            "action": ("github.event.action == 'review-broker-private-source-qualification'",
                       "github.event.action == 'other-event'"),
            "default ref": ("      github.ref == format('refs/heads/{0}', "
                            "github.event.repository.default_branch) &&\n", ""),
            "sender": ("github.event.sender.id == 30498238", "github.event.sender.id == 1"),
            "actor": ("      github.actor == 'fanilosendrison' &&\n", ""),
            "triggering actor": ("      github.triggering_actor == 'fanilosendrison'\n", ""),
            "whole guard": ("    if: >-\n" + guard, ""),
            "payload authority": ("github.event.sender.id", "github.event.client_payload.id"),
            "job secret": ("    runs-on: ubuntu-24.04\n",
                           "    env:\n      KEY: " + PRIVATE_KEY + "\n"
                           "    runs-on: ubuntu-24.04\n"),
        }
        for label, (old, new) in cases.items():
            with self.subTest(mutation=label):
                self.assertIn(old, text)
                with self.assertRaises(AssertionError):
                    audit_private_source_dispatch(text.replace(old, new, 1))

    def test_private_source_key_relocation_to_job_environment_is_rejected(self):
        text = self.workflows["private-source-qualification.yml"]
        relocated = text.replace(f"          private-key: {PRIVATE_KEY}\n", "", 1)
        relocated = relocated.replace(
            "jobs:\n", "jobs:\n  unguarded:\n"
            f"    env:\n      KEY: {PRIVATE_KEY}\n", 1
        )
        self.assertNotEqual(text, relocated)
        with self.assertRaises(AssertionError):
            audit_private_source_dispatch(relocated)

    def test_private_source_dispatch_secret_body_mutations_are_rejected(self):
        text = self.workflows["private-source-qualification.yml"]
        cases = {
            "extra mint": ("    steps:\n", "    steps:\n"
                           f"      - uses: {ACTION}\n"),
            "unguarded job": ("jobs:\n", "jobs:\n  unguarded:\n"
                              f"    env:\n      KEY: {PRIVATE_KEY}\n"),
            "issues permission": ("          permission-metadata: read\n",
                                  "          permission-metadata: read\n"
                                  "          permission-issues: read\n"),
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
            ("      github.sha == vars.REVIEW_BROKER_V3_SOURCE_QUALIFICATION_SHA\n", ""),
            ("repository_dispatch:", "workflow_dispatch:"),
            ("on:\n", "on:\n  pull_request_target:\n"),
            ("          repositories: review-broker\n", ""),
            ("          permission-issues: read\n", ""),
            ("permission-contents: read", "permission-contents: write"),
            (ACTION, "actions/create-github-app-token@v2"),
            ("    steps:\n", f"    steps:\n      - uses: {ACTION}\n"),
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
