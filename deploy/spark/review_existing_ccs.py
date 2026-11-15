"""Exercise existing CC material/evidence reuse and record Strata adapter gaps."""
import argparse,importlib.util,json,os
from pathlib import Path
from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory.store import Store,NotFound
ROOT=Path('/home/user2/software-factory-spark-20261113');REPO=Path('/factory')
p=argparse.ArgumentParser();p.add_argument('--resume-read',action='store_true');a=p.parse_args()
home=ROOT/'review-store';task='spark-lab-review'
os.environ.update(FACTORY_HOME=str(home),FACTORY_TASK_ID=task,FACTORY_WORKSPACE=str(ROOT))
with Store(home) as s:
    try:s.get_task(task)
    except NotFound:s.create_task(dict(task_id=task,objective='Review Spark lab evidence and recovery; no performance acceptance',target={'profile':'spark-gb10'},allowed_effects=['process.exec']))
host=Host(ROOT/'review-ccstore',session_grants=['process.exec'])
ccs=REPO/'jiuwenswarm/factory/ccs'
evidence=host.prepare(ccs/'evidence')
if a.resume_read:
    result=host.call(evidence,'read',{'id':'review-findings'},key='review-resume-read-001')
    assert result['state']=='succeeded',result
    (ROOT/'results/review-cc-resume-read.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(state=result['state'],purpose='Fresh container read of durable review observation')))
    raise SystemExit(0)
materials={}
for capsule,names in [('methodology_ab',['methodology']),('integration_skill',['integrate','repair','preflight']),('expert_streaming',['guide','method','ontology'])]:
    release=host.prepare(ccs/capsule)
    materials[capsule]=dict(release=release,materials={name:host.material(release,name) for name in names})
streaming=host.prepare(ccs/'expert_streaming')
args=json.loads((ROOT/'engine-investigation/measured-profile.json').read_text())['args']
applicability=host.call(streaming,'applicability',{'model_path':'/model-first.gguf','argv':args},key='review-strata-applicability-001')
assert applicability['state']=='failed','The no-contract inspection gap unexpectedly changed; review result'
from jiuwenswarm.factory.expert_streaming import applicability as direct_applicability,parse_engagement
helper=direct_applicability('/model-first.gguf',args)
assert helper['verdict']!='applicable','Do not treat this llama-only heuristic as verified Strata applicability'
engagement=parse_engagement((ROOT/'results/engine-long-forced-draft-128-001/engine/stderr.log').read_text())
checks=json.loads((ROOT/'results/review-engine-evidence-checks.json').read_text())
crashes=json.loads((ROOT/'results/review-crash-probes-final/summary.json').read_text())
refs=[]
for name,path in [('engine-checks',ROOT/'results/review-engine-evidence-checks.json'),('crash-probes',ROOT/'results/review-crash-probes-final/summary.json')]:
    result=host.call(evidence,'publish',dict(type='artifact',record=dict(artifact_id='review-'+name,text=path.read_text(),media_type='application/json')),key='review-artifact-v2-'+name)
    assert result['state']=='succeeded',result
    refs.append(result['outputs']['record']['artifact_id'])
observation=host.call(evidence,'publish',dict(type='observation',record=dict(obs_id='review-findings',kind='spark_lab_review',values=dict(recorded_cells_verified=len(checks['results']),recorded_tokens_verified=sum(r['total_generated_tokens'] for r in checks['results']),crash_probes_passed=sum(r['status']=='passed' for r in crashes['results']),strata_applicability_cc='failed_without_contract',strata_helper_verdict=helper['verdict']),source_artifacts=refs,limitations='Functional evidence checks and CPU-only lifecycle probes. No new scored A/B result. No reboot/power-loss test.')),key='review-observation-001')
assert observation['state']=='succeeded',observation
query=host.call(evidence,'query',{'limit':20},key='review-query-001');assert query['state']=='succeeded',query
result=dict(materials=materials,native_strata_applicability=applicability,direct_strata_helper=helper,direct_llama_engagement_parser_on_strata_log=engagement,evidence_publish=observation,evidence_query=query,scope='Existing native/material CCs only; no new CCs or promotions')
(ROOT/'results/review-existing-ccs.json').write_text(json.dumps(result,indent=2))
print(json.dumps(dict(evidence_publish=observation['state'],query=query['state'],applicability_cc=applicability['state'],direct_helper_verdict=helper['verdict'],materials=list(materials))))
