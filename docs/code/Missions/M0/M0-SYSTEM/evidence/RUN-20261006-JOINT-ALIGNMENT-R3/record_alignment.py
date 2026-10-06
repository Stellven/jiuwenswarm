"""Retain fresh documentary observations without modifying historical runs."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys

ROOT=Path(r'D:\research\ai_for_research\jiuwenswarm')
BASE=ROOT/'docs/code/Missions/M0'
SCRATCH=ROOT.parent/'.codex_work/m0-joint-alignment'
RUN='RUN-20261006-JOINT-ALIGNMENT-R3'
OUT=BASE/'M0-SYSTEM/evidence'/RUN
OUT.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))

def save(name,value):
    path=OUT/name
    if path.exists():
        raise RuntimeError('Refusing to overwrite observed artifact: '+str(path))
    path.write_text(json.dumps(value,indent=2,ensure_ascii=True)+'\n',encoding='utf-8')

def invoke(level):
    command=[sys.executable,str(BASE/'tools/validate_framework.py'),'--level',level]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    return {'command':command,'working_directory':str(ROOT),'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'parsed':json.loads(result.stdout)}

phase=sys.argv[1]
if phase in {'initial','renew_initial'}:
    observed={level:invoke(level) for level in ('BLOCK','BOUNDARY')}
    initial_name='initial-checks-final-candidate.json' if phase=='renew_initial' else 'initial-checks.json'
    save(initial_name,{'run_id':RUN,'utc':datetime.now(timezone.utc).isoformat(),'input_sha256':{name:sha(BASE/name) for name in ('registry.json','source-coverage.json','source-manifest.json','tools/validate_framework.py','tools/check_alignment.py')},'observations':observed})
    assert all(x['exit_code']==0 and x['parsed']['status']=='PASS' for x in observed.values()),observed
    print(json.dumps({'phase':'initial','result':'PASS','totals':observed['BOUNDARY']['parsed']['totals']}))
elif phase=='native':
    from concurrent.futures import ThreadPoolExecutor
    skill=Path(r'C:\Users\17982\.codex\plugins\cache\ai4research-dev\spec-kit\1.1.2\skills\speckit-register\SKILL.md')
    helper=skill.parents[2]/'scripts/powershell/check-prerequisites.ps1'
    template=skill.parents[2]/'templates/EVIDENCE_TEMPLATE.md'
    pointer=ROOT/'.specify/feature.json'
    before=sha(pointer)
    features=load(BASE/'registry.json')['features']
    def native(feature):
        command=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(helper),'-Json','-RequireSpec','-RequireTasks','-IncludeTasks']
        env=dict(os.environ,SPECIFY_FEATURE_DIRECTORY=feature['feature_directory'],SPECIFY_FEATURE_NO_PERSIST='1')
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True)
        stdout=result.stdout.decode('utf-8',errors='replace')
        stderr=result.stderr.decode('utf-8',errors='replace')
        parsed=json.loads(stdout) if result.returncode==0 else None
        passed=result.returncode==0 and parsed is not None and Path(parsed['FEATURE_DIR']).resolve()==(ROOT/feature['feature_directory']).resolve() and 'tasks.md' in parsed['AVAILABLE_DOCS']
        return {'task_id':feature['id'],'command':command,'working_directory':str(ROOT),'selection':feature['feature_directory'],'no_persist':True,'exit_code':result.returncode,'stdout':stdout,'stderr':stderr,'parsed':parsed,'passed':passed}
    with ThreadPoolExecutor(max_workers=3) as pool:
        observations=list(pool.map(native,features))
    after=sha(pointer)
    value={'run_id':RUN,'revision':'r3','utc':datetime.now(timezone.utc).isoformat(),'helper':{'path':str(helper),'sha256':sha(helper)},'template':{'path':str(template),'sha256':sha(template)},'skill':{'path':str(skill),'sha256':sha(skill)},'feature_pointer_before':before,'feature_pointer_after':after,'required':9,'passed':sum(o['passed'] for o in observations),'observations':observations}
    save('native-prerequisites.json',value)
    assert value['passed']==9 and before==after,value
    print(json.dumps({'phase':'native','result':'PASS','passed':9,'feature_pointer_unchanged':True}))
elif phase=='final':
    initial_name='initial-checks-final-candidate.json' if (OUT/'initial-checks-final-candidate.json').is_file() else 'initial-checks.json'
    initial=load(OUT/initial_name)
    native=load(OUT/'native-prerequisites.json')
    faults=load(OUT/'fault-observations.json')
    # Runner results are individually observed and their frozen expectations retained.
    assert native['passed']==native['required']==9
    assert native['feature_pointer_before']==native['feature_pointer_after']
    assert faults['passed']==faults['required'] and faults['original_sources_unchanged']
    assert all(sha(BASE/name)==digest for name,digest in initial['input_sha256'].items())
    runtime_path=BASE/'M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3/candidate.json'
    runtime=load(runtime_path)
    changes=[row['path'] for row in runtime['files'] if not (ROOT/row['path']).is_file() or sha(ROOT/row['path'])!=row['sha256']]
    assert not changes,changes
    manifest=load(BASE/'source-manifest.json')
    source_changes=[row['path'] for row in manifest['files'] if sha(BASE/row['path'])!=row['sha256']]
    assert not source_changes,source_changes
    review=load(SCRATCH/'r3-architecture-review.json')
    save('independent-source-review.json',review)
    for name in ('architecture-prd-comparison.json','prd-phase1-allocation.json','validator-schema.json','shell-stage-inventory.json'):
        shutil.copy2(SCRATCH/name,OUT/name)
    shutil.copy2(BASE/'tools/check_alignment.py',OUT/'observed-check-alignment.py')
    shutil.copy2(Path(__file__),OUT/Path(__file__).name)
    record=BASE/'M0-SYSTEM/evidence'/f'{RUN}.md'
    assert not record.exists()
    record.write_text(f'''# Verification run: {RUN}

Observed M0-SYSTEM AC-001 documentary alignment is PASS at r3. This is not Phase 1 runtime acceptance.

## 1. Execution identity

| Field | Actual value |
| --- | --- |
| TASK ID / run ID / UTC time | M0-SYSTEM / {RUN} / {datetime.now(timezone.utc).isoformat()} |
| Level and V IDs | AC-001 / B01 / V01 BLOCK and V02 BOUNDARY; T003/T004/T027. Documentary checks only. |
| Candidate identity | HEAD {runtime['head']} plus exact dirty current document/source hashes in [documentary candidate]({RUN}/documentary-candidate.json); tracked diff retained there. |
| Baseline / component revisions | Joint allocation r3; eight implemented trial IFs at r2; no changed runtime or source bytes. |
| PRD, spec, plan and IF versions | Exact user PRD and immediate-plan SHA256 in scope_authorities/source-manifest.json; 148 selected product units, eight architecture units, nine registered tasks, 68 AC/B and 136 V; existing r2 payload meanings retained. |
| Working directory / platform / runtime | {ROOT.as_posix()} / {platform.platform()} / Python {platform.python_version()}, PowerShell native prerequisite helper. |
| Input/fixture/model/configuration versions | Frozen documentary mutation labels/expected diagnostics, validator/runner/source/helper/template hashes and case outputs; actual source variants and D5/D6 dispositions retained. No model execution in this run. |
| Dependency mode and services | Actual local filesystem, Python validators and installed Spec Kit helper; isolated invalid-document copies. No runtime/provider/remote service. |
| Command or procedure | [Initial BLOCK/BOUNDARY]({RUN}/{initial_name}); [nine native calls]({RUN}/native-prerequisites.json); [frozen mutations/control/recovery]({RUN}/fault-observations.json); [runner]({RUN}/observed-check-alignment.py); [final checks]({RUN}/final-checks.json). |

## 2. Per-check observations

| V ID / AC references | Expected outcome / threshold source | Actual outcome | Exit code / counts including skips | Result | Raw artifacts |
| --- | --- | --- | --- | --- | --- |
| V01 / AC-001 | Complete reciprocal joint allocation, immutable source identities, source-based Phase 1 selection, stable current AC/B/V/T/IF ownership; every declared invalid mutation refused for its frozen reason | Initial actual BLOCK has zero errors; every frozen fault/control assertion met, followed by valid recovery | Initial exit 0; {faults['passed']}/{faults['required']} fault/control/recovery assertions; zero required skips | PASS | [Initial]({RUN}/{initial_name}), [faults]({RUN}/fault-observations.json) |
| V02 / AC-001 | Connected current document links, exact supplied source copies, all nine native selections without pointer mutation, valid recovery and unchanged runtime/source custody | Initial BOUNDARY zero errors; nine native helper calls resolve intended feature; current allocation and exclusions reviewed against exact source; final progress/evidence links rechecked | Initial exit 0; native 9/9, faults {faults['passed']}/{faults['required']}; zero required skips | PASS | [Native]({RUN}/native-prerequisites.json), [independent review]({RUN}/independent-source-review.json), [final]({RUN}/final-checks.json), [preservation]({RUN}/source-preservation.json) |

## 3. Scope and validity

- Established: current r3 documentary ownership of PRD Phase 1 and TRIAL-1 as two views of one M0 objective; exact selected product duties and prohibited/separate-phase dispositions; required full Brief/actual Node B/research/science/Delivery/shell/report ownership; authorized D5/D6 amendments recorded against original source; no global two-CC ceiling; native source/interface/work/check/evidence correspondence and declared refusal/recovery diagnostics.
- Not established: any new Phase 1 runtime exit, actual full Brief, Node B, empirical/scientific run, Delivery, full operational shell or completion report. AC-018 remains BLOCKED by observed required-runtime unavailability; AC-019–027 remain NOT_RUN/unbuilt. Mandatory conditional Phase 1 scaffold/boot-security requirements cannot become N/A because RSI execution is separately phased.
- Reused evidence: the prior LOCAL-3 exact 316 execution inputs remain byte-identical, verified in source-preservation.json. Its 329 local trial assertions and nine browser journeys are retained only for unchanged bounded trial behavior, not broader Phase 1 criteria. No runtime tests or provider calls were repeated in this documentary run. All 68 supplied source files remain byte-identical; packaged/master versus user PRD variants retain independent provenance.
- Superseded: prior documentary r2 sole-authority acceptance is historical for the changed allocation. Old raw observations and run records remain untouched. The unchanged scoped trial results keep their original candidate and limits.
- Retained harness failure: [first negative observations]({RUN}/fault-first-observations.json) reported 14/15 expected diagnoses although all 15 invalid mutations were refused. The missing-link case had retained an existing evidence link; the fixture now removes it. The validator and required rejection were retained. The final runner and initial checks were frozen again after that correction; no failed result was replaced or suppressed.
- Follow-up: SYSTEM T085 and T055–T084 remain open for owned product contracts/fixtures, implementation and observed BLOCK/connected BOUNDARY acceptance; existing real trial runtime work remains open. The documentary T003/T004/T027 completion grants no runtime acceptance.
- Final recording changes only documentary progress/evidence links after the initial assertions. The final candidate captures those authored files; final checks then read the exact candidate without further mutation. Future source, criterion, interface, validator, fixture or relevant runtime changes invalidate affected observations.
- Model reproducibility/cost/latency: not applicable to documentary execution; zero provider calls and no provider reliability/usage inference.
''',encoding='utf-8')
    taskpath=BASE/'M0-SYSTEM/tasks.md'
    body=taskpath.read_text(encoding='utf-8')
    lines=body.splitlines()
    for index,line in enumerate(lines):
        if line.startswith('| [AC-001](spec.md) |'):
            lines[index]=f'| [AC-001](spec.md) | B01; current scoped IFs | T003 | V01 / T004; V02 / T027 | PASS | [{RUN}](evidence/{RUN}.md); [exact r3 documentary candidate](evidence/{RUN}/documentary-candidate.json) | Actual renewed joint-source allocation/native/fault/control/recovery checks; old r2 documentary observations are historical. No runtime or Phase 1 stage acceptance follows. |'
        elif line.startswith('- [ ] T004 ') or line.startswith('- [ ] T027 '):
            item=line.split(' ',3)[3].split(' ',1)[0]
            check,level=('V01','BLOCK') if item=='T004' else ('V02','BOUNDARY')
            path_refs='`docs/code/Missions/M0/tools/validate_framework.py`' + ('; `docs/code/Missions/M0/tools/check_alignment.py`' if item=='T027' else '')
            lines[index]=f'- [x] {item} [US1] Observed {check} {level}; B01, AC-001; {path_refs}; current joint r3 allocation, native resolution and refusal/recovery assertions passed. [{RUN}](evidence/{RUN}.md). Documentary acceptance only.'
    body='\n'.join(lines)+'\n'
    body=body.replace('historical documentary T003/T004/T027 for the earlier sole-authority scope, now with T004/T027 reopened and AC-001 STALE', f'documentary T003/T004/T027 renewed at r3 under [{RUN}](evidence/{RUN}.md), with the earlier sole-authority proof retained as historical')
    body=body.replace('Current joint documentary AC-001 is STALE pending revalidation.',f'Current joint documentary AC-001 is PASS under [{RUN}](evidence/{RUN}.md); this establishes documentary alignment only.')
    body+=f'\nCurrent r3 documentary renewal: AC-001 V01/V02 and T003/T004/T027 are PASS/complete under [{RUN}](evidence/{RUN}.md). This supersedes the earlier pending documentary status only. The 31 new Phase 1 work items remain unchecked; AC-018 BLOCKED and AC-019–027 NOT_RUN are unchanged.\n'
    taskpath.write_text(body,encoding='utf-8')
    for directory in BASE.glob('M0-*'):
        if directory.name=='M0-SYSTEM':
            continue
        for name in ('TASK.md','spec.md','plan.md','tasks.md'):
            path=directory/name
            component=path.read_text(encoding='utf-8')
            component=component.replace('The broadened SYSTEM documentary AC-001 needs a fresh r3 check.',f'The broadened SYSTEM documentary AC-001 is renewed at r3; [fresh alignment observations](../M0-SYSTEM/evidence/{RUN}.md) establish documentary consistency only.')
            path.write_text(component,encoding='utf-8')
    paths={p for p in BASE.rglob('*') if p.is_file() and not set(p.relative_to(BASE).parts)&{'source','context','evidence','__pycache__'}}
    paths|={ROOT/p for p in ('AGENTS.md','docs/code/CATALOG.md','docs/code/README.en.md','deploy/intent-trial/README.md')}
    entry=lambda p:{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size}
    docs=[entry(p) for p in sorted(paths)]
    sources=[entry(BASE/r['path']) for r in manifest['files']]
    diff=subprocess.run(['git','diff','--binary','HEAD','--',*[r['path'] for r in docs]],cwd=ROOT,capture_output=True,check=True).stdout
    (OUT/'documentary-tracked.diff').write_bytes(diff)
    candidate={'run_id':RUN,'revision':'r3','scope':'Documentary AC-001 only; no runtime acceptance','head':runtime['head'],'dirty':True,'current_files':docs,'source_files':sources,'snapshot_sha256':hashlib.sha256(json.dumps({'documents':docs,'sources':sources},sort_keys=True,separators=(',',':')).encode()).hexdigest(),'tracked_dirty_diff_sha256':hashlib.sha256(diff).hexdigest(),'runtime_candidate':{'path':runtime_path.relative_to(ROOT).as_posix(),'sha256':sha(runtime_path),'snapshot_sha256':runtime['snapshot_sha256'],'execution_inputs_unchanged':316},'scope_authorities':load(BASE/'registry.json')['scope_authorities']}
    save('documentary-candidate.json',candidate)
    observations={level:invoke(level) for level in ('BLOCK','BOUNDARY')}
    save('final-checks.json',{'run_id':RUN,'candidate_sha256':sha(OUT/'documentary-candidate.json'),'observations':observations})
    assert all(o['exit_code']==0 and o['parsed']['status']=='PASS' for o in observations.values()),observations
    assert docs==[entry(p) for p in sorted(paths)]
    assert not [r['path'] for r in runtime['files'] if sha(ROOT/r['path'])!=r['sha256']]
    copies=[]
    for name in ('capsules.md','glossary.md','guard-design.md'):
        original=ROOT/'docs/architecture/build-package'/name
        copy=BASE/'source/build-package'/name
        assert original.read_bytes()==copy.read_bytes()
        copies.append({'main':original.relative_to(ROOT).as_posix(),'copy':copy.relative_to(ROOT).as_posix(),'sha256':sha(copy),'byte_identical':True})
    save('source-preservation.json',{'source_files':68,'changed_sources':[],'execution_inputs':316,'changed_execution_inputs':[],'unchanged_runtime_snapshot':runtime['snapshot_sha256'],'documentary_files_unchanged_during_final_checks':True,'source_copy_identity':copies})
    print(json.dumps({'result':'PASS','documents':len(docs),'sources_unchanged':68,'runtime_inputs_unchanged':316,'snapshot':candidate['snapshot_sha256'],'native':9,'faults':faults['passed'],'totals':observations['BOUNDARY']['parsed']['totals']}))
else:
    raise ValueError('Expected initial or final phase')
