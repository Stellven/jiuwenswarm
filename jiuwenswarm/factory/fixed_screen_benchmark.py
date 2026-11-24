"""Two nonpromoting fixed-placement screens after independently verified fixed A/A."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import re

ADAPTER='strata-benchmark-v5'
ORIGIN='spark-broad-throughput-004'
AA_TASK='spark-fixed-placement-aa-001'
CHANGES={'ahead1','cpu6'}


def shaped(c):
    from .fixed_placement_benchmark import shaped as fixed_shape
    out=fixed_shape(c)
    out['execution_sha256'].pop('fixed_screen_benchmark.py',None)
    return out


def validate_contract(c):
    from .broad_benchmark import validate_contract as validate_broad
    from .fixed_placement_benchmark import BUDGET,validate_build
    if c.get('adapter')!=ADAPTER or c.get('version')!=5 or c.get('campaign_stage')!='screen':
        raise ValueError('Wrong fixed-screen adapter/stage')
    if c.get('configuration_change') not in CHANGES or c.get('promotion_authorized') is not False:
        raise ValueError('Only nonpromoting ahead1/cpu6 fixed screens admitted')
    if c.get('expected_placement_layers')!=40 or c.get('expected_experts_per_layer')!=384:
        raise ValueError('Frozen full-model placement shape required')
    if any(arm['environment'].get('DS4_EXPERT_BUDGET_BYTES')!=BUDGET for arm in c['arms'].values()):
        raise ValueError('Exact 76GB budget required in both fixed screen arms')
    base=shaped(c);validate_broad(base)
    if set(c['execution_sha256'])!=set(base['execution_sha256'])|{'fixed_placement_benchmark.py','fixed_screen_benchmark.py','engine_adapters.py'}:
        raise ValueError('Complete v5 execution source pins required')
    if any(not re.fullmatch('[a-f0-9]{64}',v) for v in c['execution_sha256'].values()):
        raise ValueError('Invalid v5 execution source identity')
    validate_build(c)
    return c


def engagement(c,arm,parsed,stderr):
    from .fixed_placement_benchmark import engagement as fixed_engagement
    return fixed_engagement(c,arm,parsed,stderr)


def analyze(c,d,cells,decode):
    from .broad_benchmark import analyze as broad_analyze
    validate_contract(c)
    report=broad_analyze(shaped(c),d,cells,decode)
    identities=[cell[phase].get('fixed_placement_identity') for cell in cells for phase in ('quality','speed')]
    equal=len(identities)==4 and identities[0] is not None and all(value==identities[0] for value in identities)
    tokens=report.get('raw_token_equal') is True
    positive=report['verdict']=='screen_candidate' and equal and tokens
    report['gates'].update(complete_fixed_placement_equal_across_all_processes=equal,exact_cross_arm_tokens_and_finish=tokens)
    report.update(adapter=ADAPTER,scope='fixed_screen_diagnostic',promotion_authorized=False,
        performance_acceptance_evaluated=False,verdict='fixed_screen_diagnostic_positive' if positive else 'fixed_screen_diagnostic_inconclusive',
        fixed_placement=dict(processes=4,complete_identity=identities,all_equal=equal))
    report['limitations'].append('One paired screen under fixed placement is diagnostic only. Exact token/finish and placement equality are required for a diagnostic positive. No accepted improvement, confidence or promotion claim.')
    return report


def admit_fixed_screens(loop,c,*,reserving):
    """Re-read actual baseline A/A evidence, then reserve under the original cap."""
    mode=loop.task.get('constraints',{}).get('fixed_placement_screens')
    keys={'origin_task_id','baseline_task_id','baseline_cycle_id','baseline_attempt_id','baseline_contract_sha256','baseline_manifest_sha256','aggregate_max_experiments'}
    if (not isinstance(mode,dict) or set(mode)!=keys or mode['origin_task_id']!=ORIGIN
            or mode['baseline_task_id']!=AA_TASK or mode['aggregate_max_experiments']!=10
            or loop.policy['max_cycles']!=2 or loop.policy['max_experiments']!=2):
        raise ValueError('Explicit two-experiment fixed screen policy required')
    validate_contract(c)
    rows=loop.store._db.execute('SELECT record FROM factory_loop_cycles WHERE task_id=?',(AA_TASK,)).fetchall()
    matches=[json.loads(row['record']) for row in rows if json.loads(row['record']).get('cycle_id')==mode['baseline_cycle_id']]
    if len(matches)!=1:raise ValueError('Baseline fixed A/A cycle missing or ambiguous')
    baseline=matches[0]
    if (baseline['state']!='collected' or baseline['attempt_id']!=mode['baseline_attempt_id']
            or baseline['contract_sha256']!=mode['baseline_contract_sha256']
            or hashlib.sha256(Path(baseline['contract_path']).read_bytes()).hexdigest()!=mode['baseline_contract_sha256']):
        raise ValueError('Baseline fixed A/A ledger/contract identity differs')
    attempt=loop.store.read(baseline['child_task_id'],baseline['attempt_id'])
    if (attempt['task_id']!=baseline['child_task_id'] or attempt['kind']!='lab' or attempt['state']!='succeeded'
            or attempt['request'].get('contract_sha256')!=mode['baseline_contract_sha256']
            or attempt['request'].get('contract')!=baseline['contract']):
        raise ValueError('Baseline fixed A/A attempt is not verified successful execution')
    root=loop.store.home/'benchmark-spool'/baseline['attempt_id']
    if hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()!=mode['baseline_manifest_sha256']:
        raise ValueError('Baseline fixed A/A raw manifest changed')
    from .benchmark import analyze_files
    report=analyze_files(baseline['contract'],root)
    if (report.get('verdict')!='fixed_placement_aa_observed_repeatable'
            or report.get('raw_token_equal') is not True
            or not report.get('gates',{}).get('complete_fixed_placement_equal_across_all_processes')
            or report.get('verification',{}).get('raw_files_verified') is not True
            or report.get('verification',{}).get('independent_native_parse') is not True
            or report.get('verification',{}).get('complete_cells')!=2):
        raise ValueError('Independent fixed A/A repeatability/placement qualification failed')
    aa=baseline['contract']
    if c['arms']['A']!=aa['arms']['A']:
        raise ValueError('Fixed screen baseline profile differs from qualified A/A')
    for key in ('image','candidate_build','assets','workload','dataset_path','dataset_sha256','limits','gates',
                'quality_case_indices','speed_case_indices','runtime_bounds','primary_metric','expected_placement_layers','expected_experts_per_layer'):
        if c.get(key)!=aa.get(key):raise ValueError('Fixed screen qualified baseline differs: '+key)
    used=0
    for row in loop.store._db.execute('SELECT task_id,constraints FROM tasks'):
        constraints=json.loads(row['constraints'])
        linked=(row['task_id']==ORIGIN or any(constraints.get(key,{}).get('origin_task_id')==ORIGIN
            for key in ('nonpromoting_diagnostics','fixed_placement_final_slot','fixed_placement_screens')))
        if not linked:continue
        records=loop.store._db.execute('SELECT record FROM factory_loop_cycles WHERE task_id=?',(row['task_id'],)).fetchall()
        used+=len(records)
        if reserving and constraints.get('fixed_placement_screens'):
            if any(json.loads(record['record']).get('contract',{}).get('configuration_change')==c['configuration_change'] for record in records):
                raise ValueError('Fixed screen settings may not be repeated')
    if used+int(reserving)>10:raise ValueError('Ten-experiment original aggregate cap exhausted')
    return dict(aggregate_used_before_reservation=used,aggregate_cap=10,baseline_attempt_id=baseline['attempt_id'])
