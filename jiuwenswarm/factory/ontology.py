"""Small, local vocabulary for engine evidence and component selection."""
from functools import lru_cache
from pathlib import Path

import yaml

PATH = Path(__file__).parent / 'ccs/expert_streaming/ONTOLOGY.yaml'


@lru_cache(maxsize=1)
def load():
    ontology = yaml.safe_load(PATH.read_text())
    quantities = ontology['quantities']
    for spec in quantities.values():
        if (spec['phase'] not in {'prompt', 'decode', 'run'}
                or spec['region'] not in ontology['entities']['regions']
                or set(spec['distinct_from']) - quantities.keys()):
            raise ValueError('Invalid engine ontology quantity')
    return ontology


def validate_quantities(ids):
    if not isinstance(ids, list) or any(not isinstance(q, str) for q in ids):
        raise ValueError('Quantity ids must be a list of strings')
    unknown = set(ids) - load()['quantities'].keys()
    if unknown:
        raise ValueError('Unknown ontology quantities: ' + ', '.join(sorted(unknown)))


def validate_component(material):
    ontology = load()
    for field, known in [('implements', ontology['entities']['capabilities']),
                         ('modifies_region', ontology['entities']['regions']),
                         ('quantities', ontology['quantities'])]:
        ids = material.get(field, [])
        if not isinstance(ids, list) or any(not isinstance(v, str) or v not in known for v in ids):
            raise ValueError('Unknown ontology ids in component ' + field)
    return material
