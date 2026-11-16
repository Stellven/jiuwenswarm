"""Host gate for accepting a Strata repeatability reference, never a speedup."""
import hashlib
import json
from pathlib import Path

from .contract import load


def validate(store, task_id):
    task=store.get_task(task_id)
    constraints=task.get('constraints',{})
    if isinstance(constraints, dict) and constraints.get('fixed_placement_screens'):
        raise ValueError('Fixed-placement screens are diagnostic only; acceptance and promotion prohibited')
    if isinstance(constraints, dict) and constraints.get('fixed_placement_final_slot'):
        raise ValueError('Fixed-placement A/A is diagnostic only; acceptance and promotion prohibited')
    if isinstance(constraints, dict) and constraints.get('nonpromoting_diagnostics'):
        raise ValueError('Non-promoting diagnostic campaigns cannot accept or promote candidates')
    if not isinstance(constraints,dict) or constraints.get('diagnostic_only'):
        return
    if constraints.get('factory_loop', {}).get('comparison_templates'):
        from .construction_comparison import validate_acceptance
        return validate_acceptance(store,task_id)
    if constraints.get('factory_loop', {}).get('experiment_authority') or constraints.get('runtime_execution_binding'):
        raise ValueError('Authored diagnostic evidence cannot authorize engine acceptance')
    # Legacy acceptance rules remain in their existing contract path.
    target=task.get('target')
    if (target.get('profile') if isinstance(target,dict) else target) != 'spark-gb10':
        return
    contract=load(task['contract_id'])
    if contract.get('adapter') == 'strata-benchmark-v3':
        return validate_broad_campaign(store, task_id)
    if contract.get('adapter') == 'strata-prefill-scoped-v1':
        return validate_scoped_prefill(store, task_id, contract)
    if contract.get('adapter') in {'strata-benchmark-v1','strata-benchmark-v2'}:
        records=store._store.dump(task_id) if hasattr(store,'_store') else store.dump(task_id)
        if contract.get('stage')!='main' or not any(r['kind']=='lab_result'
            and r['values'].get('verdict')=='accept'
            and r['values'].get('verification',{}).get('raw_files_verified') is True
            and r['values'].get('verification',{}).get('complete_cells')==8
            for r in records['observations']):
            raise ValueError('Benchmark acceptance requires a complete verified main comparison passing both gates')
        return
    if contract.get('adapter')!='strata-v1':return
    required=constraints.get('required_successful_cells',3)
    if type(required) is not int or required<1:raise ValueError('Invalid required_successful_cells')
    records=store._store.dump(task_id) if hasattr(store,'_store') else store.dump(task_id)
    cells=[r['values'] for r in records['observations'] if r['kind']=='lab_result'
        and r['values'].get('execution_outcome')=='ok' and r['values'].get('evidence_completeness')=='complete'
        and r['values'].get('verification',{}).get('boundary_verified') is True
        and r['values'].get('verification',{}).get('replay_verified') is True]
    if len(cells)<required:
        raise ValueError(f'Strata reference acceptance requires {required} complete verified cells; found {len(cells)}')
    groups={c.get('comparison_group') for c in cells}
    outputs=[r.get('canonical_sha256') for c in cells for r in c.get('requests',[])]
    if None in groups or len(groups)!=1 or not outputs or None in outputs or len(set(outputs))!=1:
        raise ValueError('Strata reference outputs/configurations differ; report inconclusive instead of accepting')


