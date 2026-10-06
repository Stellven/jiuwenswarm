"""Capture actual local checks for the bounded source candidate without secrets."""
from pathlib import Path
import hashlib
import importlib.metadata as metadata
import json
import os
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(r'D:\research\ai_for_research\jiuwenswarm')
OUT=ROOT/'docs/code/Missions/M0/M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3'
OUT.mkdir(parents=True,exist_ok=True)
PY=ROOT/'.venv/Scripts/python.exe'

def digest(content): return hashlib.sha256(content).hexdigest()
def installed(key):
    try: return metadata.version(key)
    except metadata.PackageNotFoundError: return 'Installed distribution metadata unavailable; no version inferred.'
def save(name,value): (OUT/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
def run(name,args,expected=0):
    completed=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (OUT/(name+'.stdout.txt')).write_text(completed.stdout,encoding='utf-8')
    (OUT/(name+'.stderr.txt')).write_text(completed.stderr,encoding='utf-8')
    result={'command':args,'working_directory':str(ROOT),'exit_code':completed.returncode,'expected_exit':expected,'result':'PASS' if completed.returncode==expected else 'FAIL'}
    save(name+'.run.json',result)
    print(json.dumps({'stage':name,**result}),flush=True)
    return completed

files=set()
for folder in ('jiuwenswarm/ai4research','tests/unit_tests/ai4research','tests/integration_tests/ai4research','tests/journeys/ai4research','tests/fixtures/ai4research','deploy/intent-trial','jiuwenswarm/channels/web/frontend/src/features/intentTrial','jiuwenswarm/channels/web/frontend/dist','jiuwenswarm/server/runtime/codex_subscription'):
    for path in (ROOT/folder).rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix not in {'.pyc','.pyo'}:
            files.add(path.relative_to(ROOT).as_posix())
for name in ('pyproject.toml','.gitattributes','.gitignore','.dockerignore','jiuwenswarm/__init__.py','tests/conftest.py','pytest.ini','jiuwenswarm/channels/web/frontend/package.json','jiuwenswarm/channels/web/frontend/package-lock.json','jiuwenswarm/channels/web/frontend/src/main.tsx','jiuwenswarm/channels/web/frontend/src/i18n/locales/en.json','jiuwenswarm/channels/web/frontend/src/i18n/locales/zh.json'):
    if (ROOT/name).is_file(): files.add(name)
def inventory(): return [{'path':name,'sha256':digest((ROOT/name).read_bytes()),'bytes':(ROOT/name).stat().st_size} for name in sorted(files)]
before=inventory()
diff=subprocess.run(['git','diff','--binary','HEAD'],cwd=ROOT,capture_output=True).stdout
(OUT/'tracked.diff').write_bytes(diff)
manifest={'scope':'TRIAL-1 exact execution inputs; local infrastructure and explicit model fixtures only',
          'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'tracked_diff_sha256':digest(diff),'files':before,'snapshot_sha256':digest(json.dumps(before,sort_keys=True,separators=(',',':')).encode()),
          'python':sys.version,'platform':platform.platform(),'dependencies':{key:installed(key) for key in ('pytest','pytest-asyncio','fastapi','uvicorn','pydantic','openai-codex-cli-bin','setuptools','wheel')}}
save('candidate.json',manifest)
result=run('pytest',[str(PY),'-m','pytest','-o','addopts=','tests/unit_tests/ai4research','tests/integration_tests/ai4research','tests/journeys/ai4research/test_intent_trial_system.py','--basetemp','.codex-tmp/runtime-local-3','-o','cache_dir=.codex-tmp/cache-runtime-local-3','--junitxml',str(OUT/'pytest.xml'),'-q','--tb=short'])
cases=list(ET.parse(OUT/'pytest.xml').getroot().iter('testcase'))
observations=[{'case':case.get('classname')+'::'+case.get('name'),'seconds':float(case.get('time','0')),'result':'FAIL' if any(case.find(tag) is not None for tag in ('error','failure')) else 'SKIPPED' if case.find('skipped') is not None else 'PASS'} for case in cases]
save('pytest-cases.json',{'collected':len(cases),'passed':sum(c['result']=='PASS' for c in observations),'failed':sum(c['result']=='FAIL' for c in observations),'skipped':sum(c['result']=='SKIPPED' for c in observations),'observations':observations})
print(json.dumps({'stage':'pytest-outcomes','collected':len(cases),'passed':sum(c['result']=='PASS' for c in observations),'failed':sum(c['result']=='FAIL' for c in observations),'skipped':sum(c['result']=='SKIPPED' for c in observations)}),flush=True)
if result.returncode or not cases or any(c['result']!='PASS' for c in observations): raise SystemExit(1)
run('wheel',[str(PY),'-c',"from setuptools.build_meta import build_wheel; print(build_wheel('.codex-tmp/intent-wheel-final-3'))"])
wheel=next((ROOT/'.codex-tmp/intent-wheel-final-3').glob('*.whl'))
with zipfile.ZipFile(wheel) as archive:
    expected=[name for name in sorted(files) if name.startswith('jiuwenswarm/ai4research/')]
    compared=[]
    for name in expected:
        data=archive.read(name)
        assert data==(ROOT/name).read_bytes(),name
        compared.append({'path':name,'sha256':digest(data)})
    entrypoint=next(name for name in archive.namelist() if name.endswith('.dist-info/entry_points.txt'))
    scripts=archive.read(entrypoint).decode()
    assert 'ai4research-intent-client = jiuwenswarm.ai4research.headless:main' in scripts
    assert 'ai4research-intent-trial = jiuwenswarm.ai4research.service:main' in scripts
save('wheel-validation.json',{'result':'PASS','wheel':str(wheel.relative_to(ROOT)),'sha256':digest(wheel.read_bytes()),'compared_trial_files':compared,'entrypoints_verified':['ai4research-intent-client','ai4research-intent-trial'],'limitations':'Wheel resource/byte check only; no Docker or real model acceptance.'})
after=inventory()
save('candidate-comparison.json',{'unchanged':before==after,'changes':[name for name in sorted(files) if next(f for f in before if f['path']==name)!=next(f for f in after if f['path']==name)]})
assert before==after,'Execution inputs changed while observing the candidate.'
print(json.dumps({'stage':'final','result':'PASS','execution_inputs':len(before),'snapshot_sha256':manifest['snapshot_sha256'],'wheel_files':len(expected)}),flush=True)
