"""Read-only supported-environment availability observations; no account calls."""
from pathlib import Path
import json
import shutil
import subprocess

ROOT=Path(r'D:\research\ai_for_research\jiuwenswarm')
OUT=ROOT/'docs/code/Missions/M0/M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3'
standard=[Path(r'C:\Program Files\Docker\Docker\resources\bin\docker.exe'),Path(r'C:\ProgramData\DockerDesktop\version-bin\docker.exe')]
observed={'docker_on_path':shutil.which('docker'),'inspected_standard_paths':[{'path':str(path),'exists':path.is_file()} for path in standard],'commands':[]}
for name in ('docker','python3'):
    command=['wsl','-d','Ubuntu','--','sh','-lc',f'command -v {name}']
    result=subprocess.run(command,capture_output=True,timeout=30)
    observed['commands'].append({'command':command,'exit_code':result.returncode,'stdout':result.stdout.decode('utf-8',errors='replace'),'stderr':result.stderr.decode('utf-8',errors='replace')})
observed['scope']='Actual CLI availability only; no installation, container build, login or provider request.'
path=OUT/'environment-availability.json'
assert not path.exists()
path.write_text(json.dumps(observed,indent=2)+'\n',encoding='utf-8')
print(json.dumps(observed))
