"""Independent read-only checks of every frozen R07 publication and export."""
from pathlib import Path,PurePosixPath
import hashlib,json,sqlite3,zipfile
BASE=Path('docs/code/Missions/M0/M0-001/evidence/live-R07').resolve()
OUT=BASE.parent/'v06-r07-export-independent.json'
campaign=json.loads((BASE/'outcomes.json').read_text(encoding='utf-8'))
results=[]
for case in campaign['cases']:
 item={'case':case['case'],'actual':case['actual'],'run_id':case['run_id'],'campaign_result':case['result']}
 try:
  run=case['run_id'];location=BASE/case['case'];database=location/'state/runs.sqlite3'
  connection=sqlite3.connect('file:'+str(database).replace('\\','/')+'?mode=ro',uri=True)
  scopes=connection.execute('SELECT scope,subject,gate_ref,record_ref FROM acceptance WHERE run_id=?',(run,)).fetchall();connection.close()
  released={scope:{'subject':json.loads(subject),'gate':json.loads(gate),'receipt':json.loads(receipt)} for scope,subject,gate,receipt in scopes}
  with zipfile.ZipFile(location/'evidence.zip') as archive:
   manifest=json.loads(archive.read('manifest.json'));entries=manifest['files'];index={f['artifact_ref']['id']:f for f in entries}
   assert len(index)==len(entries),'Duplicate manifest reference'
   for entry in entries:
    path=entry['path'];parts=PurePosixPath(path);ref=entry['artifact_ref']
    assert not parts.is_absolute() and '..' not in parts.parts and ref['id']==path
    assert hashlib.sha256(archive.read(path)).hexdigest()==ref['sha256'],path
   assert set(archive.namelist())=={e['path'] for e in entries}|{'manifest.json'}
   resolved=set()
   def walk(value):
    if isinstance(value,dict):
     pin=None
     if isinstance(value.get('id'),str) and isinstance(value.get('sha256'),str):pin=(value['id'],value['sha256'])
     elif isinstance(value.get('ref'),str) and isinstance(value.get('sha256'),str):pin=(value['ref'],value['sha256'])
     if pin:
      assert pin[0] in index and index[pin[0]]['artifact_ref']['sha256']==pin[1],pin
      resolved.add(pin)
     for child in value.values():walk(child)
    elif isinstance(value,list):
     for child in value:walk(child)
   walk(manifest)
   for entry in entries:
    if entry['media_type'].startswith('application/json') and not entry['path'].endswith('.schema.json'):
     walk(json.loads(archive.read(entry['path'])))
   observations=[json.loads(archive.read(entry['path'])) for entry in entries if entry['path'].endswith('_Invocation_Observation.json')]
   roles=[o['subnode_id'] for o in observations]
   if case['actual']=='completed':
    assert set(released)=={'intention','requirements','node'}
    consumer=json.loads((location/'consumer-result.json').read_text(encoding='utf-8'))
    node= released['node'];receipt=json.loads(archive.read(node['receipt']['id']));gate=json.loads(archive.read(node['gate']['id']))
    brief=json.loads(archive.read(node['subject']['id']))
    assert consumer['node_acceptance_ref']==node['receipt']
    assert consumer['output_refs']==receipt['output_refs']==gate['accepted_refs']==[node['subject']]
    assert consumer['research_brief']==brief and brief['schema_version']=='2.0.0'
    assert node['subject']==released['requirements']['subject'] and gate['action']=='advance'
    assert len(observations)==4 and sum(o['model_calls'] for o in observations)==4
    internal=[json.loads(archive.read(released[s]['gate']['id'])) for s in ('intention','requirements')]
    assert gate['invocation_refs']==internal[0]['invocation_refs']+internal[1]['invocation_refs']
    assert gate['assessment_ref']==internal[1]['assessment_ref']
    item['exact_durable_consumer_release']=True
   else:
    assert 'node' not in released and 'Accepted_node.json' not in index
    item['no_durable_node_or_receipt']=True
    if case['case'] in ('topic','contradiction','unsupported_interpretation'):
     assert not any(role.startswith('requirements') for role in roles),roles
     assert not released
    if case['case']=='lost_constraint':assert set(released)=={'intention'}
   if case.get('protected_challenge'):
    stage='intention' if case['case']=='unsupported_interpretation' else 'requirements'
    check=json.loads(archive.read(stage.title()+'_Checks.json'))
    assessment=json.loads(archive.read('Intent_Assessment.json' if stage=='intention' else 'Requirements_Assessment.json'))
    settings=json.loads(archive.read(stage+'_Adapter_Settings.json'))
    assert settings['protected_challenge']['stage']==stage
    assert all(f['outcome']=='PASS' for f in check['results'])
    assert assessment['verdict']=='FAIL' and stage+'.verifier' in roles
    item['actual_mechanical_pass_semantic_rejection']=True
   item.update(result='PASS',named_exact_hash_files=len(entries),resolved_unique_refs=len(resolved),durable_scopes=sorted(released),dispatch_roles=roles)
 except Exception as error:item.update(result='FAIL',reason=type(error).__name__+': '+str(error))
 results.append(item)
report={'verification':'V06 independent all-case published-output/export boundary','tested_candidate':campaign['candidate'],
        'command':'.venv-intent/Scripts/python.exe docs/code/Missions/M0/M0-001/evidence/v06-r07-export-check.py',
        'working_directory':str(Path.cwd()),'dependency_mode':'All actual completed R07 terminal SQLite opened read-only and exact captured ordinary client API ZIP/consumer outputs; no model calls/replay',
        'expected':'Every named hash/ref/pin resolves; completed Brief equals exact durable node receipt and consumer; negatives publish no node, blocked Intent no Requirements; challenges mechanically valid and actually semantically rejected',
        'cases':results,'result':'PASS' if len(results)==6 and all(r['result']=='PASS' for r in results) else 'FAIL',
        'limitations':['One observed sample per case, no semantic reliability/rate claim. Protected injected challenges remain invalid for product. R07 candidate is9227; later intake-only change applicability is separately established by v06-r07-intake-equivalence.json; browser/container prerequisites remain blocked.']}
OUT.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'result':report['result'],'case_count':len(results),'named_hash_count':sum(r.get('named_exact_hash_files',0) for r in results),'cases':results}))
raise SystemExit(0 if report['result']=='PASS' else 1)
