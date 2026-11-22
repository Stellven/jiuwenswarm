"""Separately admitted source comparisons on the existing Strata benchmark worker.

Diagnostic authors provide a build, never a judge. Templates are operator inputs;
all raw evaluation and keep/accept checks remain host-owned.
"""
import copy
import json
import os
from pathlib import Path
import re
import subprocess

from .execution_binding import digest, file_digest
from .store import ScopeDenied, NotFound

ADAPTER = 'strata-construction-v1'


def image_for(contract, arm):
    if contract.get('adapter') != ADAPTER:
        return contract['image']['id']
    return contract['image']['id'] if arm == 'A' or contract['campaign_stage'] == 'aa' else contract['lineage']['image_id']


def validate_contract(c):
    from .benchmark import validate_contract as validate_reference
    ref = c['reference_contract']
    if ref.get('adapter') not in {'strata-benchmark-v3', 'strata-benchmark-v4'} or ref.get('campaign_stage') != 'aa':
        raise ValueError('An independently pinned Strata A/A reference is required')
    validate_reference(ref)
    if c.get('adapter') != ADAPTER or c.get('version') != 1:
        raise ValueError('Invalid construction comparison adapter')
    # Preserve model, resources, numerical path, independent gates and full experts.
    for key in ('target','image','assets','dataset_path','dataset_sha256','workspace_root','workload','arms','limits','gates','primary_metric'):
        if c.get(key) != ref.get(key):
            raise ValueError('Comparison changes independently admitted ' + key)
    if c['arms']['A'] != c['arms']['B']:
        raise ValueError('Source is the only treatment; runtime profiles must be identical')
    stage = c.get('campaign_stage')
    if stage not in {'aa','screen','confirm'} or c.get('configuration_change') != 'source':
        raise ValueError('Invalid source comparison stage')
    order = list('ABBA') if stage == 'confirm' else list('AB')
    indices = list(range(8,64)) if stage == 'confirm' else list(range(8))
    if (c.get('order') != order or c.get('quality_case_indices') != indices
            or c.get('speed_case_indices') != list(range(4)) or c.get('phases') != ['quality','speed']
            or c.get('campaign_timeout_s') != (2700 if stage == 'confirm' else 1200)
            or c.get('runtime_bounds') != dict(fresh_process_cells=len(order),phase_containers=2*len(order),observer_interval_ms=1000)):
        raise ValueError('Frozen screen/independent holdout protocol differs')
    if c.get('correctness_policy') != 'exact_tokens_and_finish_all_requests' or c.get('promotion_authorized') is not False:
        raise ValueError('Source comparisons require exact output replay; no automatic promotion')
    pins = c.get('execution_sha256', {})
    required = set(ref['execution_sha256']) | {'construction_comparison.py','engine_adapters.py','targets.py'}
    if set(pins) != required or any(not re.fullmatch('[a-f0-9]{64}',v) for v in pins.values()):
        raise ValueError('Complete evaluator execution identity required')
    for key in ('baseline_executable_sha256', 'template_sha256'):
        if not re.fullmatch('[a-f0-9]{64}', c.get(key,'')):
            raise ValueError('Missing pinned ' + key)
    if not isinstance(c.get('engagement_regex'),str) or not 1 <= len(c['engagement_regex']) <= 512:
        raise ValueError('Operator mechanism engagement check required')
    re.compile(c['engagement_regex'])
    lineage = c['lineage']
    if lineage.get('identity') != digest({k:v for k,v in lineage.items() if k!='identity'}):
        raise ValueError('Candidate lineage identity differs')
    if lineage.get('image_id')==c['image']['id']:
        raise ValueError('Source comparison requires a distinct admitted candidate image')
    if not re.fullmatch('sha256:[a-f0-9]{64}',lineage.get('image_id','')):
        raise ValueError('Immutable candidate image required')
    return c


