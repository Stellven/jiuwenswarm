"""Account-scoped projections of the installed workflow and its actual releases.

These views cannot install assets, dispatch work, or interpret a scientific
verdict. Private verifier instructions, model prompts and credentials stay out.
"""
from __future__ import annotations

import json
from importlib.resources import files

from .contracts import ResearchError


STAGES = ('intent', 'requirements', 'planner', 'search', 'screening', 'hypothesis',
          'builder', 'benchmark', 'evaluation', 'delivery', 'verifier')


def _declarations(store, core):
    root = files('jiuwenswarm.research_assets')
    catalog = json.loads(root.joinpath('catalog.json').read_text('utf-8'))
    result = {stage: json.loads(root.joinpath(entry['declaration_path']).read_text('utf-8'))
              for stage, entry in catalog['capsules'].items()}
    from .capsules.assets import source_metadata, STAGE_VERSIONS
    for stage, entry in source_metadata().items():
        result[stage] = dict(entry['declaration'], identity=dict(entry['declaration']['identity'], version_label=STAGE_VERSIONS[stage]))
    # Show the exact prepared/installed declarations, including a new authored
    # local release. Display must not silently substitute an older version.
    for stage, asset in getattr(core, 'installed', {}).items():
        if stage in result:
            result[stage] = store.read_record(asset['declaration_ref'], contract_id='capsule-declaration')
    return result


async def runtime_snapshot(channel, principal):
    principal.require('status')
    service = channel.research_service
    attachment = channel.research_composition
    core = attachment.composition
    declarations = _declarations(service.store, core)
    capsules = []
    for stage in STAGES:
        declaration = declarations[stage]
        identity = declaration['identity']
        row = {'stage': stage, 'name': identity['name'], 'version': identity['version_label'],
               'standing': 'not_installed', 'eligible': False, 'checks': [], 'criteria': []}
        if core is not None:
            try:
                installed = core.library.get(row['name'], row['version'])
                row['standing'] = installed['standing']
                association = core.library.eligible_association(installed['declaration_ref'])
                admission = service.store.read_record(installed['admission_ref'], contract_id='library-admission')
                row['eligible'] = admission['status'] == 'admitted' and installed['standing'] == 'active'
                bundle = service.store.read_record(association['bundle_ref'], contract_id='check-bundle')
                profile = service.store.read_record(association['profile_ref'], contract_id='checking-profile')
                row['checks'] = [item['check_id'] for item in bundle['checks']]
                row['criteria'] = [item['criterion_id'] for item in profile['criteria']]
            except ResearchError:
                # Membership and independently measured guard eligibility differ.
                # A bundled declaration alone is never an installed capability.
                pass
        capsules.append(row)
    diagnostics = [{'code': item['code'], 'detail': item['detail']} for item in attachment.diagnostics]
    readiness = None
    try:
        readiness = await service.readiness(principal)
    except ResearchError as exc:
        diagnostics.append({'code': exc.code, 'detail': 'Protected runtime readiness is unavailable.'})
    prerequisites = list(readiness['prerequisites']) if readiness else []
    # Missing catalog pins must not hide independently observable runtime facts.
    # These are status observations, never substitutes for complete readiness.
    ports = attachment.runtime_ports
    if readiness is None and ports is not None and 'readiness' in principal.operations:
        try:
            state = await ports.status_client.call('subscription_status', {}, timeout_s=10)
            for name, ok in [('model', state.get('state') == 'ready'), ('builder', state.get('builder_qualified') is True)]:
                prerequisites.append({'name': name, 'status': 'ready' if ok else 'unavailable',
                    'reason': 'Observed by the native runtime owner.' if ok else 'The native runtime owner reports this prerequisite unavailable.'})
        except Exception:
            prerequisites.append({'name': 'model', 'status': 'unavailable', 'reason': 'Native runtime status could not be observed.'})
        try:
            state = await ports.executor.prerequisites()
            prerequisites.append({'name': 'isolation', 'status': 'ready' if state.get('ready') is True else 'unavailable',
                'reason': 'Restricted executor prerequisites passed.' if state.get('ready') is True else 'Restricted executor prerequisites are incomplete.'})
        except Exception:
            prerequisites.append({'name': 'isolation', 'status': 'unavailable', 'reason': 'Restricted executor status could not be observed.'})
    defaults = service.client_defaults(principal)
    # A captured operator configuration can exist before catalog installation.
    captured = getattr(core, 'runner', None)
    configuration = getattr(channel, 'research_refusal_reason', None) is None and captured is not None
    return {'schema': 'ai4r-workflow-runtime:1', 'configured': configuration,
            'ready': readiness is not None and readiness['ready'] is True,
            'plan_source': defaults.get('plan_source') or getattr(service, 'captured_plan_source', None), 'capsules': capsules,
            'diagnostics': diagnostics, 'prerequisites': prerequisites, 'defaults': defaults,
            'example_available': getattr(service, 'local_example_ref', None) is not None}


def workflow_example(service, principal):
    """An operator-captured tutorial is source material, never run evidence."""
    from .contracts import validate
    principal.require('status')
    ref = getattr(service, 'local_example_ref', None)
    if ref is None:
        raise ResearchError('unavailable', 'This deployment has no captured research example')
    example = service.store.read_record(ref)
    if example.get('schema') != 'ai4r-local-research-example:1':
        raise ResearchError('unavailable', 'Captured research example is invalid')
    validate('Ref', example['guide_ref'])
    return {'schema': example['schema'], 'title': example['title'], 'description': example['description'],
            'filename': example['filename'], 'request': example['request'], 'guide_ref': example['guide_ref'],
            'guide': service.store.read_blob(example['guide_ref']).decode('utf-8')}


