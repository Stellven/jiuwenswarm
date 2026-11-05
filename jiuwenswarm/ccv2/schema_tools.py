"""Offline validators for the published schema bundle; no adapter imports."""
import json
from functools import lru_cache
from pathlib import Path
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

SCHEMAS = Path(__file__).resolve().parent/'schemas'


@lru_cache(maxsize=None)
def validator(filename, definition=None):
    registry = Registry()
    documents = {}
    for path in SCHEMAS.glob('*.schema.json'):
        schema = json.loads(path.read_bytes())
        schema['$id'] = path.as_uri()
        Draft202012Validator.check_schema(schema)
        documents[path.name] = schema
        registry = registry.with_resource(path.as_uri(), Resource.from_contents(schema))
    schema = documents[filename]
    if definition:
        schema = {'$schema': schema['$schema'], '$id': schema['$id']+'?selected',
                  '$ref': documents[filename]['$id']+'#/$defs/'+definition}
    return Draft202012Validator(schema, registry=registry)


def validate(filename, value, definition=None):
    validator(filename, definition).validate(value)