def _template(loop, template_id):
    entries = loop.policy.get('comparison_templates', [])
    matches = [v for v in entries if v['id'] == template_id]
    if len(matches) != 1:
        raise ScopeDenied('Comparison template is not separately operator-admitted')
    entry = matches[0]
    raw = Path(entry['path']).read_bytes()
    if file_digest(entry['path']) != entry['sha256']:
        raise ValueError('Comparison policy changed')
    return json.loads(raw), entry


def _component(host, expected):
    from jiuwenswarm.ccv2.roles import read_roles
    declaration, bundle = host.release(expected['release'])
    if read_roles(declaration,bundle)['materials'].get(expected['material']) != 'component':
        raise ValueError('Candidate source must be a sealed component material')
    material = host.material(expected['release'], expected['material'])
    source = json.loads((bundle/material['path']).read_text())['source']
    return source, material['artifact']


def candidate_lineage(store, task_id, cycle_id, expected):
    from .loop import FactoryLoop
    from .experiment_jobs import ExperimentJobs
    from jiuwenswarm.ccv2.ccv2 import Host
    loop = FactoryLoop(store, task_id)
    cycle = loop._get(cycle_id)
    if cycle['state'] != 'collected' or cycle['contract'].get('adapter') != 'factory-experiment-v1':
        raise ValueError('Collect the source construction diagnostic first')
    result = ExperimentJobs(store).result(cycle['child_task_id'], cycle['attempt_id'])
    if result['state'] != 'succeeded' or result['analysis'].get('verified_complete') is not True:
        raise ValueError('Construction diagnostic evidence is incomplete or failed')
    attempt = store.read(task_id, cycle['build_attempt_id'])
    if attempt['state'] != 'succeeded' or attempt['request'].get('build_target') != 'strata-dsv41':
        raise ValueError('A successful native Strata engine build is required')
    receipt_id = attempt['attempt_id'] + ':receipt'
    receipt = json.loads(store.artifact_bytes(task_id, receipt_id))
    record_id = receipt['build_record']['artifact_id']
    record = json.loads(store.artifact_bytes(task_id, record_id))
    source = attempt['request']['source']
    if any(source[k] != expected[k] or record['source'][k] != expected[k] for k in ('commit','tree')):
        raise ValueError('Built source commit/tree differs from independent admission')
    component_source, artifact = _component(Host(store.home/'ccstore'), expected['component'])
    if any(component_source[k] != source[k] for k in ('commit','tree')):
        raise ValueError('Sealed component does not describe the built source tree')
    if (record.get('status') != 'success' or record.get('image',{}).get('Id') != receipt['image_id']
            or cycle['contract']['image'] != receipt['image_id']
            or cycle.get('build_receipt_sha256') != store.read(task_id,receipt_id)['sha256']):
        raise ValueError('Build receipt, executable image and diagnostic lineage differ')
    admission = json.loads(store.artifact_bytes(task_id,cycle['build_admission_id']))
    if admission['image']['id'] != receipt['image_id'] or admission['build_attempt_id'] != attempt['attempt_id']:
        raise ValueError('Host build admission differs')
    binding = store.get_task(task_id)['constraints']['execution_binding']
    if (attempt['request'].get('execution_binding_id') != binding['binding_id']
            or cycle['contract']['execution_binding_id'] != binding['binding_id']):
        raise ValueError('Build and diagnostic execution bindings differ')
    value = dict(task_id=task_id,source_cycle_id=cycle_id,build_attempt_id=attempt['attempt_id'],
        receipt_sha256=store.read(task_id,receipt_id)['sha256'], build_record_sha256=store.read(task_id,record_id)['sha256'],
        source=source,component=expected['component'],component_artifact=artifact,
        executable_sha256=record['executable_sha256'],image_id=receipt['image_id'],
        execution_binding_id=binding['binding_id'],build_admission_id=cycle['build_admission_id'])
    value['identity'] = digest(value)
    return value


