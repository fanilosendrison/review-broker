"""Static compatibility and local-contract regressions for reviewer output schemas."""
from copy import deepcopy
import hashlib
from importlib import resources
import inspect
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from review_broker.pilot_output import pilot_output
from review_broker import pilot_synthetic, validation


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "src/review_broker/schemas"
FULL_PATH = SCHEMAS / "reviewer-findings-v1.schema.json"
WIRE_PATH = SCHEMAS / "reviewer-findings-v1.codex-wire.schema.json"
ALLOWED_WIRE_KEYWORDS = {
    "type", "properties", "required", "additionalProperties", "items", "enum",
}
FORBIDDEN_WIRE_KEYWORDS = {
    "uniqueItems", "minLength", "maxLength", "$schema", "$id", "allOf",
    "not", "if", "then", "else",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_bytes())


def _object_shapes(schema: dict, path: tuple[str, ...] = ()) -> dict:
    shapes = {}
    if schema.get("type") == "object":
        properties = schema["properties"]
        shapes[path] = (tuple(properties), tuple(schema["required"]))
        for name, child in properties.items():
            shapes.update(_object_shapes(child, path + (name,)))
    if schema.get("type") == "array":
        shapes.update(_object_shapes(schema["items"], path + ("[]",)))
    return shapes


def _wire_schema_errors(schema: dict, path: tuple[str, ...] = ()) -> list[str]:
    errors = []
    unknown = set(schema) - ALLOWED_WIRE_KEYWORDS
    if unknown:
        errors.append(f"{path}: unsupported {sorted(unknown)}")
    if set(schema) & FORBIDDEN_WIRE_KEYWORDS:
        errors.append(f"{path}: forbidden keyword")
    if schema.get("type") == "object":
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is not False:
            errors.append(f"{path}: open object")
        if set(schema.get("required", [])) != set(properties):
            errors.append(f"{path}: required/property mismatch")
        for name, child in properties.items():
            errors.extend(_wire_schema_errors(child, path + (name,)))
    if schema.get("type") == "array":
        if "items" not in schema:
            errors.append(f"{path}: missing items")
        else:
            errors.extend(_wire_schema_errors(schema["items"], path + ("[]",)))
    return errors


def _valid_output() -> dict:
    return {
        "schema_version": 1,
        "request_id": "request:sha256:" + "a" * 64,
        "subject_id": "subject:sha256:" + "b" * 64,
        "packet_id": "packet:sha256:" + "c" * 64,
        "verdict": "NO_GO",
        "sources_examined": ["S001"],
        "findings": [{
            "id": "F001",
            "category": "contradiction",
            "claim": "The age boundary is incorrect.",
            "consequence": "An invalid age is accepted.",
            "evidence": [{"source_id": "S001", "line": 3, "quote": "return age > 18"}],
        }],
        "remaining_uncertainties": ["Runtime behavior was not exercised."],
    }


class WireSchemaCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.full = _load(FULL_PATH)
        self.wire = _load(WIRE_PATH)
        self.full_validator = Draft202012Validator(self.full)
        self.wire_validator = Draft202012Validator(self.wire)

    def test_wire_schema_uses_only_conservative_strict_keywords(self):
        self.assertEqual(self.wire["type"], "object")
        self.assertEqual(_wire_schema_errors(self.wire), [])
        serialized = json.dumps(self.wire)
        for keyword in FORBIDDEN_WIRE_KEYWORDS:
            self.assertNotIn(f'"{keyword}"', serialized)

    def test_wire_and_full_schemas_have_identical_object_hierarchy(self):
        self.assertEqual(_object_shapes(self.wire), _object_shapes(self.full))
        self.assertEqual(self.wire["properties"]["schema_version"], {
            "type": "integer", "enum": [1],
        })
        self.assertEqual(
            self.wire["properties"]["verdict"]["enum"],
            self.full["properties"]["verdict"]["enum"],
        )
        wire_category = self.wire["properties"]["findings"]["items"]["properties"]["category"]
        full_category = self.full["properties"]["findings"]["items"]["properties"]["category"]
        self.assertEqual(wire_category["enum"], full_category["enum"])

    def test_locally_valid_output_is_wire_valid_without_mutating_schemas(self):
        before = (hashlib.sha256(FULL_PATH.read_bytes()).hexdigest(),
                  hashlib.sha256(WIRE_PATH.read_bytes()).hexdigest())
        value = _valid_output()
        self.full_validator.validate(value)
        self.wire_validator.validate(value)
        after = (hashlib.sha256(FULL_PATH.read_bytes()).hexdigest(),
                 hashlib.sha256(WIRE_PATH.read_bytes()).hexdigest())
        self.assertEqual(after, before)

    def test_full_schema_rejects_constraints_intentionally_absent_from_wire(self):
        cases = {}
        cases["duplicate sources"] = lambda value: value.update(sources_examined=["S001", "S001"])
        cases["request id"] = lambda value: value.update(request_id="bad")
        cases["subject id"] = lambda value: value.update(subject_id="bad")
        cases["packet id"] = lambda value: value.update(packet_id="bad")
        cases["finding id"] = lambda value: value["findings"][0].update(id="bad")
        cases["source id"] = lambda value: value["findings"][0]["evidence"][0].update(source_id="bad")
        cases["line zero"] = lambda value: value["findings"][0]["evidence"][0].update(line=0)
        cases["empty quote"] = lambda value: value["findings"][0]["evidence"][0].update(quote="")
        cases["short claim"] = lambda value: value["findings"][0].update(claim="bad")
        cases["short consequence"] = lambda value: value["findings"][0].update(consequence="bad")
        cases["too many findings"] = lambda value: value.update(findings=value["findings"] * 101)
        cases["too much evidence"] = lambda value: value["findings"][0].update(
            evidence=value["findings"][0]["evidence"] * 11,
        )
        cases["too many uncertainties"] = lambda value: value.update(
            remaining_uncertainties=["known"] * 101,
        )
        cases["missing field"] = lambda value: value.pop("verdict")
        cases["unexpected field"] = lambda value: value.update(unexpected=True)
        for name, mutate in cases.items():
            with self.subTest(name=name):
                value = deepcopy(_valid_output())
                mutate(value)
                self.assertFalse(self.full_validator.is_valid(value))

    def test_actual_call_sites_keep_wire_and_full_roles_separate(self):
        synthetic_source = inspect.getsource(pilot_synthetic)
        self.assertIn('"reviewer-findings-v1.codex-wire.schema.json"', synthetic_source)
        self.assertNotIn('"reviewer-findings-v1.schema.json"', synthetic_source)
        self.assertIn("_findings_schema()", inspect.getsource(pilot_output))
        self.assertIn(
            'joinpath("reviewer-findings-v1.schema.json")',
            inspect.getsource(validation._findings_schema),
        )
        workflow = (ROOT / ".github/workflows/review-request.yml").read_text()
        self.assertEqual(workflow.count("reviewer-findings-v1.codex-wire.schema.json"), 5)
        self.assertNotIn("broker-dist/reviewer-findings-v1.schema.json", workflow)
        self.assertIn(
            '--schema "$REMOTE_ROOT/broker-dist/reviewer-findings-v1.codex-wire.schema.json"',
            workflow,
        )

    def test_package_resources_expose_both_schemas(self):
        packaged = resources.files("review_broker.schemas")
        for name in ("reviewer-findings-v1.schema.json",
                     "reviewer-findings-v1.codex-wire.schema.json"):
            self.assertTrue(packaged.joinpath(name).is_file())
        package_rule = (ROOT / "pyproject.toml").read_text()
        self.assertIn('review_broker = ["schemas/*.json"', package_rule)


if __name__ == "__main__":
    unittest.main()
