from pathlib import Path
import hashlib
import json
import os
import subprocess
import xml.etree.ElementTree as ET
root=Path(r'D:\research\ai_for_research\jiuwenswarm')
out=root/'docs/code/Missions/M0/M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3'
observations=out/'browser-observations'; observations.mkdir()
env=dict(os.environ,AI4R_FRONTEND_ARTIFACT_DIR=str(observations))
command=[str(root/'.venv/Scripts/python.exe'),'-m','pytest','-o','addopts=','tests/journeys/ai4research/test_intent_trial_frontend.py','--basetemp','.codex-tmp/runtime-native-3','-o','cache_dir=.codex-tmp/cache-runtime-native-3','--junitxml',str(out/'browser.xml'),'-q','--tb=short']
run=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
(out/'browser.stdout.txt').write_text(run.stdout,encoding='utf-8'); (out/'browser.stderr.txt').write_text(run.stderr,encoding='utf-8')
cases=list(ET.parse(out/'browser.xml').getroot().iter('testcase'))
result={'command':command,'exit_code':run.returncode,'result':'PASS' if run.returncode==0 else 'FAIL','collected':len(cases),'passed':sum(not any(c.find(t) is not None for t in ('failure','error','skipped')) for c in cases),'failed':sum(any(c.find(t) is not None for t in ('failure','error')) for c in cases),'skipped':sum(c.find('skipped') is not None for c in cases),'observations':[{'case':c.get('name'),'seconds':c.get('time')} for c in cases]}
manifest=json.loads((out/'candidate.json').read_bytes())
changed=[f['path'] for f in manifest['files'] if hashlib.sha256((root/f['path']).read_bytes()).hexdigest()!=f['sha256']]
result['candidate_unchanged']=not changed; result['changes']=changed
(out/'browser.run.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
assert run.returncode==0 and len(cases)==9 and not changed and result['skipped']==0 and result['failed']==0