def prepare(loop, comparison_id, source_cycle_id, template_id):
    if os.environ.get('FACTORY_BRIDGE_DIR'):
        return _bridge('construction_prepare',loop.task_id,comparison_id=comparison_id,source_cycle_id=source_cycle_id,template_id=template_id)
    if not re.fullmatch('[A-Za-z0-9_-]{1,100}',comparison_id):
        raise ValueError('Invalid comparison ID')
    template, entry = _template(loop, template_id)
    c = copy.deepcopy(template)
    c['lineage'] = candidate_lineage(loop.store, loop.task_id, source_cycle_id, template['candidate_source'])
    c.update(template_id=template_id, template_sha256=entry['sha256'])
    validate_contract(c)
    artifact_id = 'prepared-comparison:' + comparison_id
    raw = (json.dumps(c,sort_keys=True,allow_nan=False)+'\n').encode()
    artifact = loop.store.put_artifact(loop.task_id,artifact_id,raw,'application/json',None)
    return dict(comparison_id=comparison_id,artifact_id=artifact_id,sha256=artifact['sha256'],execution_authorized=False)


def resolve(loop, comparison_id):
    if os.environ.get('FACTORY_BRIDGE_DIR'):
        return _bridge('construction_resolve',loop.task_id,comparison_id=comparison_id)
    artifact = loop.store.read(loop.task_id,'prepared-comparison:'+comparison_id)
    c = json.loads(loop.store.artifact_bytes(loop.task_id,artifact['artifact_id']))
    template, entry = _template(loop,c['template_id'])
    expected = dict(template,lineage=c['lineage'],template_id=c['template_id'],template_sha256=entry['sha256'])
    if expected != c:
        raise ValueError('Prepared comparison changed independent policy')
    verify_lineage(loop.store,c)
    return validate_contract(c),dict(path=str(loop.store.home/artifact['location']),sha256=artifact['sha256'])


def verify_lineage(store, c):
    lineage = c['lineage']
    actual = candidate_lineage(store,lineage['task_id'],lineage['source_cycle_id'],c['candidate_source'])
    if actual != lineage:
        raise ValueError('Candidate build/source/component lineage changed')


def verify_executable(c, arm):
    expected = c['baseline_executable_sha256'] if arm=='A' or c['campaign_stage']=='aa' else c['lineage']['executable_sha256']
    value = subprocess.check_output(['docker','run','--rm','--pull=never','--network=none','--read-only',
        '--cap-drop=ALL','--security-opt=no-new-privileges','--entrypoint','sha256sum',image_for(c,arm),
        '/opt/strata/strata-dsv41'],text=True,timeout=30).split()[0]
    if value != expected:
        raise ValueError('Actual engine executable differs from admitted build')
    return value


def engagement(c, arm, parsed, stderr):
    from .benchmark import verify_prefill_engagement
    verify_prefill_engagement(c['reference_contract'],arm,parsed,stderr)
    if c['campaign_stage'] != 'aa' and arm=='B' and re.search(c['engagement_regex'],stderr,re.MULTILINE) is None:
        raise ValueError('Candidate mechanism did not engage')


def analyze(c, dataset, cells, decode):
    from .broad_benchmark import analyze_validated
    validate_contract(c)
    report = analyze_validated(c,dataset,cells,decode)
    # Include all warmups, long outputs and repeat pairs; equal answers alone are insufficient.
    outputs = [[(r['ids'],r['finish']) for phase in ('quality','speed') for r in cell[phase]['requests']] for cell in cells]
    exact = bool(outputs) and all(row == outputs[0] for row in outputs)
    report.update(scope='pinned_source_engine_comparison',lineage=c['lineage'],
                  execution_complete=True,evidence_completeness='complete',promotion_authorized=False)
    report['gates']['exact_tokens_and_finish_all_requests'] = exact
    if not exact:
        report['verdict']='reject_correctness'
    if c['reference_contract']['adapter']=='strata-benchmark-v4':
        placements=[cell[phase].get('fixed_placement_identity') for cell in cells for phase in ('quality','speed')]
        equal=bool(placements) and placements[0] is not None and all(v==placements[0] for v in placements)
        report['gates']['complete_fixed_placement_equal_across_all_processes']=equal
        if not equal:report['verdict']='inconclusive'
    if c['campaign_stage']=='confirm':
        report['independent_holdout_case_indices']=c['quality_case_indices']
        report['limitations'].append('Holdout quality excludes the eight screening questions; timing repeats use the same pinned workload.')
    return report


