"""Validates contracts/examples/*.json against contracts/schemas/*.json.
Pure offline test — no services required.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from referencing import Registry, Resource

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPO_ROOT / "contracts" / "schemas"
EXAMPLES_DIR = REPO_ROOT / "contracts" / "examples"


def _registry() -> Registry:
    resources = []
    for f in SCHEMAS_DIR.glob("*.json"):
        resources.append((f.name, Resource.from_contents(json.loads(f.read_text()))))
    return Registry().with_resources(resources)


def test_travel_request_example_matches_schema():
    schema = json.loads((SCHEMAS_DIR / "travel-request.schema.json").read_text())
    example = json.loads((EXAMPLES_DIR / "travel-request.example.json").read_text())
    jsonschema.Draft202012Validator(schema, registry=_registry()).validate(example)


def test_travel_response_example_matches_schema():
    schema = json.loads((SCHEMAS_DIR / "travel-response.schema.json").read_text())
    example = json.loads((EXAMPLES_DIR / "travel-response.example.json").read_text())
    jsonschema.Draft202012Validator(schema, registry=_registry()).validate(example)


def test_flight_result_example_matches_schema():
    schema = json.loads((SCHEMAS_DIR / "flight-result.schema.json").read_text())
    example = json.loads((EXAMPLES_DIR / "flight-result.example.json").read_text())
    jsonschema.Draft202012Validator(schema, registry=_registry()).validate(example)


def test_hotel_result_example_matches_schema():
    schema = json.loads((SCHEMAS_DIR / "hotel-result.schema.json").read_text())
    example = json.loads((EXAMPLES_DIR / "hotel-result.example.json").read_text())
    jsonschema.Draft202012Validator(schema, registry=_registry()).validate(example)


def test_all_schemas_are_valid_json_schema():
    for f in SCHEMAS_DIR.glob("*.json"):
        schema = json.loads(f.read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
