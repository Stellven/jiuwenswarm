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


def _declarations():
    root = files('jiuwenswarm.research_assets')
    catalog = json.loads(root.joinpath('catalog.json').read_text('utf-8'))
    result = {stage: json.loads(root.joinpath(entry['declaration_path']).read_text('utf-8'))
              for stage, entry in catalog['capsules'].items()}
    from .capsules.assets import source_metadata
    for stage, entry in source_metadata().items():
        result[stage] = dict(entry['declaration'], identity=dict(entry['declaration']['identity'], version_label='m1-1'))
    return result


async def runtime_snapshot(channel, principal):
    principal.require('status')
    service = channel.research_service
    attachment = channel.research_composition
    core = attachment.composition
    declarations = _declarations()
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
    defaults = service.client_defaults(principal)
    return {'schema': 'ai4r-workflow-runtime:1', 'configured': defaults['configuration_ref'] is not None,
            'ready': readiness is not None and readiness['ready'] is True,
            'plan_source': defaults.get('plan_source'), 'capsules': capsules,
            'diagnostics': diagnostics, 'prerequisites': readiness['prerequisites'] if readiness else []}


def run_timeline(service, principal, run_id):
    principal.require('status')
    run = service.store.get_run(run_id, account_id=principal.account_id)
    principal.require('status', run['workspace_id'])
    events = []
    for envelope in service.store.iter_records(run_id=run_id):
        kind, record = envelope['kind'], envelope['record']
        if kind == 'invocation-observation':
            events.append({'kind': 'invocation', 'ref': envelope['ref'], 'node_id': record['node_id'],
                           'subnode_id': record.get('subnode_id'), 'outcome': record['outcome'],
                           'reason': record.get('failure_reason_code'), 'accepted': False})
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