def stage_admission(loop, c):
    prior = [v for v in loop._cycles() if v.get('contract',{}).get('adapter')==ADAPTER and v['state']=='collected']
    matching = [v for v in prior if v['contract']['lineage']==c['lineage'] and
                v['contract']['reference_contract']==c['reference_contract'] and v['contract']['engagement_regex']==c['engagement_regex']]
    def passed(stage, verdict):
        for v in matching:
            if v['contract']['campaign_stage'] != stage: continue
            report = raw_report(loop,v)
            if report.get('verdict')==verdict and (stage!='aa' or report['gates']['aa_timing_stable']):return True
        return False
    if c['campaign_stage']!='aa' and not passed('aa','aa_valid'):
        raise ScopeDenied('Source comparison requires collected matched A/A')
    if c['campaign_stage']=='confirm' and not passed('screen','screen_candidate'):
        raise ScopeDenied('Independent confirmation requires a qualifying same-source screen')


def validate_acceptance(store, task_id, evidence_ids=None):
    """Re-read raw benchmark files, lineage and operator templates; summaries cannot keep a candidate."""
    from .loop import FactoryLoop
    host = getattr(store,'_store',store)
    loop = FactoryLoop(host,task_id)
    reports = []
    for cycle in loop._cycles():
        c=cycle['contract']
        if c.get('adapter')!=ADAPTER or cycle['state']!='collected':continue
        report=raw_report(loop,cycle)
        reports.append((cycle,report))
    for confirm, report in reports:
        c=confirm['contract']
        if (c['campaign_stage']=='confirm' and report['verdict']=='accept'
                and (evidence_ids is None or confirm['evidence_id'] in evidence_ids)):
            others=[(v,r) for v,r in reports if v['contract']['lineage']==c['lineage']
                    and v['contract']['reference_contract']==c['reference_contract']
                    and v['contract']['engagement_regex']==c['engagement_regex']]
            if (any(v['contract']['campaign_stage']=='aa' and r['verdict']=='aa_valid' and r['gates']['aa_timing_stable'] for v,r in others)
                    and any(v['contract']['campaign_stage']=='screen' and r['verdict']=='screen_candidate' for v,r in others)):
                return dict(lineage=c['lineage'],evidence_id=confirm['evidence_id'],verdict='accept',
                            ratio=report['speed']['geometric_mean_ratio_B_over_A'])
    raise ValueError('Keep/accept requires independent complete A/A, screen and exact holdout confirmation')


def record_evaluation(loop, cycle, report, evidence_id):
    """Persist the independent host evaluation with the exact source/build lineage."""
    c=cycle['contract'];identifier='engine-evaluation:'+str(cycle['number'])
    try: return loop.store.read(loop.task_id,identifier)
    except NotFound: pass
    complete=(report.get('verification',{}).get('raw_files_verified') is True
              and report.get('verification',{}).get('complete_cells')==len(c['order']))
    return loop.store.add_evaluation(loop.task_id,dict(eval_id=identifier,
        contract_id=cycle['contract_path'],contract_version='1',contract=c,
        inputs=dict(lineage=c['lineage'],evidence_id=evidence_id,attempt_id=cycle['attempt_id'],
                    comparison_verdict=report.get('verdict','inconclusive'),promotion_authorized=False),
        execution_outcome='ok' if report.get('execution_complete') else 'failed',
        correctness='pass' if complete and report.get('gates',{}).get('exact_tokens_and_finish_all_requests') else 'not_verified',
        evidence_completeness='complete' if complete else 'incomplete'))


