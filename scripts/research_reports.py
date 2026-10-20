"""Derive status from native matrices and current hash-bound raw evidence.

Reports are views, never new acceptance or work authorities. Core population:
M1-SYSTEM plan B02/B03/B04 and V01-V06,V08,V09,V15, with their exact required
child evidence (PRD1.5/6.3-6.10; system spec AC001-006/008-009/015).
Phase2/3 and QA remain separate under system FR008/012/014 and AC012/014.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from datetime import datetime,timezone
import xml.etree.ElementTree as ET


REPORT_NAMES=('phase_1_completion_report.md','phase_2_completion_report.md','phase_3_completion_report.md','m1_implementation_report.md','m1_final_test_report.md')
ID=re.compile(r'M1-(?:\d{3}|QA|SYSTEM)/(?:AC-\d{3}|V\d{2}|T\d{3})')
CORE=tuple(f'M1-SYSTEM/V{i:02}' for i in (1,2,3,4,5,6,8,9,15))
OUTCOMES={'PASS','FAIL','BLOCKED','NOT_RUN','STALE','N/A'}


def sha(data):return hashlib.sha256(data).hexdigest()


def _cells(line):
    return [x.strip() for x in re.split(r'(?<!\\)\|',line.strip().strip('|'))]


def interface_index(register, required):
    revisions={};owners={};diagnostics=[]
    for line in register.splitlines():
        match=re.match(r'^\|\s*(M1-IF-\d{3})\s*/\s*(r\d+)\s*\|',line)
        if match:
            cells=_cells(line)
            if len(cells)!=5:
                diagnostics.append('Malformed interface definition '+match[1]);continue
            if match[1] in revisions:diagnostics.append('Duplicate interface definition '+match[1])
            revisions[match[1]]=match[2];owners[match[1]]=cells[2]
    for identity in sorted(required):
        if identity not in revisions:diagnostics.append('Canonical interface missing from TASKS: '+identity)
    return revisions,owners,diagnostics


def parse_native(feature):
    feature=Path(feature);texts={name:(feature/name).read_text(encoding='utf-8-sig') for name in ('spec.md','plan.md','tasks.md')}
    acs={};checks={};matrix={};check_matrix={};work={};diagnostics=[]
    for line in texts['spec.md'].splitlines():
        if line.startswith('|'):
            c=_cells(line);found=re.search(r'M1-(?:\d{3}|QA|SYSTEM)/AC-\d{3}',c[0])
            if found:
                if found[0] in acs:diagnostics.append('Duplicate spec AC '+found[0])
                acs[found[0]]={'id':found[0],'source_row':line,'required_checks':[]}
    for line in texts['plan.md'].splitlines():
        if line.startswith('|'):
            c=_cells(line);found=re.search(r'M1-(?:\d{3}|QA|SYSTEM)/V\d{2}',c[0])
            if found:
                if len(c)<7 or c[1] not in {'BLOCK','BOUNDARY','SYSTEM'}:diagnostics.append('Malformed plan V '+found[0]);continue
                checks[found[0]]={'id':found[0],'level':c[1],'source_row':line,'procedure_sha256':sha(line.encode()),'command':c[5],
                    'expected_outcome':c[4],
                    'required_checks':sorted(set(re.findall(r'M1-(?:\d{3}|QA|SYSTEM)/V\d{2}',c[6])))}
    section=None
    for line in texts['tasks.md'].splitlines():
        match=re.match(r'- \[([ xX])\]\s+(M1-(?:\d{3}|QA|SYSTEM)/T\d{3})\b',line)
        if match:work[match[2]]=match[1].lower()=='x'
        if not line.startswith('|'):continue
        c=_cells(line)
        if c[0].startswith('AC ID'):section='ac';continue
        if c[0].startswith('V ID'):section='v';continue
        found=ID.search(c[0])
        if not found:continue
        if section=='ac' and '/AC-' in found[0]:
            if len(c)!=7:diagnostics.append('Malformed AC matrix '+found[0]);continue
            matrix[found[0]]={'required_checks':sorted(set(re.findall(r'M1-(?:\d{3}|QA|SYSTEM)/V\d{2}',c[3]))),'claimed_status':c[4],'evidence':c[5]}
        elif section=='v' and '/V' in found[0]:
            if len(c)!=5:diagnostics.append('Malformed V matrix '+found[0]);continue
            check_matrix[found[0]]={'claimed_status':c[2],'evidence':c[3]}
    for key,ac in acs.items():
        if key not in matrix:diagnostics.append('Missing AC matrix row '+key)
        else:ac.update(matrix[key])
        if not ac['required_checks']:diagnostics.append('AC has no required V '+key)
        for ref in ac['required_checks']:
            if ref not in checks:diagnostics.append('AC refers to missing plan V '+ref)
    for key,check in checks.items():
        check.update(check_matrix.get(key,{'claimed_status':'NOT_RUN','evidence':''}))
        if key not in check_matrix:diagnostics.append('Missing V matrix row '+key)
    for key in matrix.keys()-acs.keys():diagnostics.append('Orphan AC matrix row '+key)
    for key in check_matrix.keys()-checks.keys():diagnostics.append('Orphan V matrix row '+key)
    native_pins={feature.name+'/'+name:sha((feature/name).read_bytes()) for name in ('spec.md','plan.md')}
    if (feature/'TASK.md').is_file():native_pins[feature.name+'/TASK.md']=sha((feature/'TASK.md').read_bytes())
    else:diagnostics.append('Missing owning TASK '+feature.name)
    return {'feature':feature.name,'acs':acs,'checks':checks,'work':work,'diagnostics':diagnostics,'native_pins':native_pins}


def _confined(root,name):
    root=Path(root).resolve(strict=True);relative=Path(name)
    if relative.is_absolute() or '..' in relative.parts or '\\' in name:raise ValueError('evidence path escapes root')
    if any(p in {'private','protected','codex-home'} for p in relative.parts) or relative.name in {'auth.json','credentials.json','secrets.json'} or relative.suffix.lower() in {'.key','.pem','.p12','.pfx'}:raise ValueError('protected credential/scoring path is not report input')
    path=root/relative
    for item in [path,*path.parents]:
        if item==root:break
        if item.is_symlink():raise ValueError('evidence symlink denied')
    if not path.resolve(strict=True).is_relative_to(root) or not path.is_file():raise ValueError('evidence outside root')
    return path


def _artifact(root,row):
    path=_confined(root,row['path'])
    if path.stat().st_size>128*1024*1024:raise ValueError('evidence exceeds bounded reader policy')
    raw=path.read_bytes()
    if sha(raw)!=row['sha256']:raise ValueError('evidence artifact digest mismatch')
    return raw


def validate_receipt(receipt,*,check,root,candidate_id,source_sha,interfaces,native_pins):
    reasons=[];claimed=receipt.get('outcome','NOT_RUN')
    result={'status':claimed if claimed in OUTCOMES else 'NOT_RUN','reasons':reasons,'receipt':receipt.get('check_id')}
    if claimed!='PASS':
        if not receipt.get('reason'):reasons.append('Nonpassing outcome lacks an explicit reason.')
        return result
    expected={'schema':'m1-verification-result:1','check_id':check['id'],'candidate_id':candidate_id,
        'source_baseline_sha256':source_sha,'procedure_sha256':check['procedure_sha256']}
    for key,value in expected.items():
        if value is None or receipt.get(key)!=value:reasons.append('Missing or mismatched '+key)
    if receipt.get('interface_revisions')!=interfaces:reasons.append('Interface revisions differ from canonical program pins.')
    if any(receipt.get('native_pins',{}).get(k)!=v for k,v in native_pins.items()):reasons.append('Spec/plan pins are absent or stale.')
    if not receipt.get('command') or not receipt.get('cwd') or not receipt.get('started_at') or not receipt.get('ended_at'):reasons.append('Exact command/cwd/start/end missing.')
    else:
        try:
            start=datetime.fromisoformat(receipt['started_at'].replace('Z','+00:00'));end=datetime.fromisoformat(receipt['ended_at'].replace('Z','+00:00'))
            if start.tzinfo is None or end.tzinfo is None or end<start:raise ValueError('invalid execution time')
        except (ValueError,TypeError):reasons.append('Execution timestamps are invalid.')
    environment=receipt.get('environment',{})
    if not environment.get('platform') or not re.fullmatch(r'sha256:[a-f0-9]{64}',environment.get('image_digest','')):reasons.append('Actual image/platform identity unavailable.')
    artifacts=receipt.get('artifacts',[]);junit=[];assertion_manifest=None;raw_evidence=False
    try:
        for row in artifacts:
            raw=_artifact(root,row)
            if row['kind']=='junit':junit.append(raw)
            if row['kind']=='raw' and raw:raw_evidence=True
            if row['kind']=='assertion_manifest':
                if assertion_manifest is not None:raise ValueError('multiple assertion manifests')
                assertion_manifest=json.loads(raw)
                if receipt.get('fixture_pins',{}).get(assertion_manifest['id'])!=row['sha256']:raise ValueError('assertion manifest lacks frozen fixture pin')
        if not junit or not any(r['kind'] in {'stdout','stderr'} for r in artifacts):raise ValueError('raw JUnit or command output absent')
        cases=[]
        for raw in junit:
            doc=ET.fromstring(raw)
            for suite in doc.iter():
                if suite.tag in {'testsuite','testsuites'} and any(int(suite.get(k,'0')) for k in ('skipped','failures','errors')):raise ValueError('nonpassing JUnit aggregate')
            cases.extend(doc.iter('testcase'))
        if not cases or any(c.find(k) is not None for c in cases for k in ('skipped','failure','error')):raise ValueError('JUnit has zero cases or skipped/failed/error cases')
        if assertion_manifest is None:raise ValueError('independent frozen assertion manifest absent')
        if assertion_manifest['check_id']!=check['id'] or assertion_manifest['procedure_sha256']!=check['procedure_sha256']:raise ValueError('assertion manifest procedure mismatch')
        allowed={'BLOCK':{'local_real','fixture'},'BOUNDARY':{'real_boundary','external_real'},'SYSTEM':{'real_system'}}[check['level']]
        mode=assertion_manifest['required_dependency_mode']
        if mode not in allowed or receipt.get('dependency_mode')!=mode:raise ValueError('required real dependency mode was not executed')
        if check['level']!='BLOCK' and not raw_evidence:raise ValueError('connected check has no raw runtime evidence')
        required=assertion_manifest['required_assertion_ids'];actual=receipt.get('assertions',{})
        if not required or len(required)!=len(set(required)) or actual.get('required_ids')!=required or set(actual.get('passed_ids',[]))!=set(required) or len(actual.get('passed_ids',[]))!=len(required):raise ValueError('not every independent required assertion passed')
        if actual.get('expected')!=len(required) or actual.get('observed')!=len(required):raise ValueError('assertion population differs from frozen requirements')
        required_cases=assertion_manifest['required_case_ids']
        observed_cases={c.get('classname','')+'::'+c.get('name','') for c in cases}
        if len(observed_cases)!=len(cases):raise ValueError('duplicate/rerun JUnit case identities')
        if not required_cases or not set(required_cases)<=observed_cases:raise ValueError('required test cases missing from raw JUnit')
        if not receipt.get('profile_pins') or not receipt.get('fixture_pins'):raise ValueError('fixture/profile pins unavailable')
    except (ValueError,KeyError,TypeError,OSError,ET.ParseError):reasons.append('Raw evidence, required assertions or dependency mode failed verification.')
    if reasons:result['status']='STALE' if any('stale' in x.lower() or 'mismatch' in x.lower() for x in reasons) else 'INCOMPLETE'
    return result


def derive_ac(ac,checks):
    required=ac['required_checks'];states=[checks.get(v,{}).get('status','INCOMPLETE') for v in required]
    if not required:return {'status':'INCOMPLETE','required_checks':required}
    status='PASS' if all(s=='PASS' for s in states) else 'FAIL' if 'FAIL' in states else 'STALE' if 'STALE' in states else 'BLOCKED' if 'BLOCKED' in states else 'INCOMPLETE'
    return {'status':status,'required_checks':required}


def _all_pass(keys,checks):return bool(keys) and all(checks.get(k,{}).get('status')=='PASS' for k in keys)


def derive_conclusions(checks,acs,*,all_work_complete,core_children):
    core_complete=all(k in core_children for k in CORE) and bool(core_children.get('M1-SYSTEM/V01'))
    child_keys={key for values in core_children.values() for key in values}
    core='PASS' if core_complete and _all_pass(CORE,checks) and all(checks.get(k,{}).get('status')=='PASS' for k in child_keys) else 'INCOMPLETE'
    phase2=[v for v in checks if v.startswith('M1-008/')]
    phase3=[v for v in checks if v.startswith(('M1-005/','M1-007/'))]+['M1-SYSTEM/V07']
    conditional_acs=('M1-003/AC-007','M1-004/AC-011','M1-002/AC-006')
    phase3_complete=_all_pass(phase3,checks) and all(acs.get(key,{}).get('status')=='PASS' for key in conditional_acs)
    qa=[v for v in checks if v.startswith('M1-QA/')]+['M1-SYSTEM/V10']
    return {'core_release':core,'phase_2':'PASS' if _all_pass(phase2,checks) else 'INCOMPLETE',
        'phase_3':'PASS' if phase3_complete else 'INCOMPLETE','four_case_qa':'PASS' if _all_pass(qa,checks) else 'INCOMPLETE',
        'platform_qualification':'PASS' if checks.get('M1-SYSTEM/V11',{}).get('status')=='PASS' else 'INCOMPLETE',
        'full_requested_delivery':'PASS' if core=='PASS' and checks and acs and all_work_complete and all(x['status']=='PASS' for x in checks.values()) and all(x['status']=='PASS' for x in acs.values()) else 'INCOMPLETE'}


def source_identity(root,program):
    path=program/'source-baseline.json';raw=path.read_bytes();baseline=json.loads(raw)
    receipts=[*baseline['architecture']['files'],baseline['prd'],*baseline['qa'],baseline['invoked_prompt']]
    changed=[]
    for receipt in receipts:
        try:
            data=_confined(root,receipt['path']).read_bytes()
            if sha(data)!=receipt['sha256'] or len(data)!=receipt['bytes']:changed.append(receipt['path'])
        except (ValueError,OSError):changed.append(receipt['path'])
    return sha(raw),changed


def _receipt_path(feature,evidence):
    # An exact native link is the authority. Never choose the newest directory
    # or search all evidence for a convenient passing receipt.
    links=re.findall(r'\]\(([^)]+\.json)\)',evidence)
    if not links:
        links=re.findall(r'(?<![\w/])((?:evidence/|\.\./)[A-Za-z0-9_./:-]+\.json)\b',evidence)
    if len(links)!=1:raise ValueError('native V row must identify one exact receipt JSON file')
    relative=Path(links[0])
    program=feature.parent.resolve()
    logical=feature/relative
    for item in [logical,*logical.parents]:
        if item==program:break
        if item.is_symlink():raise ValueError('native receipt symlink denied')
    path=logical.resolve(strict=True)
    if not path.is_relative_to(program) or path.is_symlink() or not path.is_file():raise ValueError('native receipt is outside registered program')
    return path


def reconcile(program,*,root,candidate=None):
    root=Path(root).resolve();program=Path(program).resolve();register=(program/'TASKS.md').read_text(encoding='utf-8-sig')
    features=sorted(set(re.findall(r'\]\((M1-(?:\d{3}|QA|SYSTEM))/TASK\.md\)',register)))
    diagnostics=[];native={};checks={};acs={};work={};pins={};receipts={};core_children={}
    if not features:diagnostics.append('TASKS contains no registered native features.')
    for name in features:
        try:data=parse_native(program/name)
        except (ValueError,OSError):diagnostics.append('Native artifact missing or unreadable for '+name);continue
        native[name]=data;pins.update(data['native_pins']);work.update(data['work']);diagnostics.extend(data['diagnostics'])
    source_sha,changed_sources=source_identity(root,program)
    if changed_sources:diagnostics.append('Supplied source byte identity changed: '+', '.join(changed_sources))
    # Include subsequently registered private agreements consumed by native
    # definitions; the original ten interfaces are not a closed future catalog.
    required_interfaces={f'M1-IF-{i:03}' for i in range(1,11)}
    for name in native:
        for filename in ('TASK.md','spec.md','plan.md'):
            required_interfaces.update(re.findall(r'M1-IF-\d{3}',(program/name/filename).read_text(encoding='utf-8-sig')))
    interfaces,interface_owners,interface_diagnostics=interface_index(register,required_interfaces)
    diagnostics.extend(interface_diagnostics)
    candidate_id=None;candidate_changes=[]
    if candidate:
        try:
            try:from scripts.research_candidate import verify_candidate
            except ImportError:from research_candidate import verify_candidate
            candidate_id=candidate['candidate_id'];candidate_changes=verify_candidate(root,candidate)
            identity={key:candidate[key] for key in ('schema_version','base_head','scope','files')}
            if sha(json.dumps(identity,sort_keys=True,separators=(',',':')).encode())!=candidate_id:candidate_changes.append('candidate identity does not recompute')
        except (ValueError,KeyError,OSError):candidate_changes=['candidate manifest unavailable or invalid']
    for name,data in native.items():
        for key,check in data['checks'].items():
            claimed=check['claimed_status']
            result={'status':claimed if claimed in OUTCOMES and claimed!='PASS' else 'INCOMPLETE','reasons':[],'level':check['level'],'native_evidence':check['evidence']}
            if claimed=='PASS':
                try:
                    path=_receipt_path(program/name,check['evidence']);receipt=json.loads(path.read_bytes());receipts[key]=receipt
                    relevant_pins={k:v for k,v in pins.items() if k.startswith(name+'/')}
                    for interface in set(re.findall(r'M1-IF-\d{3}',check['source_row'])):
                        owner=interface_owners.get(interface);owner_key=str(owner)+'/TASK.md'
                        if owner_key in pins:relevant_pins[owner_key]=pins[owner_key]
                        else:raise ValueError('consumed interface owner definition unavailable')
                    outcome=validate_receipt(receipt,check=check,root=path.parent,candidate_id=candidate_id,source_sha=source_sha,interfaces=interfaces,native_pins=relevant_pins)
                    result.update(outcome);result['receipt_path']=str(path.relative_to(program))
                    # A receipt may narrow dependencies only through the frozen
                    # assertion/profile manifest validated above.
                    if result['status']=='PASS':
                        manifest_row=next(a for a in receipt['artifacts'] if a['kind']=='assertion_manifest')
                        manifest=json.loads(_artifact(path.parent,manifest_row))
                        children=manifest.get('required_child_checks')
                        if key in CORE and isinstance(children,list) and receipt.get('required_child_checks')==children:
                            core_children[key]=children
                except (ValueError,KeyError,OSError,StopIteration):result['reasons'].append('Exact native receipt is absent, malformed or unverified.')
            elif claimed not in OUTCOMES:result['reasons'].append('Unknown native outcome; no acceptance inferred.')
            if result['status']=='PASS' and (changed_sources or candidate_changes or data['diagnostics']):
                result['status']='STALE';result['reasons'].append('Source/candidate/native coverage changed or is incomplete.')
            checks[key]=result
    # Child results must themselves be current, mapped native V records.
    visiting=set();done=set()
    def children_current(key):
        if key in visiting:return False
        if key in done:return checks.get(key,{}).get('status')=='PASS'
        visiting.add(key);required=receipts.get(key,{}).get('required_child_checks',[])
        valid=all(child in checks and children_current(child) for child in required)
        visiting.remove(key);done.add(key)
        if checks.get(key,{}).get('status')=='PASS' and not valid:
            checks[key]['status']='INCOMPLETE';checks[key]['reasons'].append('Required child evidence is incomplete, stale or cyclic.')
        return checks.get(key,{}).get('status')=='PASS'
    for key in checks:children_current(key)
    for data in native.values():
        for key,ac in data['acs'].items():acs[key]=derive_ac(ac,checks)
    conclusions=derive_conclusions(checks,acs,all_work_complete=bool(work) and all(work.values()) and not diagnostics,core_children=core_children)
    if not candidate_id or changed_sources or candidate_changes or diagnostics:
        conclusions={key:'INCOMPLETE' for key in conclusions}
    qa_cases={}
    for module,required,task in [('capsule',['M1-QA/V04'],'M1-QA/T018'),('verifier',['M1-QA/V05','M1-QA/V06'],'M1-QA/T019'),('routing',['M1-QA/V07'],'M1-QA/T020'),('rsi',['M1-QA/V08'],'M1-QA/T021')]:
        qa_cases[module]={'implementation':'work_recorded_complete' if work.get(task) else 'incomplete_or_not_recorded',
            'execution':'PASS' if _all_pass(required,checks) else 'INCOMPLETE','required_checks':required,
            'required_assertions':{key:native.get('M1-QA',{}).get('checks',{}).get(key,{}).get('expected_outcome') for key in required},
            'assertions':{key:receipts.get(key,{}).get('assertions') for key in required},
            'evidence':[checks[key]['receipt_path'] for key in required if checks.get(key,{}).get('receipt_path')],
            'remaining_gaps':[key+': '+checks.get(key,{}).get('status','missing') for key in required if checks.get(key,{}).get('status')!='PASS']}
    components={}
    for feature in native:
        own_work=native[feature]['work'];own_checks={k:v for k,v in checks.items() if k.startswith(feature+'/')}
        boundary=[k for k,v in own_checks.items() if v['level'] in {'BOUNDARY','SYSTEM'}]
        components[feature]={'implementation_work_complete':bool(own_work) and all(own_work.values()),'work_completed':sum(own_work.values()),'work_total':len(own_work),
            'integration':'PASS' if _all_pass(boundary,checks) else 'INCOMPLETE','verification':'PASS' if own_checks and all(v['status']=='PASS' for v in own_checks.values()) else 'INCOMPLETE'}
    return {'schema':'m1-derived-status:1','candidate_id':candidate_id,'candidate_changes':candidate_changes,'source_baseline_sha256':source_sha,
        'source_changes':changed_sources,'interface_revisions':interfaces,'native_pins':pins,'conclusions':conclusions,
        'counts':{'features':len(native),'acceptance_criteria':len(acs),'checks':len(checks),'work_items':len(work),'work_completed':sum(work.values())},
        'checks':checks,'acceptance':acs,'components':components,'qa_cases':qa_cases,'diagnostics':diagnostics,'source_policy':{'core_checks':list(CORE),'conditional_phase3_acs':['M1-003/AC-007','M1-004/AC-011','M1-002/AC-006'],'authority':'M1-SYSTEM spec FR008/012/014; AC001-006/008-009/012/014/015; plan B02-B05 and matching V procedures; TASKS source/phase allocation'},
        'limitations':['Reports do not establish performance, native GB10 qualification, model identity or transfer without their actual current evidence.',
            'Development suite manifests without qualified check_id/receipt/raw requirements are never V evidence.']}


def render_report(name,status):
    title=name.removesuffix('.md').replace('_',' ').capitalize();c=status['conclusions'];counts=status['counts']
    selected={'phase_1_completion_report.md':('core_release',),'phase_2_completion_report.md':('phase_2',),
        'phase_3_completion_report.md':('phase_3',),'m1_implementation_report.md':tuple(c),'m1_final_test_report.md':tuple(c)}[name]
    lines=['# '+title,'','Derived view of TASKS/TASK/spec/plan/tasks and exact linked raw evidence. Native records remain the authorities.','',
        'Candidate: '+(status['candidate_id'] or 'unavailable; no acceptance inferred'),'',
        '| Conclusion | Current status |','| --- | --- |']
    lines.extend('| '+key+' | '+c[key]+' |' for key in selected)
    lines.extend(['',f"Registered population: {counts['features']} features; {counts['acceptance_criteria']} ACs; {counts['checks']} checks; {counts['work_completed']}/{counts['work_items']} work items checked.",'',
        'Core release requires the named Phase 1 system checks and exact current child evidence. Advanced implementation, targeted verification, platform qualification and four-case QA retain separate conclusions.','',
        '| Check | Level | Verified status | Evidence / reason |','| --- | --- | --- | --- |'])
    for key,row in sorted(status['checks'].items()):
        if name=='phase_2_completion_report.md' and not key.startswith('M1-008/'):continue
        if name=='phase_3_completion_report.md' and not key.startswith(('M1-005/','M1-007/')) and key!='M1-SYSTEM/V07':continue
        evidence=row.get('receipt_path') or '; '.join(row['reasons']) or row['native_evidence'] or 'No current raw result'
        lines.append('| '+key+' | '+row['level']+' | '+row['status']+' | '+evidence.replace('|','\\|')+' |')
    lines.extend(['','| Component | Implementation work | Integration | Verification |','| --- | --- | --- | --- |'])
    for key,row in status['components'].items():lines.append(f"| {key} | {row['work_completed']}/{row['work_total']} checked | {row['integration']} | {row['verification']} |")
    lines.extend(['','| QA case | Implementation record | Execution | Assertions / evidence / gaps |','| --- | --- | --- | --- |'])
    for key,row in status['qa_cases'].items():
        expected=['Required '+check+': '+value for check,value in row.get('required_assertions',{}).items() if value]
        observed=[check+': '+json.dumps(value,sort_keys=True) for check,value in row.get('assertions',{}).items() if value is not None]
        detail='; '.join(expected+(['Observed '+value for value in observed] or ['Assertions not executed; no current assertion receipt.'])+row['evidence']+row['remaining_gaps'])
        lines.append(f"| {key} | {row['implementation']} | {row['execution']} | {detail.replace('|',chr(92)+'|')} |")
    lines.extend(['','Diagnostics:']+['- '+x for x in status['diagnostics'] or ['No structural diagnostics; runtime status remains as shown.']])
    lines.extend(['','Limitations:']+['- '+x for x in status['limitations']])
    return '\n'.join(lines)+'\n'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--program',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--root',default='.');parser.add_argument('--candidate')
    args=parser.parse_args(argv)
    try:
        candidate=json.loads(Path(args.candidate).read_bytes()) if args.candidate else None
        status=reconcile(args.program,root=args.root,candidate=candidate)
        output=Path(args.output)
        if output.exists():raise ValueError('derived report identity already exists; choose a new evidence-run output')
        output.mkdir(parents=True)
        (output/'reconciliation.json').write_text(json.dumps(status,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
        for name in REPORT_NAMES:(output/name).write_text(render_report(name,status),encoding='utf8')
        print(json.dumps({'conclusions':status['conclusions'],'counts':status['counts'],'output':str(output)}))
        return 0 # Successful derivation is not a product acceptance command.
    except (ValueError,KeyError,OSError) as error:
        print('Report derivation failed: '+type(error).__name__,file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
