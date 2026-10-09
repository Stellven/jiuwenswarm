"""Read-only prior-run comparison against independent current qualification."""
from pathlib import Path
import copy,gc,hashlib,json,sqlite3,sys,tempfile
sys.path.insert(0,str(Path('standalone/intent_compiler').resolve()))
from intent_compiler.config import Config
from intent_compiler.intake import qualify
from intent_compiler.store import Store

BASE=Path('docs/code/Missions/M0/M0-001/evidence/live-R07').resolve()
OUTPUT=BASE.parent/'v06-r07-intake-equivalence.json'
outcomes=json.loads((BASE/'outcomes.json').read_text(encoding='utf-8'))
rows=[]
for item in outcomes['cases']:
 row={'case':item['case'],'run_id':item['run_id']}
 try:
  original=BASE/item['case']/'state';run=item['run_id'];artifacts=original/'artifacts'/run
  connection=sqlite3.connect('file:'+str((original/'runs.sqlite3').resolve()).replace('\\','/')+'?mode=ro',uri=True)
  state=json.loads(connection.execute('SELECT data FROM runs WHERE id=?',(run,)).fetchone()[0]);connection.close()
  submission=state['submission'];frozen=json.loads((artifacts/'Run_Configuration.json').read_text(encoding='utf-8'))
  assert not submission.get('resources'), 'Affected explicit role was in original campaign'
  with tempfile.TemporaryDirectory(prefix='m0-qualified-equivalence-',ignore_cleanup_errors=True) as temporary:
   config=Config(Path(temporary)/'state',BASE/'visible-input',input_directory=BASE/'visible-input/docs',
                 account_id=frozen['account_id'],workspace_id=frozen['workspace_id'],profile_id=frozen['profile_id'],
                 model_mode=frozen['model_mode'],model_name=frozen['requested_model'],
                 call_time_s=frozen['call_time_s'],node_time_s=frozen['node_time_s'],
                 max_source_bytes=frozen['max_source_bytes'],max_resource_bytes=frozen['max_resource_bytes'],
                 max_output_bytes=frozen['max_output_bytes'],memory_mb=frozen['memory_mb'],token_budget=frozen['token_budget'])
   shadow=Store(config.state_dir)
   qualified=qualify(config,shadow,run,submission['request'],documents=submission.get('documents'),
                     resources=submission.get('resources'),input_directory=submission.get('input_directory'))
   old_qualified=state['qualified']
   assert qualified==old_qualified, 'Qualified dictionary/ref/text differs'
   old_intake=(artifacts/'Qualified_Intake.json').read_bytes()
   assert shadow.read_bytes(run,'Qualified_Intake.json')==old_intake, 'Intake capture bytes differ'
   bindings=[{'id':'input'+str(i),'role':shadow.get_json(run,ref)['kind'],'resource_ref':ref} for i,ref in enumerate(qualified['intake']['resource_refs'])]
   disclosed=[]
   for path in sorted(artifacts.glob('*_Disclosed_Input.json')):
    observed=path.read_bytes();replacement=json.loads(observed.decode('utf-8'))
    replacement.update(intake=qualified['intake'],intake_ref=qualified['intake_ref'],sources=qualified['sources'],resource_bindings=bindings)
    regenerated=json.dumps(replacement,ensure_ascii=False).encode('utf-8')
    assert regenerated==observed, 'Host-disclosed model payload bytes differ: '+path.name
    disclosed.append({'name':path.name,'observed_sha256':hashlib.sha256(observed).hexdigest(),'current_regenerated_sha256':hashlib.sha256(regenerated).hexdigest(),'result':'PASS'})
   row.update(result='PASS',qualified_dictionary_exact=True,qualified_capture_sha256=hashlib.sha256(old_intake).hexdigest(),disclosed_payloads=disclosed)
   gc.collect()
 except Exception as error:
  row.update(result='FAIL',reason=type(error).__name__+': '+str(error))
 rows.append(row)
report={'verification':'V06 R07 scoped qualification/context equivalence after T028','tested_candidate':outcomes['candidate'],
        'current_intake_sha256':hashlib.sha256(Path('standalone/intent_compiler/intent_compiler/intake.py').read_bytes()).hexdigest(),
        'command':'.venv-intent/Scripts/python.exe docs/code/Missions/M0/M0-001/evidence/v06-r07-intake-equivalence.py',
        'working_directory':str(Path.cwd()),'dependency_mode':'Prior terminal SQLite/artifacts read-only; new independent temporary qualification store; no original-run writes/model calls/workflow replay',
        'expected':'All six original exact inputs without explicit resource role produce byte-identical qualified intake and all18 disclosed model payloads under current qualifier',
        'cases':rows,'result':'PASS' if len(rows)==6 and all(row['result']=='PASS' for row in rows) else 'FAIL',
        'limitations':['Equivalence applies only to the six actual R07 inputs (none used explicit reference_document resources). New role behavior is separately verified by B01/API regressions; no live sample of that changed route is claimed. Other unchanged model outputs/observations in copied context are not regenerated.']}
OUTPUT.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'result':report['result'],'case_count':len(rows),'disclosed_payload_count':sum(len(r.get('disclosed_payloads',[])) for r in rows),'cases':[{'case':r['case'],'result':r['result'],'reason':r.get('reason')} for r in rows]}))
raise SystemExit(0 if report['result']=='PASS' else 1)
