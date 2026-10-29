"""Validate neutral published contract DATA, without importing core code."""
import json
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .request_validation import IntegrityFault


class ContractData:
    def __init__(self, root=None):
        self.root = Path(root) if root else Path(str(files("jiuwenswarm.research_contracts")))
        catalog = json.loads((self.root / "catalog.json").read_text(encoding="utf-8"))
        self.schemas = {}
        resources = []
        for path in sorted((self.root / "schemas").glob("*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            if "$id" in doc: resources.append((doc["$id"], Resource.from_contents(doc)))
        self.registry = Registry().with_resources(resources)
        for row in catalog["contracts"]:
            self.schemas[row["name"]] = json.loads((self.root / row["schema"]).read_text(encoding="utf-8"))
            self.schemas[row["schema_id"]] = self.schemas[row["name"]]
        # The core publishes field schemas once; sides consume them as data only.
        lookup = json.loads((self.root / "contract_lookup.json").read_text(encoding="utf-8"))
        for name, location in lookup["contracts"].items():
            target = location["schema_id"]
            if location.get("definition"):
                target += "#/$defs/" + location["definition"]
            self.schemas[name] = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$ref": target}

    def validate(self, name, value):
        schema = self.schemas.get(name)
        if schema is None: raise IntegrityFault("contract_data_unavailable:" + name)
        try:
            Draft202012Validator(schema, registry=self.registry).validate(value)
        except Exception:
            # Do not echo a value, credential or complete request in a diagnostic.
            raise IntegrityFault("contract_structure:" + name) from None

