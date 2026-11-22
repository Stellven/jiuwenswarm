"""Diagnostic A/A of a source-built fixed-placement candidate. Never accepts a gain."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import re

ADAPTER='strata-benchmark-v4'
BUDGET='76000000000'
COMMIT='89ae0ee6123597636ef162dec826230186c00f3b'
TREE='55eb1b479a648d5211b2846302a60b6c79f2528e'
SOURCE_FILES={
 'docs/FIXED_PLACEMENT.md':'60ade31ded4ccee4484f97f6a052e86b5731dbe637b4e534a9a781bc20e0e531',
 'src/dsv41/ds4_fixed_placement.hpp':'c100288504de641d16455d979102f2dfb486d4c3c34f9c2854d3425db9e91327',
 'src/dsv41/ds4_fixed_placement_test.cpp':'7dd8ab462b58fab324a9dfa766d01aee67c5bcc6bfc9fbec047764c7a24b541b',
 'src/dsv41/ds4_model.cu':'63ffd0f7c1b1bee24e9fd710ee9836f5748fbbe208d7d2657b62e575f25b94d6',
}
PATCH='b837a970a5835dcff63fef93d251f7b352ca49f68d3cea42e91ec189d74b4873'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def shaped(c):
    out=copy.deepcopy(c)
    out.update(adapter='strata-benchmark-v3',version=3)
    for arm in out['arms'].values():arm['environment'].pop('DS4_EXPERT_BUDGET_BYTES',None)
    out['execution_sha256'].pop('fixed_placement_benchmark.py',None)
    out['execution_sha256'].pop('engine_adapters.py',None)
    return out


def validate_build(c):
    identity=c['candidate_build']
    if sha(identity['receipt_path'])!=identity['receipt_sha256']:
        raise ValueError('Fixed-placement build receipt changed')
    receipt=json.loads(Path(identity['receipt_path']).read_text())
    if (receipt.get('status')!='success' or receipt.get('host_architecture') not in ('aarch64','arm64') or receipt.get('target')!='spark-gb10'
            or receipt.get('source',{}).get('commit')!=COMMIT
            or receipt['source'].get('tree')!=TREE
            or receipt.get('image',{}).get('Id')!=c['image']['id']
            or receipt.get('image',{}).get('Architecture')!='arm64'
            or receipt['image'].get('Config',{}).get('Labels',{}).get('factory.source')!=COMMIT
            or receipt.get('dependency',{}).get('commit')!='3cf03257f219afbe7334045ff7c6a06ac68c627d'):
        raise ValueError('Build receipt does not establish admitted source/dependency/image identity')
    if not re.fullmatch('[a-f0-9]{64}',receipt.get('executable_sha256','')):
        raise ValueError('Built executable identity missing')
    if sha(identity['source_record_path'])!=identity['source_record_sha256']:
        raise ValueError('Source CC identity record changed')
    source=json.loads(Path(identity['source_record_path']).read_text())
    if source.get('candidate_commit')!=COMMIT or source.get('candidate_tree')!=TREE or source.get('patch_sha256')!=PATCH:
        raise ValueError('Source CC candidate differs')
    if source.get('files')!=SOURCE_FILES or source.get('clean') is not True or source.get('base_commit')!='ffa80d73133ea5c548aefe57889a16e8085a938f':
        raise ValueError('Complete exact committed candidate file identities required')
    if sha(identity['patch_path'])!=PATCH:raise ValueError('Source CC patch changed')
    root=Path(source['source'])
    for name,digest in source['files'].items():
        path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()) or sha(path)!=digest:
            raise ValueError('Committed candidate file differs: '+name)
    return receipt


def validate_contract(c):
    from . import broad_benchmark
    if c.get('adapter')!=ADAPTER or c.get('version')!=4:
        raise ValueError('Wrong fixed-placement adapter')
    if c.get('campaign_stage')!='aa' or c.get('configuration_change')!='aa' or c.get('promotion_authorized') is not False:
        raise ValueError('Fixed placement is nonpromoting A/A only')
    if c.get('expected_placement_layers')!=40 or c.get('expected_experts_per_layer')!=384:
        raise ValueError('Frozen full model placement shape required')
    if set(c['execution_sha256']) != set(broad_benchmark.validate_contract(shaped(c))['execution_sha256']) | {'fixed_placement_benchmark.py','engine_adapters.py'}:
        raise ValueError('Complete fixed placement execution source pins required')
    if any(not re.fullmatch('[a-f0-9]{64}',v) for v in c['execution_sha256'].values()):
        raise ValueError('Invalid fixed placement execution pin')
    if c['arms']['A']!=c['arms']['B'] or any(a['environment'].get('DS4_EXPERT_BUDGET_BYTES')!=BUDGET for a in c['arms'].values()):
        raise ValueError('Exact identical fixed budget required in both A/A arms')
    validate_build(c)
    return c


def engagement(c,arm,parsed,stderr):
    from .broad_benchmark import engagement as broad_engagement
    broad_engagement(shaped(c),arm,parsed,stderr)
    lines=stderr.splitlines()
    if (sum(line.startswith('ds4: fixed expert budget ') for line in lines)!=1
            or sum(line.startswith('ds4: fixed placement layer=') for line in lines)!=40
            or sum(line.startswith('ds4: fixed placement layers=') for line in lines)!=1):
        raise ValueError('Missing, duplicated or malformed complete fixed-placement startup evidence')
    budget=re.findall(r'^ds4: fixed expert budget requested=(\d+) effective=(\d+) safe=(\d+) bytes$',stderr,re.M)
    if len(budget)!=1 or budget[0][:2]!=(BUDGET,BUDGET) or int(budget[0][2])<int(BUDGET):
        raise ValueError('Exact requested/effective fixed budget or safe admission missing')
    layers=re.findall(r'^ds4: fixed placement layer=(\d+) experts=(\d+) resident=(\d+) fnv1a64=([a-f0-9]{16})$',stderr,re.M)
    if (len(layers)!=40 or [int(x[0]) for x in layers]!=list(range(40))
            or any(int(x[1])!=384 or not 0<=int(x[2])<=384 for x in layers)):
        raise ValueError('Complete per-layer placement identity missing')
    aggregate=re.findall(r'^ds4: fixed placement layers=(\d+) fnv1a64=([a-f0-9]{16})$',stderr,re.M)
    if len(aggregate)!=1 or aggregate[0][0]!='40':raise ValueError('Aggregate placement identity missing')
    value=14695981039346656037
    for row in layers:
        word=int(row[3],16)
        for byte in word.to_bytes(8,'little'):
            value=((value^byte)*1099511628211)&((1<<64)-1)
    if f'{value:016x}'!=aggregate[0][1]:raise ValueError('Aggregate placement hash inconsistent with all layers')
    parsed['fixed_placement_identity']=dict(layers=layers,aggregate=aggregate[0],requested_budget=BUDGET,effective_budget=BUDGET)


def analyze(c,d,cells,decode):
    from .broad_benchmark import analyze as broad_analyze
    validate_contract(c)
    report=broad_analyze(shaped(c),d,cells,decode)
    placement=[cell[phase].get('fixed_placement_identity') for cell in cells for phase in ('quality','speed')]
    equal=len(placement)==4 and placement[0] is not None and all(p==placement[0] for p in placement)
    report['gates']['complete_fixed_placement_equal_across_all_processes']=equal
    report['fixed_placement']=dict(processes=4,complete_identity=placement,all_equal=equal)
    report['adapter']=ADAPTER
    report['scope']='candidate_image_fixed_budget_aa_diagnostic_only'
    report['promotion_authorized']=False
    report['performance_acceptance_evaluated']=False
    report['verdict']='fixed_placement_aa_observed_repeatable' if equal and report['verdict']=='aa_valid' else 'fixed_placement_aa_inconclusive'
    report['limitations'].append('New source image A/A only; no historical performance or correctness equivalence established. Fixed placement is not proven to explain prior divergence.')
    return report


def admit_final_slot(loop,contract,*,reserving):
    """The original A/A plus all continuation reservations share one cap/lock."""
    mode=loop.task.get('constraints',{}).get('fixed_placement_final_slot')
    if mode!={'origin_task_id':'spark-broad-throughput-004','aggregate_max_experiments':10}:
        raise ValueError('Explicit operator final-slot policy required')
    if loop.policy['max_cycles']!=1 or loop.policy['max_experiments']!=1:
        raise ValueError('Exactly one final-slot experiment permitted')
    used=0
    for row in loop.store._db.execute('SELECT task_id,constraints FROM tasks'):
        constraints=json.loads(row['constraints'])
        linked=(row['task_id']==mode['origin_task_id'] or
            constraints.get('nonpromoting_diagnostics',{}).get('origin_task_id')==mode['origin_task_id'] or
            constraints.get('fixed_placement_final_slot',{}).get('origin_task_id')==mode['origin_task_id'] or
            constraints.get('fixed_placement_screens',{}).get('origin_task_id')==mode['origin_task_id'])
        if linked:
            used+=loop.store._db.execute('SELECT COUNT(*) FROM factory_loop_cycles WHERE task_id=?',(row['task_id'],)).fetchone()[0]
    if used+int(reserving)>10:raise ValueError('Ten-experiment aggregate cap exhausted')
    validate_contract(contract)
    return {'aggregate_used_before_reservation':used,'aggregate_cap':10}