def run_timeline(service, principal, run_id):
    principal.require('status')
    run = service.store.get_run(run_id, account_id=principal.account_id)
    principal.require('status', run['workspace_id'])
    events = []
    records = list(service.store.iter_records(run_id=run_id))
    # Public ModelCall records carry an invocation ID, not a run ID. Resolve
    # only exact call Refs captured by observations of this owned run.
    seen_calls = {entry['ref']['id'] for entry in records if entry['kind'] == 'model-call'}
    for entry in list(records):
        if entry['kind'] != 'invocation-observation':
            continue
        for ref in entry['record']['trace_refs']:
            if ref['id'] in seen_calls:
                continue
            try:
                kind = service.store.record_kind(ref)
            except ResearchError as exc:
                if exc.code != 'evidence_unavailable':
                    raise
                continue  # Raw native trace blobs have no record kind.
            if kind == 'model-call':
                call = service.store.read_record(ref, contract_id='model-call')
                records.append({'kind': 'model-call', 'ref': ref, 'record': call})
                seen_calls.add(ref['id'])
    routes = {entry['record']['route_id']: entry for entry in records if entry['kind'] == 'route-record'}
    starts = {(entry['record']['call_id'], entry['record']['invocation_id'], entry['record']['execution_id']): entry['record']
              for entry in records if entry['kind'] == 'model-call-start'}
    for envelope in records:
        kind, record = envelope['kind'], envelope['record']
        if kind == 'invocation-observation':
            events.append({'kind': 'invocation', 'ref': envelope['ref'], 'node_id': record['node_id'],
                           'subnode_id': record.get('subnode_id'), 'outcome': record['outcome'],
                           'reason': record.get('failure_reason_code'), 'accepted': False})
        elif kind == 'model-call':
            # ModelCall deliberately has no node/route fields. Join the exact
            # host-captured start and RouteRecord, rather than inventing them.
            start = starts.get((record['id'], record['invocation_id'], record['execution_id']))
            routed = routes.get(start['route_id']) if start else None
            if routed is None or routed['ref'] != start['route_ref']:
                raise ResearchError('integrity_fault', 'Model call has no exact captured route')
            route = routed['record']
            identity = record.get('identity', {})
            events.append({'kind': 'model_call', 'ref': envelope['ref'], 'node_id': route['node_id'],
                'subnode_id': route.get('subnode_id'), 'outcome': record['outcome'],
                'function': record.get('call_function'), 'requested_model': identity.get('requested'),
                'effective_model': identity.get('effective'), 'route_source': route.get('decision_source'),
                'route_id': route.get('route_id'), 'reason': record.get('provider_error_code')})
        elif kind == 'gate-decision':
            checks = []
            ref = record.get('deterministic_result_ref')
            if ref is not None:
                checked = service.store.read_record(ref, contract_id='deterministic-check-result')
                checks = [{key: item.get(key) for key in ('check_id', 'outcome', 'reason')}
                          for item in checked['results']]
            findings = []
            ref = record.get('assessment_ref')
            if ref is not None:
                assessed = service.store.read_record(ref, contract_id='verifier-assessment')
                findings = [{key: item.get(key) for key in ('criterion_id', 'outcome', 'reason')}
                            for item in assessed['findings']]
            events.append({'kind': 'gate', 'ref': envelope['ref'], 'node_id': record['node_id'],
                           'subnode_id': record.get('subnode_id'), 'scope': record['scope_kind'],
                           'action': record['action'], 'verdict': record.get('verdict'),
                           'checks': checks, 'findings': findings,
                           'accepted_refs': record['accepted_refs'] if record['action'] == 'advance' else []})
    return {'schema': 'ai4r-workflow-timeline:1', 'run_id': run_id, 'revision': run['revision'], 'events': events}


async def run_result(service, principal, run_id):
    """Return only an accepted Delivery report through existing disclosure rules."""
    principal.require('export')
    store = service.store
    run = store.get_run(run_id, account_id=principal.account_id)
    principal.require('export', run['workspace_id'])
    result = {'schema': 'ai4r-workflow-result:1', 'run_id': run_id, 'status': run['state'], 'report': None}
    if run['state'] != 'completed':
        return result
    reports = []
    for node in store.node_states(run_id):
        for ref in store.accepted_outputs(run_id, node['node_id']).values():
            try:
                manifest = store.read_record(ref, contract_id='delivery-manifest')
            except (ResearchError, ValueError, UnicodeError):
                continue
            # The report is both released by its node and named by its accepted
            # manifest. Candidate output and a plausible filename never suffice.
            accepted = store.accepted_outputs(run_id, node['node_id'])
            if manifest['report_ref'] not in accepted.values():
                raise ResearchError('integrity_fault', 'Delivery report lacks its exact node release')
            for item in manifest['files']:
                if item['role'] == 'report' and item['artifact_ref'] == manifest['report_ref'] and item['audience'] == 'researcher':
                    reports.append(item)
    if len(reports) != 1:
        raise ResearchError('unavailable', 'Completed workflow has no unique accepted researcher report')
    exported, contents = await service.artifact_bytes(principal, run_id, audience='researcher')
    matches = [item for item in exported['files'] if item['path'] == reports[0]['path'] and item['media_type'] == 'text/markdown']
    if len(matches) != 1:
        raise ResearchError('unavailable', 'Accepted report is unavailable under the current disclosure policy')
    view = matches[0]
    result['report'] = {'content': contents[view['path']].decode('utf-8'), 'path': view['path'],
                        'accepted_ref': reports[0]['artifact_ref'], 'display_ref': view['artifact_ref'],
                        'redacted': view['artifact_ref'] != reports[0]['artifact_ref']}
    return result
