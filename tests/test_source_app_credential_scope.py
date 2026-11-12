"""Closed declared-scope inventory; no claim about live installation grants."""
from collections import Counter
from functools import lru_cache
import hashlib
from pathlib import Path
import re
import unittest
import yaml
import source_app_credential_path_syntax as syntax

ROOT = Path(__file__).parents[1]


@lru_cache(maxsize=256)
def decoded_workflow(text):
    values = tuple(e.value for e in yaml.parse(text) if isinstance(e, yaml.events.ScalarEvent))
    document = yaml.safe_load(text)
    jobs = document.get("jobs", {}) if isinstance(document, dict) else {}
    jobs = [job for job in jobs.values() if isinstance(job, dict)] if isinstance(jobs, dict) else []
    conditions = jobs + [step for job in jobs for step in job.get("steps", []) if isinstance(step, dict)]
    bindings = ([document] if isinstance(document, dict) else []) + conditions
    keys = frozenset(k for n in bindings for role in ("env", "with", "outputs") if isinstance(n.get(role), dict) for k in n[role] if isinstance(k, str))
    return values, frozenset(n["if"] for n in conditions if isinstance(n.get("if"), str)), keys, tuple(n["uses"] for n in conditions if isinstance(n.get("uses"), str)), frozenset(n["id"].casefold() for n in conditions if isinstance(n.get("id"), str))
ACTION = "actions/create-github-app-token@fee1f7d63c2ff003460e3d139729b119787bc349"
APP_MINT_ACTION = re.compile(r"^actions/create-github-app-token(?:@|$)", re.IGNORECASE)
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
QUALIFICATION_HEADER_SHA256 = "73bced1a1d34ce4491e0eecec6c4547c687a4212eea7021aa9c5dc1bb88a916b"
QUALIFICATION_STEPS_SHA256 = "51f378720f91b47597116eaabe6003ce98b160f1db0ae34947271bd080e04dc7"


def audit_private_source_dispatch(text):
    """Preserve the independently accepted admission prefix and entire steps body."""
    header, separator, body = text.partition("    steps:\n")
    if not separator or hashlib.sha256((header + separator).encode()).hexdigest() != QUALIFICATION_HEADER_SHA256:
        raise AssertionError("private-source dispatch admission changed")
    if hashlib.sha256(body.encode()).hexdigest() != QUALIFICATION_STEPS_SHA256:
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
    for key, value in re.findall(r"^" + " " * indent + r"([\w-]+):(?: (.*))?$", block, re.MULTILINE):
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


def source_paths(value, *, template):
    """Authorize positions from neutral syntax, never names found in arbitrary suffixes."""
    result, paths = syntax.scan_paths(value, roots=("steps", "vars", "secrets"), template=template), []
    for access in (a for a in result.accesses if a.root == "steps"):
        selectors = access.selectors or next(iter(access.projections), ())
        if not access.selectors and access.opaque:
            paths.append(None)
        if not selectors or selectors[0].kind == "dynamic":
            paths.append(None)
        elif selectors[0].literal_value.casefold() in {"source", "source_auth"}:
            literal = tuple(s.literal_value.casefold() for s in selectors if s.kind == "literal")
            complete = not access.opaque and len(selectors) == len(literal) == 3 and literal[1] == "outputs" and literal[2] in {"token", "app-slug", "installation-id"}
            paths.append(literal if complete else False)
    authority = any(a.root != "steps" and (not a.selectors or (a.selectors[0].kind == "literal" and a.selectors[0].literal_value.casefold() in {"review_broker_source_app_id", "review_broker_source_app_private_key"})) for a in result.accesses)
    return tuple(paths), result.issues, authority