def validate_scoped_prefill(store, task_id, contract):
    """Accept only the declared subsystem claim, using ledger and host revalidation."""
    from .prefill_workbench import Workbench
    from .jobs import Jobs
    host = getattr(store, '_store', store)
    task = store.get_task(task_id)
    policy = task.get('constraints', {}).get('factory_loop')
    if contract.get('stage') != 'confirm' or not isinstance(policy, dict):
        raise ValueError('Scoped acceptance requires an operator-admitted confirm loop')
    exists = host._db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='factory_loop_cycles'").fetchone()
    if not exists:
        raise ValueError('Scoped acceptance requires a collected ledger-bound confirm attempt')
    templates = {item['id']: item for item in policy['templates']}
    for row in host._db.execute('SELECT record FROM factory_loop_cycles WHERE task_id=?', (task_id,)):
        cycle = json.loads(row['record'])
        if cycle['state'] != 'collected' or cycle['contract'] != contract:
            continue
        template = templates.get(cycle['request']['template_id'])
        if not template or cycle['template_sha256'] != template['sha256']:
            raise ValueError('Scoped confirm differs from admitted template')
        raw = Path(template['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != template['sha256'] or json.loads(raw) != contract:
            raise ValueError('Scoped confirm template identity changed')
        attempt = Jobs(host)._get(cycle['attempt_id'])
        child = host.get_task(cycle['child_task_id'])
        if (attempt['task_id'] != cycle['child_task_id'] or attempt['kind'] != 'lab'
                or attempt['request'].get('adapter') != 'strata-prefill-scoped-v1'
                or attempt['request'].get('contract') != contract
                or attempt['request'].get('contract_sha256') != cycle['contract_sha256']
                or child['constraints'].get('factory_loop_parent') != task_id):
            raise ValueError('Scoped confirm attempt ownership or contract differs')
        # Always ask the finite host result importer to verify raw artifacts. An
        # agent-authored summary or a cached loop report cannot authorize accept.
        result = Workbench(host).result(cycle['child_task_id'], cycle['attempt_id'])
        report = result.get('analysis') or {}
        verification = report.get('verification', {})
        if (result.get('state') == 'succeeded' and report.get('verdict') == 'scoped_improvement'
                and report.get('scope') == 'prefill_microbenchmark' and report.get('stage') == 'confirm'
                and report.get('execution_complete') is True
                and report.get('promotion_authorized') is False
                and report.get('full_quality_claim') is False
                and verification.get('raw_files_verified') is True
                and verification.get('independent_native_parse') is True
                and verification.get('complete_cells') == 4
                and all(report.get('gates', {}).get(key) is True for key in (
                    'single_token_repeatability_and_cross_arm_agreement', 'minimum_5pct_signal',
                    'all_candidate_cell_medians_below_all_baseline'))):
            return
    raise ValueError('Scoped acceptance requires a complete host-verified confirm improvement; no end-to-end promotion')


def validate_broad_campaign(store, task_id):
    """Require independently re-read A/A and confirmation, bound to admitted children."""
    from .benchmark import analyze_files, validate_contract
    from .jobs import Jobs
    host = getattr(store, '_store', store)
    policy = store.get_task(task_id).get('constraints', {}).get('factory_loop')
    if not isinstance(policy, dict):
        raise ValueError('Broad acceptance requires an admitted campaign')
    exists = host._db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='factory_loop_cycles'").fetchone()
    if not exists:
        raise ValueError('Broad acceptance requires ledger-bound A/A and confirm')
    templates = {item['id']: item for item in policy['templates']}
    aa_contracts, confirms = [], []
    for row in host._db.execute('SELECT record FROM factory_loop_cycles WHERE task_id=?', (task_id,)):
        cycle = json.loads(row['record'])
        contract = cycle.get('contract', {})
        if (cycle.get('state') != 'collected' or contract.get('adapter') != 'strata-benchmark-v3'
                or contract.get('campaign_stage') not in {'aa', 'confirm'}):
            continue
        validate_contract(contract)
        template = templates.get(cycle['request']['template_id'])
        if not template or cycle['template_sha256'] != template['sha256']:
            raise ValueError('Broad template differs from admission')
        raw = Path(template['path']).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != template['sha256'] or json.loads(raw) != contract:
            raise ValueError('Broad contract identity changed')
        attempt = Jobs(host)._get(cycle['attempt_id'])
        child = host.get_task(cycle['child_task_id'])
        child_raw = (json.dumps(contract, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
        child_digest = hashlib.sha256(child_raw).hexdigest()
        if cycle['contract_sha256'] != child_digest:
            raise ValueError('Broad child contract digest differs')
        if (attempt['task_id'] != child['task_id'] or attempt['kind'] != 'lab'
                or child['constraints'].get('factory_loop_parent') != task_id
                or attempt['request'].get('contract') != contract
                or attempt['request'].get('contract_sha256') != child_digest):
            raise ValueError('Broad attempt ownership or identity changed')
        if attempt['state'] != 'succeeded':
            continue
        root = host.home/'benchmark-spool'/attempt['attempt_id']
        config = json.loads((root/'config.json').read_text())
        if config.get('task_id') != child['task_id'] or config.get('attempt_id') != attempt['attempt_id']:
            raise ValueError('Broad raw evidence belongs to another attempt')
        report = analyze_files(contract, root)
        verified = report.get('verification', {})
        if (verified.get('raw_files_verified') is not True
                or verified.get('independent_native_parse') is not True
                or verified.get('complete_cells') != len(contract['order'])):
            raise ValueError('Broad raw evidence incomplete')
        if (contract['campaign_stage'] == 'aa' and report.get('verdict') == 'aa_valid'
                and report.get('gates', {}).get('aa_timing_stable') is True):
            aa_contracts.append(contract)
        if (contract['campaign_stage'] == 'confirm' and report.get('verdict') == 'accept'
                and report.get('performance_acceptance_evaluated') is True
                and report.get('promotion_authorized') is False
                and report.get('quality', {}).get('case_count') == 64):
            confirms.append(contract)
    for confirm in confirms:
        if any(all(aa[key] == confirm[key] for key in ('image', 'assets', 'dataset_sha256', 'workload'))
               and aa['arms']['A'] == confirm['arms']['A'] for aa in aa_contracts):
            return
    raise ValueError('Broad acceptance requires matching host-verified A/A and full-quality confirmation')
