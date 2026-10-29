"""Explicit opt-in static selection without modifying historical planner bytes."""
from __future__ import annotations

import hashlib
import json
from importlib.resources import files

from .contracts import ResearchError, validate


def capture_static_template(store, library, *, expected_ref=None, screening_version='m1-4', delivery_version='m1-5'):
    from .releases import implicit_release, require_release
    require_release('screening', screening_version, 'static_template_pin')
    require_release('delivery', delivery_version, 'static_template_pin')
    if screening_version == implicit_release('screening') and delivery_version == implicit_release('delivery'):
        from .planning import capture_static_template as original_capture
        return original_capture(store, library, expected_ref=expected_ref)

    root = files('jiuwenswarm.research_assets')
    catalog = json.loads(root.joinpath('catalog.json').read_text('utf-8'))
    entry = catalog.get('static_template')
    if not isinstance(entry, dict) or entry.get('interface_revision') != 'M1-IF-002@r2':
        raise ResearchError('static_template_pin', 'No current authored static release is installed')
    historical = root.joinpath(entry['path']).read_bytes()
    if hashlib.sha256(historical).hexdigest() != entry['sha256']:
        raise ResearchError('static_template_pin', 'Installed static template differs from its frozen release pin')
    validate('static-template', json.loads(historical))

    from .local_profile import _static_template
    ref = _static_template(store, screening_version=screening_version, delivery_version=delivery_version)
    value = json.loads(store.read_blob(ref))
    validate('static-template', value)
    snapshot = store.read_record(library.snapshot(), contract_id='library-snapshot')
    entries = {(e['cc_name'], e['cc_version'], e['declaration_sha256']): e for e in snapshot['entries']}
    for node in value['nodes']:
        pin = node['cc']
        chosen = entries.get(tuple(pin[k] for k in ('cc_name', 'cc_version', 'declaration_sha256')))
        if chosen is None or any(node['limits'][k] > chosen['max_limits'][k] for k in ('time_s', 'model_calls', 'memory_mb')):
            raise ResearchError('static_template_pin', 'Authored static node lacks its exact eligible aggregate library allowance')
    required = {'time_s': sum(n['limits']['time_s'] for n in value['nodes']),
                'model_calls': sum(n['limits']['model_calls'] for n in value['nodes']),
                'memory_mb': max(n['limits']['memory_mb'] for n in value['nodes'])}
    if any(required[k] > value['limits'][k] for k in required):
        raise ResearchError('static_template_pin', 'Authored aggregate exceeds unchanged overall static limits')
    if expected_ref is not None and expected_ref != ref:
        raise ResearchError('static_template_pin', 'Approved configuration names another static template; explicitly capture the current release', {'current_static_template_ref': ref})
    return ref