def audit_workflows(workflows):
    sites, seen = site_contracts(), set()
    for name, text in workflows.items():
        try:
            decoded, conditions, mapping_keys, uses, producer_ids = decoded_workflow(text)
        except (yaml.YAMLError, ValueError, TypeError, RecursionError) as exc:
            raise AssertionError(f"unsupported YAML serialization: {name}") from exc
        accesses = [(value, *source_paths(value, template=value not in conditions)) for value in decoded]
        if name not in sites and (any(APP_MINT_ACTION.match(value) for value in uses) or any(authority for _, _, _, authority in accesses)):
            raise AssertionError(f"unclassified source mint: {name}")
        blocks = list(step_blocks(text)) if name in sites else []
        mint_blocks = [block for block in blocks if APP_MINT_ACTION.match(literal_fields(block, 8).get("uses", ""))]
        if sum(bool(APP_MINT_ACTION.match(value)) for value in uses) != len(mint_blocks):
            raise AssertionError(f"unclassified action serialization: {name}")
        for block in mint_blocks:
            if name not in sites or name in seen:
                raise AssertionError(f"unclassified source mint: {name}")
            seen.add(name)
            site, fields, inputs = sites[name], literal_fields(block, 8), literal_fields(block, 10)
            if (fields.get("uses"), fields.get("id"), fields.get("with")) != (ACTION, site["step"], ""):
                raise AssertionError(f"source action/identifier or block input mapping changed: {name}")
            permissions = {k: v for k, v in inputs.items() if k.startswith("permission-")}
            if permissions != site["permissions"]:
                raise AssertionError(f"incorrect classified permission subset: {name}")
            expected = {"app-id": APP_ID, "private-key": PRIVATE_KEY, "owner": site["owner"], **site["permissions"]}
            if site["repositories"] is not None:
                expected["repositories"] = site["repositories"]
            if inputs != expected:
                raise AssertionError(f"source inputs changed: {name}")
            if any(line.strip() and not re.fullmatch(r"          [\w-]+: .+", line) for line in block.split("        with:\n", 1)[1].splitlines()):
                raise AssertionError(f"unaudited source input syntax: {name}")
            if enclosing_job(text, block) != site["job"]:
                raise AssertionError(f"source mint moved to another job: {name}")
        reserved_scalars = [value for value, paths, _, _ in accesses if any(path is not None for path in paths)]
        source_keys = bool(set(SOURCE_KEYS) & mapping_keys)
        relevant = name in sites or source_keys or bool(reserved_scalars) or bool(producer_ids & {"source", "source_auth"})
        if relevant and (any(issues for _, _, issues, _ in accesses) or any(path is None or path is False for _, paths, _, _ in accesses for path in paths)):
            raise AssertionError(f"unclassified source-token consumer / reserved source path: {name}")
        if name not in sites:
            if source_keys or reserved_scalars:
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


