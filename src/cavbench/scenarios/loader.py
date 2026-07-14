"""Scenario pack loading, schema validation, and digest computation."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema

from cavbench.errors import ScenarioLoadError, SchemaValidationError, UnsupportedSchemaVersion
from cavbench.scenarios.models import ScenarioDefinition, ScenarioPack

SUPPORTED_SCHEMA_VERSION = "1.0"


@lru_cache(maxsize=1)
def _scenario_schema() -> dict[str, Any]:
    text = resources.files("cavbench.scenarios.schemas").joinpath("scenario-v1.schema.json").read_text()
    schema: dict[str, Any] = json.loads(text)
    return schema


def validate_scenario_document(data: dict[str, Any], *, source: str) -> None:
    schema_version = data.get("schema_version")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise UnsupportedSchemaVersion(source, str(schema_version), SUPPORTED_SCHEMA_VERSION)
    try:
        jsonschema.validate(data, _scenario_schema())
    except jsonschema.ValidationError as exc:
        raise SchemaValidationError(source, exc.message) from exc


def _digest(scenario_dicts: list[dict[str, Any]]) -> str:
    canonical = json.dumps(scenario_dicts, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_pack_from_directory(directory: Path, *, pack_id: str | None = None) -> ScenarioPack:
    directory = Path(directory)
    pack_meta_path = directory / "pack.json"
    if not pack_meta_path.exists():
        raise ScenarioLoadError(f"Missing pack.json in {directory}")
    pack_meta = json.loads(pack_meta_path.read_text())

    scenarios_dir = directory / "scenarios"
    if not scenarios_dir.is_dir():
        raise ScenarioLoadError(f"Missing scenarios/ directory in {directory}")

    scenario_files = sorted(scenarios_dir.glob("*.json"))
    if not scenario_files:
        raise ScenarioLoadError(f"No scenario files found in {scenarios_dir}")

    scenarios: dict[str, ScenarioDefinition] = {}
    raw_dicts: list[dict[str, Any]] = []
    for path in scenario_files:
        data = json.loads(path.read_text())
        validate_scenario_document(data, source=str(path))
        definition = ScenarioDefinition.from_dict(data)
        if definition.id in scenarios:
            raise ScenarioLoadError(f"Duplicate scenario id {definition.id!r} in {path}")
        scenarios[definition.id] = definition
        raw_dicts.append(data)

    scenario_ids = tuple(sorted(scenarios))
    declared_ids = pack_meta.get("scenario_ids")
    if declared_ids is not None and set(declared_ids) != set(scenario_ids):
        raise ScenarioLoadError(
            f"pack.json scenario_ids does not match files on disk in {directory}: "
            f"declared={sorted(declared_ids)} found={list(scenario_ids)}"
        )

    return ScenarioPack(
        pack_id=pack_id or pack_meta["pack_id"],
        pack_version=pack_meta["pack_version"],
        schema_version=pack_meta.get("schema_version", SUPPORTED_SCHEMA_VERSION),
        description=pack_meta.get("description", ""),
        scenario_ids=scenario_ids,
        digest=_digest(sorted(raw_dicts, key=lambda d: d["id"])),
        scenarios=scenarios,
    )


@lru_cache(maxsize=8)
def load_builtin_pack(pack_id: str = "core-v1") -> ScenarioPack:
    pack_root = resources.files("cavbench.scenarios.packs").joinpath(pack_id)
    with resources.as_file(pack_root) as directory:
        return load_pack_from_directory(directory, pack_id=pack_id)
