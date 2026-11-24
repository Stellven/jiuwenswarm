"""Small, local vocabulary for engine evidence and component selection."""
from functools import lru_cache
from pathlib import Path

import yaml

PATH = Path(__file__).parent / 'ccs/expert_streaming/ONTOLOGY.yaml'


@lru_cache(maxsize=1)
def load():
    return _validate_ontology(yaml.safe_load(PATH.read_text()))


@lru_cache(maxsize=32)
def _read_yaml(path):
    return yaml.safe_load(path.read_text())


def _validate_ontology(ontology):
    quantities = ontology['quantities']
    for spec in quantities.values():
        if (spec['phase'] not in {'prompt', 'decode', 'run'}
                or spec['region'] not in ontology['entities']['regions']
                or set(spec['distinct_from']) - quantities.keys()):
            raise ValueError('Invalid engine ontology quantity')
    for slice_ in ontology.get('slices', {}).values():
        if (not slice_.get('purpose')
                or set(slice_['regions']) - ontology['entities']['regions'].keys()
                or set(slice_['quantities']) - quantities.keys()):
            raise ValueError('Invalid engine ontology slice')
    return ontology


def validate_quantities(ids):
    if not isinstance(ids, list) or any(not isinstance(q, str) for q in ids):
        raise ValueError('Quantity ids must be a list of strings')
    unknown = set(ids) - load()['quantities'].keys()
    if unknown:
        raise ValueError('Unknown ontology quantities: ' + ', '.join(sorted(unknown)))


def validate_component(material, *, ontology_path=None):
    ontology = load() if ontology_path is None else _validate_ontology(_read_yaml(ontology_path))
    if ontology_path is not None and not ontology.get('slices'):
        raise ValueError('Builder specification requires a capsule ontology slice')
    for field, known in [('implements', ontology['entities'].get('capabilities', [])),
                         ('modifies_region', ontology['entities']['regions']),
                         ('quantities', ontology['quantities'])]:
        ids = material.get(field, [])
        if not isinstance(ids, list) or any(not isinstance(v, str) or v not in known for v in ids):
            raise ValueError('Unknown ontology ids in component ' + field)
    return material


def validate_slice(slice_id, component_cc=None):
    """Validate a domain target; it grants no execution or acceptance authority."""
    if not isinstance(slice_id, str):
        raise ValueError('Unknown engine ontology slice')
    # Older task records can omit component_cc. Preserve their original vocabulary.
    component_cc = component_cc or 'engine.expert_streaming'
    if component_cc == 'engine.expert_streaming' and slice_id in load().get('slices', {}):
        return load()['slices'][slice_id]

    sources = []
    for path in sorted(PATH.parents[1].glob('*/ONTOLOGY.yaml')):
        manifest = path.with_name('cc.yaml')
        if manifest.is_file():
            sources.append((_read_yaml(manifest)['id'], path))

    for preferred in (True, False):
        matches = [(cc, path) for cc, path in sources if (cc == component_cc) == preferred
                   and slice_id in _read_yaml(path).get('slices', {})]
        if len(matches) > 1:
            candidates = ', '.join(f'{cc} ({path.parent.name})' for cc, path in matches)
            raise ValueError(f'Ambiguous engine ontology slice {slice_id!r}: {candidates}')
        if matches:
            return _validate_ontology(_read_yaml(matches[0][1]))['slices'][slice_id]
    raise ValueError('Unknown engine ontology slice')
