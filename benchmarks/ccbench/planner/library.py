"""Offline release capture. No admission, worker, model, or runtime service runs."""
import sys
sys.dont_write_bytecode = True
import hashlib
import json
import asyncio
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
import roots  # noqa: E402

REPO = roots.code_root()
sys.path.insert(0, str(REPO))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def ref(value, label='offline'):
    return {'id': label, 'sha256': hashlib.sha256(canonical(value).encode()).hexdigest()}


class MemoryAssets:
    """The release factories need only immutable blob capture, never a RunStore."""
    def __init__(self):
        self.blobs = {}

    def put_blob(self, raw, **kwargs):
        digest = hashlib.sha256(raw).hexdigest()
        self.blobs[digest] = raw
        return {'id': 'blob:' + digest, 'sha256': digest}

    def read_blob(self, pin):
        return self.blobs[pin['sha256']]

    def put_record(self, contract_id, value, **kwargs):
        from jiuwenswarm.research.state import json_bytes
        return self.put_blob(json_bytes(value))

    def read_record(self, pin, **kwargs):
        return json.loads(self.read_blob(pin))


@lru_cache(maxsize=1)
def build_library():
    from cclib.harness import product_assets
    from jiuwenswarm.research.capsule_extensions.catalog import candidates
    from jiuwenswarm.research.contracts import validate, contract_schema
    from jiuwenswarm.research.planner_catalog import verify_catalog
    from jiuwenswarm.research.unified_planning import integrated_plan_policy, integrated_planner_instructions
    store = MemoryAssets()
    core, research, paper, evidence = asyncio.run(product_assets(store))
    assets = list(research.values()) + list(paper.values())
    assets += list(evidence['research_assets'].values()) + list(evidence['paper_assets'].values())
    assets += [evidence['compiler_assets']['verifier']]
    assets += [a for a, module in candidates(store).values()]
    assets += list(core.values())
    entries, capsules, checks = [], [], {}
    # Same worker+per-output review formula as LibraryService.snapshot. These
    # are explicit experimental admission assumptions, not live admission claims.
    verifier = store.read_record(core['verifier']['declaration_ref'])
    fixed = {'intent.compiler', 'requirements.compiler', 'research.verifier', 'research.planner',
             'workflow.paper_planner', 'workflow.capability_planner'}
    for asset in assets:
        d = store.read_record(asset['declaration_ref'])
        validate('capsule-declaration', d)
        bundle = store.read_record(asset['bundle_ref'])
        profile = store.read_record(asset['profile_ref'])
        identity, budget = d['identity'], d['budget']['per_call']
        pin = dict(cc_name=identity['name'], cc_version=identity['version_label'], declaration_sha256=asset['declaration_ref']['sha256'])
        count = 0 if identity['name'] == 'research.verifier' else len(d['ports']['outputs'])
        limits = {'time_s': budget['wall_s'] + count * min(verifier['budget']['per_call']['wall_s'], profile['time_s']),
                  'model_calls': (budget['invocations'] if any(i['service_key'] == 'audited_model_bridge' for i in d['needs']['injects']) else 0) + count,
                  'memory_mb': 16384}
        pins = dict(check_bundle_id=bundle['bundle_id'], check_bundle_version=bundle['version'], check_bundle_sha256=asset['bundle_ref']['sha256'],
                    checking_profile_id=profile['profile_id'], checking_profile_version=profile['version'], checking_profile_sha256=asset['profile_ref']['sha256'])
        selectable = identity['name'] not in fixed
        entries.append(dict(**pin, selectable_by_planner=selectable,
            input_ports=[{k: p[k] for k in ('name', 'artifact_type', 'schema_ref', 'required')} for p in d['ports']['inputs']],
            output_ports=[{k: p[k] for k in ('name', 'artifact_type', 'schema_ref', 'required')} for p in d['ports']['outputs']],
            effect_class=d['changes']['effect_class'], network_mode=d['needs']['network']['mode'],
            resource_needs=[dict(resource_key=r['resource_key'], mode=r['mode'], min_quantity=r.get('min_quantity')) for r in d['needs']['resources']],
            max_limits=limits, check_pins=pins))
        if selectable:
            capsules.append(dict(cc=pin, declaration_ref=asset['declaration_ref'], declaration=d))
        checks[identity['name']] = [c['check_id'] for c in bundle['checks']]
    snapshot = dict(schema_version='1.0.0', id='offline-release-library', captured_at='2026-10-26T00:00:00Z', entries=entries)
    validate('library-snapshot', snapshot)
    snapshot_ref = ref(snapshot, 'library_snapshot')
    catalog = dict(schema_version='1.0.0', library_snapshot_ref=snapshot_ref, capsules=capsules)
    verify_catalog(catalog, snapshot, snapshot_ref)
    policy = integrated_plan_policy()
    instructions = (REPO / 'jiuwenswarm/research_assets/planner/planner.txt').read_text('utf-8')
    instructions += '\n' + integrated_planner_instructions(policy)
    schema = contract_schema('plan-proposal')
    instructions += '\nPinned output schema:\n' + json.dumps(schema, ensure_ascii=False)
    return dict(library_snapshot=snapshot, capsule_contracts=catalog, plan_policy=policy,
                instructions=instructions, plan_proposal_schema=schema, checks=checks)


def _listed_ports(ports):
    # A plain skill can state its inputs and outputs in its own text, so arm B sees port names, types and
    # requiredness. Not schema_refs, limits, effects or checks.
    return [{'name': p['name'], 'type': p['artifact_type'], 'required': p['required']} for p in ports]


def undeclared_view(library=None):
    # identity.summary is the release's description/purpose field. Verbatim:
    return [{'name': c['declaration']['identity']['name'], 'description': c['declaration']['identity']['summary'],
             'inputs': _listed_ports(c['declaration']['ports']['inputs']),
             'outputs': _listed_ports(c['declaration']['ports']['outputs'])}
            for c in (library or build_library())['capsule_contracts']['capsules']]


def declared_payload(task, library=None):
    from jiuwenswarm.research.capsules.planner import _protected_host_bindings, _protected_run_inputs
    lib = library or build_library()
    payload = {k: lib[k] for k in ('library_snapshot', 'capsule_contracts', 'plan_policy')}
    payload.update(brief=task['brief'], resource_inventory=task['resource_inventory'])
    for key, source in [('brief_ref', 'brief'), ('library_snapshot_ref', 'library_snapshot'),
                        ('resource_inventory_ref', 'resource_inventory'), ('policy_ref', 'plan_policy')]:
        payload[key] = ref(payload[source], source)
    payload.update(protected_host_bindings=_protected_host_bindings(), protected_run_input_bindings=_protected_run_inputs(task['resource_inventory']))
    return payload


if __name__ == '__main__':
    print(json.dumps(undeclared_view(), indent=2))

