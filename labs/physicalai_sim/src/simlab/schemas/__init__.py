"""Exported JSON Schema for SIMLAB-IF-001@r1 (generated from the contract models).

`python -m simlab.schemas --write` regenerates; tests/core/test_schemas.py fails
when the committed export drifts from the models.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def generate() -> dict[str, dict]:
    from simlab.contracts.records import RECORDS, SCHEMA_VERSION

    out = {}
    for name, cls in RECORDS.items():
        schema = cls.model_json_schema(mode="validation")
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"https://simlab.local/schemas/{SCHEMA_VERSION}/{name}.schema.json"
        schema["x-simlab-interface"] = SCHEMA_VERSION
        out[name] = schema
    return out


def path_for(name: str) -> Path:
    return HERE / f"{name}.schema.json"


def write() -> list[Path]:
    paths = []
    for name, schema in generate().items():
        p = path_for(name)
        p.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
        paths.append(p)
    return paths


def drift() -> list[str]:
    bad = []
    for name, schema in generate().items():
        p = path_for(name)
        if not p.exists() or json.loads(p.read_text()) != schema:
            bad.append(name)
    return bad


if __name__ == "__main__":
    if "--write" in sys.argv:
        for p in write():
            print(p)
    else:
        d = drift()
        print("drift:", d or "none")
        raise SystemExit(1 if d else 0)
