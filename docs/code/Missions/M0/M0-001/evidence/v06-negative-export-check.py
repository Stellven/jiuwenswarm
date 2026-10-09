"""Read-only verification of completed negative live runs and exact exports."""
from pathlib import Path, PurePosixPath
import hashlib,json,sqlite3,zipfile

BASE=Path('docs/code/Missions/M0/M0-001/evidence/live-R06')
OUT=Path('docs/code/Missions/M0/M0-001/evidence/v06-negative-export-independent.json')
observed=json.loads((BASE/'outcomes.json').read_text(encoding='utf-8'))
results=[]
for case in observed['cases']:
 if case['case']=='actionable':
  continue # Separate root positive durable release/147-file proof is retained.
 item={'case':case['case'],'expected':case['expected'],'actual':case.get('actual'),'run_id':case.get('run_id')}
 try:
  location=BASE/case['case'];run=case['run_id']
  connection=sqlite3.connect('file:'+str((location/'state/runs.sqlite3').resolve()).replace('\\','/')+'?mode=ro',uri=True)
  rows=connection.execute('SELECT scope,subject,record_ref FROM acceptance WHERE run_id=?',(run,)).fetchall()
  connection.close()
  item['durable_scopes']=[r[0] for r in rows]
  assert not any(r[0]=='node' for r in rows), 'Terminal negative publishes node acceptance'
  with zipfile.ZipFile(location/'evidence.zip') as archive:
   names=archive.namelist();manifest=json.loads(archive.read('manifest.json'))
   index={entry['artifact_ref']['id']:entry for entry in manifest['files']}
   seen=[]
   for entry in manifest['files']:
    path=entry['path'];parts=PurePosixPath(path)
    assert not parts.is_absolute() and '..' not in parts.parts
    body=archive.read(path);ref=entry['artifact_ref']
    assert hashlib.sha256(body).hexdigest()==ref['sha256'],path
    assert ref['id']==path,path
    seen.append(path)
   assert len(seen)==len(set(seen))
   assert set(names)==set(seen)|{'manifest.json'}
   assert 'Accepted_node.json' not in seen
   resolved=set();unresolved=[]
   def refs(value):
    if isinstance(value,dict):
     if isinstance(value.get('id'),str) and isinstance(value.get('sha256'),str):
      rid=value['id'];sha=value['sha256'];entry=index.get(rid)
      if entry is None or entry['artifact_ref']['sha256']!=sha:unresolved.append({'id':rid,'sha256':sha})
      else:resolved.add((rid,sha))
     if isinstance(value.get('ref'),str) and isinstance(value.get('sha256'),str):
      rid=value['ref'];sha=value['sha256'];entry=index.get(rid)
      if entry is None or entry['artifact_ref']['sha256']!=sha:unresolved.append({'id':rid,'sha256':sha})
      else:resolved.add((rid,sha))
     for child in value.values():refs(child)
    elif isinstance(value,list):
     for child in value:refs(child)
   refs(manifest)
   for entry in manifest['files']:
    if entry['media_type'].startswith('application/json') and not entry['path'].endswith('.schema.json'):
     refs(json.loads(archive.read(entry['path'])))
   assert not unresolved,unresolved[:4]
   observations=[json.loads(archive.read(entry['path'])) for entry in manifest['files'] if entry.get('ext',{}).get('m0.intent',{}).get('artifact_type')=='invocation-observation']
   # Actual observation artifact filenames and payloads, without trusting an
   # optional metadata extension layout, identify dispatched role inventory.
   observations=[json.loads(archive.read(name)) for name in seen if name.endswith('_Invocation_Observation.json')]
   roles=[v['subnode_id'] for v in observations]
   if case['case'] in ('topic','contradiction','unsupported_interpretation','lost_constraint'):
    assert all(not role.startswith('requirements') for role in roles),roles
   item.update(result='PASS',named_files=len(seen),exact_hash_files=len(seen),resolved_unique_refs=len(resolved),dispatch_roles=roles,node_receipt_absent=True)
   if case['case']=='unsupported_interpretation':
    checks=json.loads(archive.read('Intention_Checks.json'));assessment=json.loads(archive.read('Intent_Assessment.json'))
    assert all(f['outcome']=='PASS' for f in checks['results']) and assessment['verdict']=='FAIL'
    item['actual_semantic_negative']=True
   if case['case']=='lost_constraint':
    item['actual_semantic_negative']=False
    item['limitation']='R06 halted before Requirements; loss injection was not exercised'
  results.append(item)
 except Exception as error:
  item.update(result='FAIL',reason=type(error).__name__+': '+str(error));results.append(item)
report={'verification':'V06 independent negative publication/export boundary','candidate':observed['candidate'],'command':'.venv-intent/Scripts/python.exe docs/code/Missions/M0/M0-001/evidence/v06-negative-export-check.py','working_directory':str(Path.cwd()),'dependency_mode':'Actual completed live run SQLite in read-only mode and captured API ZIP exports; no model calls/replay','expected':'Every captured named hash/ref resolves; terminal negatives publish no durable node/receipt; blocked Intent dispatches zero Requirements calls','cases':results,'result':'PASS' if all(r['result']=='PASS' for r in results) else 'FAIL','limitations':['This establishes captured boundary facts, not semantic reliability. R06 omissions was a positive false refusal; R06 lost-constraint injection never ran. Positive exact node release is separately verified in v06-release-independent.json.']}
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'result':report['result'],'cases':results},ensure_ascii=False))
raise SystemExit(0 if report['result']=='PASS' else 1)
