"""Record actual documentary assertions, then verify final progress links read-only."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import subprocess
import sys

ROOT=Path(r'D:\research\ai_for_research\jiuwenswarm')
BASE=ROOT/'docs/code/Missions/M0'
OUT=BASE/'M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3'
faults=json.loads((OUT/'scope-r2-fault-observations.json').read_bytes())
native=json.loads((OUT/'scope-r2-native-prerequisites.json').read_bytes())
initial=json.loads((OUT/'scope-r2-checker-initial.json').read_bytes())
assert faults['passed']==faults['required']==9 and faults['original_sources_unchanged']
assert native['passed']==native['required']==9 and native['feature_pointer_before']==native['feature_pointer_after']
assert all(observation['exit_code']==0 and observation['parsed']['status']=='PASS' for observation in initial['observations'].values())
RUN='RUN-20261006-RUNTIME-LOCAL-3-DOCS'
relative='RUN-20261006-RUNTIME-LOCAL-3'

record=BASE/'M0-SYSTEM/evidence'/f'{RUN}.md'
assert not record.exists()
record.write_text(f'''# Verification run: {RUN}

Observed current M0-SYSTEM AC-001 documentary checks are PASS. Real model/container acceptance remains independently BLOCKED.

## 1. Execution identity

| Field | Actual value |
| --- | --- |
| TASK / run / observed time | M0-SYSTEM / {RUN} / {faults['utc']} |
| Criteria | AC-001 / B01 / V01 BLOCK and V02 BOUNDARY; T003/T004/T027. Documentary acceptance only. |
| Candidate | Current exact document/source byte hashes, dirty HEAD identity and tracked diff are retained in [documentary candidate]({relative}/documentary-candidate.json). Runtime source identities are separately frozen in [runtime candidate]({relative}/candidate.json). |
| Source / interface | Sole active immediate-plan.md SHA-256 `0a7c21c2933c0be3b07e67cedaa91d2bd1706ca4382c364eb474ae616b919ec3`; nine TASK/spec/plan/tasks sets, 58 active ACs, 20 deferred ACs, 116 V, 201 work items, eight IF@r2 and exactly two authored CCs. Other supplied files remain future context. |
| Runtime / dependencies | Real local Windows filesystem, Python 3.11.3, installed Spec Kit 1.1.2 PowerShell prerequisite helper. Helper SHA-256 `{native['helper']['sha256']}`; EVIDENCE_TEMPLATE SHA-256 `{faults['template']['sha256']}`. No model/provider service invoked. |
| Working directory | D:/research/ai_for_research/jiuwenswarm |
| Fixtures / policy | Seven mutations and expected diagnostic fragments frozen before execution, plus valid baseline and unchanged recovery. The isolated seed copies the current deployment guide and exact authored package bytes needed for link/module ownership resolution; it executes no runtime/provider. |
| Commands | [Exact initial commands/stdout/stderr/exits]({relative}/scope-r2-checker-initial.json), [nine native prerequisite commands]({relative}/scope-r2-native-prerequisites.json), [each fixture command/observation]({relative}/scope-r2-fault-observations.json), [reproducible runner]({relative}/current-document-faults.py), [final progress-link checks]({relative}/documentary-final-checks.json). |

## 2. Per-check observations

| V / expected result | Actual observation | Exit / counts | Result | Raw artifacts |
| --- | --- | --- | --- | --- |
| V01: scoped English authority/source/AC-B-V-T/IF consistency; every declared invalid mutation refused | Actual initial BLOCK PASS with no errors. Seven wrong mutations matched the frozen expected diagnostic, and both valid controls passed through the BOUNDARY superset of BLOCK assertions | BLOCK 0; seven expected rejection exits 1; two control exits 0; 9/9 fixture assertions | PASS | [Initial checker]({relative}/scope-r2-checker-initial.json), [fixture observations]({relative}/scope-r2-fault-observations.json) |
| V02: current links and source-copy identity, nine native feature resolutions, refusal and recovery | Actual initial BOUNDARY PASS; nine installed helper calls resolved the exact registered feature with unchanged feature pointer. All fixture observations passed; 68 original source files remained unchanged | BOUNDARY 0; native 9/9; fixture 9/9; no required skips | PASS | [Native observations]({relative}/scope-r2-native-prerequisites.json), [fixture observations]({relative}/scope-r2-fault-observations.json), [final checks]({relative}/documentary-final-checks.json), [source preservation]({relative}/source-preservation.json) |

The invalid cases are third authored CC, extra future task, alternate active authority, missing immediate-plan allocation, changed supplied source, broken current link and unsupported PASS. The fixed expected diagnostics and actual outputs are retained individually.

## 3. Scope and validity

- Established: current scoped documentary source identities, allocation, reciprocal interfaces, requirements/blocks/checks/work mapping, future/current separation, links, installed nine-feature resolution, the seven declared refusal diagnostics and unchanged recovery.
- Not established: actual approved model fidelity, secured native IPC/container acceptance, calibrated scientific conclusions or full Stage 0/1/2/Phase 3/M1 exits. The separate runtime record attributes actual local fixture/control checks; this documentary result does not replace them or missing real checks.
- LOCAL-1 documentary preparation failure is preserved: its isolated seed omitted the newly linked deployment guide. This renewed runner supplies that exact authored guide; no original source, scope obligation, threshold or expected diagnostic was weakened. Earlier full-M1 r1 and SCOPE-R2 observations are retained, without substituting them for this current run.
- After the initial assertions, only SYSTEM AC-001 progress/evidence links and this evidence recording were completed. The final read-only BLOCK/BOUNDARY check and exact manifest cover the resulting progress records. No source, normative requirement, validator or fault definition changed after the initial observations.
- Documentary T003/T004/T027 are complete. Runtime preparation T001/T002 and local V29/T047 and V31/T050 were recorded separately; unresolved real V04/V26/V28/V30/V32/V34 and real BLOCK portions remain open.
- Model/provider calls: zero; no cost, seed, provider reliability or population inference. Future normative source/checker/fixture changes require renewed affected evidence.
''',encoding='utf-8')

taskpath=BASE/'M0-SYSTEM/tasks.md'
lines=taskpath.read_text(encoding='utf-8').splitlines()
for index,line in enumerate(lines):
    if line.startswith('| [AC-001]'):
        lines[index]='| [AC-001](spec.md) | B01; current participating IFs | T003 | V01 / T004; V02 / T027 | PASS | ['+RUN+'](evidence/'+RUN+'.md); [current documentary candidate](evidence/'+relative+'/documentary-candidate.json) | Current source/allocation/link/native/fault observations renewed; final progress/evidence links rechecked. Documentary acceptance grants no runtime acceptance. |'
taskpath.write_text('\n'.join(lines)+'\n',encoding='utf-8')
runtime_record=BASE/'M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3.md'
runtime_record.write_text(runtime_record.read_text(encoding='utf-8')+f'\n- Current documentary AC-001 is independently PASS: nine native prerequisites and nine refusal/control/recovery assertions, 68 original sources unchanged; [{RUN}]({RUN}.md). Required real runtime checks remain BLOCKED.\n',encoding='utf-8')

def sha(data): return hashlib.sha256(data).hexdigest()
def entry(path): return {'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path.read_bytes()),'bytes':path.stat().st_size}
original=json.loads((BASE/'M0-SYSTEM/evidence/scope-r2-candidate.json').read_bytes())
paths={row['path'] for row in original['current_files']}
paths.add('deploy/intent-trial/README.md')
documents=[entry(ROOT/path) for path in sorted(paths)]
sources=[entry(ROOT/row['path']) for row in original['source_files']]
assert all(current['sha256']==prior['sha256'] for current,prior in zip(sources,original['source_files']))
runtime=json.loads((OUT/'candidate.json').read_bytes())
changed_runtime=[row['path'] for row in runtime['files'] if sha((ROOT/row['path']).read_bytes())!=row['sha256']]
assert not changed_runtime
copies=[]
for name in ('capsules.md','glossary.md','guard-design.md'):
    main=ROOT/'docs/architecture/build-package'/name
    copied=BASE/'source/build-package'/name
    assert main.read_bytes()==copied.read_bytes()
    copies.append({'main':main.relative_to(ROOT).as_posix(),'copy':copied.relative_to(ROOT).as_posix(),'sha256':sha(main.read_bytes()),'byte_identical':True})
diff=subprocess.run(['git','diff','--binary','HEAD','--',*sorted(paths)],cwd=ROOT,capture_output=True,check=True).stdout
(OUT/'documentary-tracked.diff').write_bytes(diff)
candidate={'run_id':RUN,'scope':'Documentary AC-001 only; current progress links after observed assertions','utc':datetime.now(timezone.utc).isoformat(),'head':runtime['head'],'dirty':True,'current_files':documents,'source_files':sources,'snapshot_sha256':sha(json.dumps({'documents':documents,'sources':sources},sort_keys=True,separators=(',',':')).encode()),'tracked_dirty_diff_sha256':sha(diff),'runtime_candidate':{'path':'candidate.json','sha256':sha((OUT/'candidate.json').read_bytes()),'snapshot_sha256':runtime['snapshot_sha256'],'unchanged':True},'identity_policy':'Exact authored current document/guide/governance and preserved source bytes; runtime/module ownership bytes separately frozen by the unchanged runtime candidate. Context/archive and raw evidence output files are outside the documentary snapshot.'}
(OUT/'documentary-candidate.json').write_text(json.dumps(candidate,indent=2)+'\n',encoding='utf-8')
observations={}
for level in ('BLOCK','BOUNDARY'):
    command=[sys.executable,str(BASE/'tools/validate_framework.py'),'--level',level]
    observed=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    observations[level]={'command':command,'working_directory':str(ROOT),'exit_code':observed.returncode,'stdout':observed.stdout,'stderr':observed.stderr,'parsed':json.loads(observed.stdout)}
(OUT/'documentary-final-checks.json').write_text(json.dumps({'run_id':RUN,'candidate_sha256':sha((OUT/'documentary-candidate.json').read_bytes()),'observations':observations},indent=2)+'\n',encoding='utf-8')
assert all(observed['exit_code']==0 and observed['parsed']['status']=='PASS' for observed in observations.values())
assert documents==[entry(ROOT/path) for path in sorted(paths)]
assert not [row['path'] for row in runtime['files'] if sha((ROOT/row['path']).read_bytes())!=row['sha256']]
preservation={'original_source_files':len(sources),'unchanged_from_original_supplied_manifest':True,'main_architecture_clarifications_match_copies':copies,'execution_inputs':len(runtime['files']),'execution_candidate_unchanged':True,'documentary_candidate_unchanged_during_final_checks':True}
(OUT/'source-preservation.json').write_text(json.dumps(preservation,indent=2)+'\n',encoding='utf-8')
shutil.copy2(Path(__file__),OUT/Path(__file__).name)
print(json.dumps({'documentary_result':'PASS','native_prerequisites':9,'fault_control_assertions':9,'documents':len(documents),'sources_unchanged':len(sources),'snapshot':candidate['snapshot_sha256'],'execution_inputs_unchanged':len(runtime['files']),'levels':{level:observed['parsed'] for level,observed in observations.items()}},indent=2))