class StepsSyntaxTests(syntax.SyntaxContractTests):
    extra_position_cases = (("steps.source.outputs.token", ("source", "outputs", "token")),
                            ("steps['source']['outputs']['token']", ("source", "outputs", "token")),
                            ("steps.fallback.outputs.source", ("fallback", "outputs", "source")),
                            ("steps[inputs.step].outputs.token", (None, "outputs", "token")),
                            ("steps.source_auth[format('{0}', 'outputs')].token", ("source_auth", None, "token")))


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
        self.assertIn(old, self.workflows[name])
        workflows = {**self.workflows, name: self.workflows[name].replace(old, new, 1)}
        with self.assertRaisesRegex(AssertionError, reason):
            audit_workflows(workflows)

    def assert_added(self, scalar, *, rejected, marked=False, producers=("fallback", "unrelated", "source_helper", "outputs", "source_data")):
        prefix = "name: Policy corpus\nenv:\n" + ("  REVIEW_BROKER_SOURCE_TOKEN: fixture\n" if marked else "") + f"  NOTE: |\n      - name: Documentation only\n        uses: {ACTION}\non:\n  workflow_dispatch:\n    inputs:\n      step:\n        type: string\n        default: fallback\njobs:\n  extra:\n    runs-on: ubuntu-24.04\n    steps:\n"
        prefix += "".join(f"      - id: {p}\n        run: printf 'token=fixture\\nsource=fixture\\nsource_auth=fixture\\n' >> $GITHUB_OUTPUT\n" for p in producers)
        quoted = scalar.replace("'", "''")
        for tail in (f"      - env:\n          {'REVIEW_BROKER_SOURCE_TOKEN' if marked else 'UNRELATED'}: '{quoted}'\n        run: ':'\n", f"      - run: 'echo {quoted}'\n"):
            text = prefix + tail
            with self.subTest(scalar=scalar, marked=marked, rejected=rejected, rendering=tail):
                if rejected:
                    with self.assertRaises(AssertionError):
                        audit_workflows({**self.workflows, "added.yml": text})
                else:
                    self.assertEqual(audit_workflows({**self.workflows, "added.yml": text}), self.expected)

    def test_legacy_scope_and_input_mutations_are_rejected(self):
        mutations = [case for p in LEGACY_PERMISSIONS for case in ((f"          {p}: read\n", ""), (f"{p}: read", f"{p}: write"))]
        mutations += [("          permission-metadata: read\n", "          permission-metadata: read\n" + addition)
                      for addition in [*(f"          permission-{p}: read\n" for p in ("issues", "actions", "workflows", "administration")),
                                       "          permission-metadata: write\n", "          <<: *unrestricted\n"]]
        mutations += [(ACTION, "actions/create-github-app-token@v2"), ("id: source_auth", "id: other_auth"),
                      (TOKEN, "${{ github.token }}"), (PRIVATE_KEY, "${{ secrets.OTHER_KEY }}")]
        for name in LEGACY_SITES:
            text = self.workflows[name]
            cases = mutations + [(text, re.sub(r"^          permission-(contents|pull-requests|metadata): read\n", "", text, flags=re.MULTILINE))]
            for old, new in cases:
                with self.subTest(workflow=name, mutation=old, replacement=new):
                    self.assert_rejected(name, old, new)

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
            line = f"          {key}: {value}\n"
            mutations += [(line, "", "consumer binding"), (value, "${{ github.token }}", "consumer binding"), (line, line * 2, "consumer binding")]
        for name, (job, invocation) in OPERATIONAL_SITES.items():
            cases = mutations + [(f"  {job}:\n", "  misplaced:\n", "another job"),
                                 (invocation[1], "untrusted-consumer", "consumer invocation")]
            mint = next(b for b in step_blocks(self.workflows[name]) if ACTION in b)
            cases.append((mint, mint.replace("        with:\n", "        with: {}\n", 1), "block input mapping|serialization"))
            for old, new, reason in cases:
                with self.subTest(workflow=name, mutation=old, reason=reason):
                    self.assert_rejected(name, old, new, reason)

        for name in (V3_SITE, V3_ADAPTER_SITE):
            for old, new, reason in mutations:
                if reason in {"permission subset", "source inputs"}:
                    with self.subTest(workflow=name, mutation=old):
                        self.assert_rejected(name, old, new, reason)
            self.assert_rejected(name, self.workflows[name], self.workflows[name] + "\n", "workflow structure")

    def test_known_site_consumers_and_legacy_invocations_are_closed(self):
        for name, site in site_contracts().items():
            with self.subTest(workflow=name, wrong_producer=True):
                self.assert_rejected(name, site["token"], TOKEN if site["step"] == "source" else V3_TOKEN)
            for field in ("token", "app-slug", "installation-id"):
                value = f"${{{{ steps.{site['step']}.outputs.{field} }}}}"
                extra = f"      - name: Unclassified source consumer\n        env:\n          GH_TOKEN: {value}\n        run: untrusted-consumer\n"
                with self.subTest(workflow=name, consumer=field):
                    self.assert_rejected(name, self.workflows[name], self.workflows[name] + extra, "output consumer count")
            mint = next(b for b in step_blocks(self.workflows[name]) if ACTION in b)
            with self.subTest(workflow=name, duplicate_mint=True):
                self.assert_rejected(name, self.workflows[name], self.workflows[name] + mint, "unclassified source mint")
            if name in LEGACY_SITES:
                for block in step_blocks(self.workflows[name]):
                    if TOKEN in block:
                        before, separator, body = block.partition("        run:")
                        self.assertTrue(separator)
                        with self.subTest(workflow=name, invocation=hashlib.sha256(block.encode()).hexdigest()):
                            self.assert_rejected(name, block, before + "        run: untrusted-consumer\n", "workflow structure|private-source secret")

    def test_unknown_mints_consumers_and_serializations_are_rejected(self):
        escaped = ACTION.replace("token", r"\u0074oken")
        text = f'jobs:\n  extra:\n    runs-on: ubuntu-24.04\n    steps:\n      - uses: "{escaped}"\n'
        with self.assertRaisesRegex(AssertionError, "unclassified source mint"):
            audit_workflows({**self.workflows, "escaped.yml": text})
        mint = f"      - uses: {ACTION}\n        with:\n          app-id: {APP_ID}\n          private-key: {PRIVATE_KEY}\n"
        with self.assertRaisesRegex(AssertionError, "unclassified source mint"):
            audit_workflows({**self.workflows, "unclassified.yml": "jobs:\n  other:\n    steps:\n" + mint})
        for field in (*SOURCE_KEYS, V3_TOKEN, *V3_IDENTITY_BINDINGS.values()):
            workflows = {**self.workflows, "unknown-consumer.yml": f"env:\n  {field}: untrusted\n"}
            with self.subTest(consumer=field), self.assertRaisesRegex(AssertionError, "unclassified source-token consumer"):
                audit_workflows(workflows)
        dynamic = [f"steps[{key}].outputs.token" for key in ("inputs.step", "github.event.action", "matrix.step", "env.STEP", "format('{0}', 'source_auth')")]
        for step in ("source", "source_auth"):
            roots = (f"steps.{step}", f"steps['{step}']", f'steps["{step}"]', f"(steps).{step}", f"steps[('{step}')]")
            suffixes = ("", ".outputs", ".outputs.expiration", ".outputs.owner", ".outputs.token.foo", ".outputs.token[0]", ".outputs.*",
                        "[inputs.property].token", "[format('{0}', 'outputs')].token", ".outputs[inputs.name]", ".outputs[format('{0}', 'token')]", "['outputs']['token']")
            bodies = [root + suffix for root in roots for suffix in suffixes]
            bodies += [f"{fn}({root}{suffix})" for root in roots for suffix in ("", ".outputs", ".outputs.token") for fn in ("toJSON", "fromJSON")]
            bodies += [f"format('{{0}}', steps.{step}.outputs.token)", f"fromJSON(toJSON(steps) || '{{}}').{step}.outputs.token", f"steps.{step}.outputs.token || steps[inputs.step].outputs.token", f"fromJSON(format('[{{0}}]', toJSON(steps)))[0].{step}.outputs.token", f"fromJSON(format('{{{{\"box\":{{0}}}}}}', toJSON(steps))).box.{step}.outputs.token"]
            for body, marked in [(b, False) for b in bodies] + [(b, True) for b in dynamic]:
                expression = "${{ " + body + " }}"
                with self.subTest(producer=step, expression=expression):
                    self.assert_rejected(V3_CONTROLLER_SITE if step == "source" else "review-reconciler.yml", V3_TOKEN if step == "source" else TOKEN, expression)
                    self.assert_added(expression, rejected=True, marked=marked, producers=(step,))
        foreign = [f"steps.{p}.outputs.{leaf}" for p, leaf in (("fallback", "source"), ("fallback", "source_auth"), ("source_helper", "token"), ("unrelated", "source"), ("outputs", "source"), ("source_data", "token"))]
        controls = foreign + dynamic + [f"{a} {op} {b}" for a in dynamic for b in foreign for op in ("||", "&&")] + [f"{b} || {a}" for a in dynamic for b in foreign]
        controls += ["fromJSON(format('[{0}]', toJSON(steps)))[0].fallback.outputs.source", "toJSON(vars.FOREIGN)", "toJSON(secrets.FOREIGN)"]
        for body in controls + [f"toJSON({b})" for b in foreign] + ["format('source_auth outputs token')", "'steps.source.outputs.token'"]:
            self.assert_added("${{ " + body + " }}", rejected=False)
        for scalar in ("source", "source_auth", "steps.source.outputs.token", "review_broker_source_app_id", "review_broker_source_app_private_key", ACTION, "${{ format('label={0}', 'review_broker_source_app_id') }}"):
            self.assert_added(scalar, rejected=False)
        for job_id in SOURCE_KEYS:
            with self.subTest(job_identifier=job_id):
                self.assertEqual(audit_workflows({**self.workflows, "job-id.yml": f"name: Data identifier\non: workflow_dispatch\njobs:\n  {job_id}:\n    runs-on: ubuntu-24.04\n    steps:\n      - run: ':'\n"}), self.expected)
        for scalar in (APP_ID, PRIVATE_KEY, "${{ fromJSON(toJSON(vars)).REVIEW_BROKER_SOURCE_APP_ID }}", "${{ fromJSON(format('[{0}]', toJSON(secrets)))[0].REVIEW_BROKER_SOURCE_APP_PRIVATE_KEY }}", "${{ toJSON(secrets) }}"):
            self.assert_added(scalar, rejected=True)
        for body in (pattern.format(a=dynamic[0], b=foreign[0], r=reserved) for pattern in ("{a} || {r} || {b}", "{r} || {a} || {b}", "{a} || {b} || {r}") for reserved in ("steps.source.outputs.token", "steps.source_auth.outputs.token")):
            self.assert_added("${{ " + body + " }}", rejected=True, producers=("source", "source_auth", "fallback"))
        workflows = {**self.workflows, "serialized.yml": f"jobs:\n  other:\n    steps:\n    - uses: {ACTION}\n"}
        with self.assertRaisesRegex(AssertionError, "serialization|unclassified source mint"):
            audit_workflows(workflows)

    def test_private_source_dispatch_admission_and_body_mutations_are_rejected(self):
        text = self.workflows["private-source-qualification.yml"]
        audit_private_source_dispatch(text)
        guard = text.split("    if: >-\n", 1)[1].split("    runs-on:", 1)[0]
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
            "extra mint": ("    steps:\n", "    steps:\n" + f"      - uses: {ACTION}\n"),
            "unguarded job": ("jobs:\n", "jobs:\n  unguarded:\n" + f"    env:\n      KEY: {PRIVATE_KEY}\n"),
            "issues permission": ("          permission-metadata: read\n", "          permission-metadata: read\n          permission-issues: read\n"),
            "job token": (TOKEN, "${{ github.token }}"),
            "isolation removed": ("                *) unset \"$variable\" ;;", ""),
            "key relocation": (text, text.replace(f"          private-key: {PRIVATE_KEY}\n", "", 1).replace("jobs:\n", "jobs:\n  unguarded:\n" + f"    env:\n      KEY: {PRIVATE_KEY}\n", 1)),
        }
        cases.update({p: (f"{p}: read", f"{p}: write") for p in LEGACY_PERMISSIONS})
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