def _bridge(operation, task_id, **values):
    from .bridge import call
    result=call(operation,task_id=task_id,**values)
    result.check_returncode()
    return json.loads(result.stdout)


def raw_report(loop, cycle):
    if os.environ.get('FACTORY_BRIDGE_DIR'):
        return _bridge('construction_report',loop.task_id,cycle_id=cycle['cycle_id'])
    from .benchmark import analyze_files
    import hashlib
    host=loop.store;c=cycle['contract']
    resolved,_=resolve(loop,cycle['request']['comparison_id'])
    if resolved!=c:raise ValueError('Evaluation contract differs from independent admission')
    attempt=host.read(cycle['child_task_id'],cycle['attempt_id'])
    child=host.get_task(cycle['child_task_id'])
    raw=(json.dumps(c,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    if (attempt['state']!='succeeded' or attempt['request'].get('contract')!=c
            or attempt['request'].get('contract_sha256')!=hashlib.sha256(raw).hexdigest()
            or child['constraints'].get('factory_loop_parent')!=loop.task_id):
        raise ValueError('Comparison ownership or execution differs')
    root=host.home/'benchmark-spool'/attempt['attempt_id']
    observation=host.read(child['task_id'],attempt['attempt_id']+':observation')
    retained=observation['source_artifacts']
    if attempt['attempt_id']+':manifest.json' not in retained:
        raise ValueError('Retained comparison manifest missing')
    for artifact_id in retained:
        relative=artifact_id.removeprefix(attempt['attempt_id']+':')
        path=root/relative
        if not path.resolve().is_relative_to(root.resolve()) or path.read_bytes()!=host.artifact_bytes(child['task_id'],artifact_id):
            raise ValueError('Changed/escaping retained comparison evidence: '+relative)
    config=json.loads((root/'config.json').read_text())
    if config.get('task_id')!=child['task_id'] or config.get('attempt_id')!=attempt['attempt_id']:
        raise ValueError('Raw evaluation belongs to another attempt')
    report=analyze_files(c,root)
    if (report.get('verification',{}).get('raw_files_verified') is not True
            or report['verification'].get('independent_native_parse') is not True
            or report['verification'].get('complete_cells')!=len(c['order'])):
        raise ValueError('Raw evaluation incomplete')
    return report


def operator_templates(reference, candidate_source, baseline_executable_sha256, engagement_regex, hypothesis):
    """Prepare reviewable policies without submitting work or admitting a campaign.

    Only the operator places these outputs in constraints.factory_loop.comparison_templates.
    Call against the frozen runtime: these execution pins deliberately change with the backend.
    """
    templates={}
    for stage in ('aa','screen','confirm'):
        c=copy.deepcopy(reference)
        c.update(adapter=ADAPTER,version=1,reference_contract=copy.deepcopy(reference),
            candidate_source=copy.deepcopy(candidate_source),baseline_executable_sha256=baseline_executable_sha256,
            engagement_regex=engagement_regex,hypothesis=hypothesis,configuration_change='source',campaign_stage=stage,
            phases=['quality','speed'],correctness_policy='exact_tokens_and_finish_all_requests',promotion_authorized=False)
        if stage=='confirm':
            c.update(order=list('ABBA'),quality_case_indices=list(range(8,64)),campaign_timeout_s=2700,
                     runtime_bounds=dict(fresh_process_cells=4,phase_containers=8,observer_interval_ms=1000))
        c['execution_sha256']={name:file_digest(Path(__file__).parent/name) for name in
            set(reference['execution_sha256'])|{'construction_comparison.py','engine_adapters.py','targets.py'}}
        templates[stage]=c
    return templates
