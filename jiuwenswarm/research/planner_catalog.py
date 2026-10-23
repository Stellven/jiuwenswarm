"""Explicit immutable declaration context; never a worker's live Library access."""
from .contracts import ResearchError, validate
from .state import json_bytes

SCHEMA = 'urn:ai4r:planner-catalog:1.0.0'
MAX_BYTES = 2 * 1024 * 1024


def verify_catalog(value, snapshot, snapshot_ref):
    validate(SCHEMA, value)
    if value['library_snapshot_ref'] != snapshot_ref or len(json_bytes(value)) > MAX_BYTES:
        raise ResearchError('planner_catalog', 'Catalog differs from the frozen snapshot or exceeds its context ceiling')
    expected = {(e['cc_name'], e['cc_version'], e['declaration_sha256']): e
                for e in snapshot['entries'] if e['selectable_by_planner']}
    seen = set()
    for item in value['capsules']:
        pin, declaration = item['cc'], item['declaration']
        key = tuple(pin[k] for k in ('cc_name', 'cc_version', 'declaration_sha256'))
        entry = expected.get(key)
        if key in seen or entry is None or item['declaration_ref']['sha256'] != pin['declaration_sha256']:
            raise ResearchError('planner_catalog', 'Catalog has a duplicate, unavailable or mismatched capsule')
        validate('capsule-declaration', declaration)
        if (declaration['identity']['name'], declaration['identity']['version_label']) != key[:2]:
            raise ResearchError('planner_catalog', 'Declaration identity differs from its exact pin')
        for direction, field in (('inputs', 'input_ports'), ('outputs', 'output_ports')):
            ports = [{k: p[k] for k in ('name', 'artifact_type', 'schema_ref', 'required')}
                     for p in declaration['ports'][direction]]
            if ports != entry[field]:
                raise ResearchError('planner_catalog', 'Declared ports differ from the frozen snapshot')
        seen.add(key)
    if seen != set(expected):
        raise ResearchError('planner_catalog', 'Catalog omits a selectable admitted capsule')


def capture_catalog(store, library, snapshot_ref):
    snapshot = store.read_record(snapshot_ref, contract_id='library-snapshot')
    items = []
    for entry in snapshot['entries']:
        if not entry['selectable_by_planner']:
            continue
        row = library.get(entry['cc_name'], entry['cc_version'])
        ref = row['declaration_ref']
        if ref['sha256'] != entry['declaration_sha256']:
            raise ResearchError('planner_catalog', 'Live declaration differs from frozen admitted selection')
        items.append({'cc': {k: entry[k] for k in ('cc_name', 'cc_version', 'declaration_sha256')},
                      'declaration_ref': ref, 'declaration': store.read_record(ref, contract_id='capsule-declaration')})
    value = {'schema_version': '1.0.0', 'library_snapshot_ref': snapshot_ref, 'capsules': items}
    verify_catalog(value, snapshot, snapshot_ref)
    return store.put_blob(json_bytes(value), media_type='application/json')


def verify_captured_catalog(store, value, snapshot, snapshot_ref):
    """Host verifies exact source bytes as well as descriptive snapshot agreement."""
    verify_catalog(value, snapshot, snapshot_ref)
    for item in value['capsules']:
        if store.read_record(item['declaration_ref'], contract_id='capsule-declaration') != item['declaration']:
            raise ResearchError('planner_catalog', 'Catalog text differs from the pinned declaration bytes')
