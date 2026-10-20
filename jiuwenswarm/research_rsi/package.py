"""Custodian-only inactive candidate packaging; admission is independently owned."""
from pathlib import Path
import os
import uuid
import json
import copy
from .signing import verify
from .records import encoded


def build_candidate(session_result_ref,*,read_ref,put_record,resolve_body_ref,public_key,key_id,validate,qualification=None):
    """Construct the source package from exact signed evidence, without standing."""
    get=lambda pin:json.loads(read_ref(pin))
    result=get(session_result_ref);verify(result,public_key,key_id);validate('rsi-session-result',result)
    from .qualification import require_qualification
    require_qualification(qualification,'package',session_ref=result['session_ref'],candidate_ref=result.get('child_declaration_ref'))
    if result['schema_version']!='2.0.0' or result['outcome']!='QUALIFIED' or result['qualified_by']=='none' or not result['final_attempt_ref']:raise ValueError('Only current qualified evidence can be packaged')
    session=get(result['session_ref']);validate('rsi-session',session)
    target=get(session['target_profile_ref']);validate('rsi-target-profile',target)
    if result['final_attempt_ref'] not in result['attempt_refs']:raise ValueError('Final attempt is outside retained history')
    attempt=get(result['final_attempt_ref']);validate('rsi-attempt',attempt)
    if attempt['schema_version']!='2.0.0' or attempt['attempt_status']!='proposed':raise ValueError('Rejected/historical attempt cannot be packaged')
    referee=get(result['referee_evidence_ref']);verify(referee,public_key,key_id);validate('rsi-referee-evidence',referee)
    if referee['schema_version']!='2.0.0' or referee['attempt_ref']!=result['final_attempt_ref'] or referee['child_ref']!=attempt['child_ref'] or referee['parent_ref']!=target['parent_ref']:raise ValueError('Final comparison identities differ')
    parent=get(session['parent_declaration_ref']);child=get(result['child_declaration_ref'])
    for declaration in (parent,child):validate('capsule-declaration',declaration)
    if child['identity']['lineage']['builder_ref']!=result['final_attempt_ref'] or child['identity']['lineage']['parent']!=session['parent_declaration_ref']:raise ValueError('Child lineage does not name exact final attempt/parent')
    before={row['path']:row['sha256'] for row in parent['identity']['body']};after={row['path']:row['sha256'] for row in child['identity']['body']}
    touched={path for path in before.keys()|after.keys() if before.get(path)!=after.get(path)}
    if not touched or not touched.issubset(target['mutable_paths']):raise ValueError('Child has forbidden/missing actual changes')
    protected=[]
    for declaration in (parent,child):
        value=copy.deepcopy(declaration)
        for key in ('version_label','carrier','body','lineage'):value['identity'].pop(key,None)
        protected.append(value)
    if protected[0]!=protected[1]:raise ValueError('Child changed protected authored obligations')
    implementations=[resolve_body_ref(row['sha256']) for row in child['identity']['body']]
    for pin in implementations:read_ref(pin)
    provenance={'schema_version':'1.0.0','id':'provenance:'+uuid.uuid4().hex,'declaration_ref':result['child_declaration_ref'],
        'implementation_refs':implementations,'parent_ref':target['parent_ref'],'builder_ref':result['final_attempt_ref'],
        'evidence_refs':[result['referee_evidence_ref'],*attempt['visible_evidence_refs']][:32]}
    validate('candidate-provenance',provenance);provenance_ref=put_record(provenance)
    from datetime import datetime,timezone
    package={'schema_version':'1.0.0','id':'package:'+uuid.uuid4().hex,'target_profile_ref':session['target_profile_ref'],'session_ref':result['session_ref'],
        'session_result_ref':session_result_ref,'provenance_ref':provenance_ref,'parent':session['parent'],'child':result['child'],
        'parent_declaration_ref':session['parent_declaration_ref'],'child_declaration_ref':result['child_declaration_ref'],'diff_ref':attempt['diff_ref'],
        'referee_evidence_ref':result['referee_evidence_ref'],'mutable_paths_touched':sorted(touched),'created_at':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    validate('candidate-package',package);return package


def publish_candidate(package,*,read_public,publication,qualification=None):
    """Copy only an already-public exact closure; a hidden Ref fails closed."""
    from .qualification import require_qualification
    require_qualification(qualification,'package',session_ref=package['session_ref'],candidate_ref=package['child_declaration_ref'])
    refs=[];seen=set()
    def visit(value):
        if isinstance(value,dict):
            if set(value)=={'id','sha256'}:
                identity=(value['id'],value['sha256'])
                if identity in seen:return
                if len(seen)>=5000:raise ValueError('Candidate public closure exceeds the protected bound')
                seen.add(identity)
                raw=read_public(value)
                if not isinstance(raw,bytes):raise ValueError('Public original bytes unavailable')
                publication.put_ref(value,raw);refs.append(value)
                try:nested=json.loads(raw.decode('utf8'))
                except (ValueError,UnicodeError):return
                visit(nested)
            else:
                for item in value.values():visit(item)
        elif isinstance(value,list):
            for item in value:visit(item)
    visit(package)
    return refs


def write_candidate(package,*,session_result,referee_evidence,public_key,key_id,read_ref,validate,inbox,custodian_uid,qualification=None):
    if not hasattr(os,'geteuid') or os.geteuid()!=custodian_uid:raise PermissionError('custodian identity required')
    from .qualification import require_qualification
    require_qualification(qualification,'package',session_ref=package.get('session_ref'),candidate_ref=package.get('child_declaration_ref'))
    verify(session_result,public_key,key_id);verify(referee_evidence,public_key,key_id)
    validate('rsi-session-result',session_result);validate('rsi-referee-evidence',referee_evidence);validate('candidate-package',package)
    if session_result.get('schema_version')!='2.0.0' or referee_evidence.get('schema_version')!='2.0.0':raise ValueError('New candidate packages require current signed records')
    if session_result['outcome']!='QUALIFIED' or session_result['qualified_by']=='none' or not session_result['statistics']:raise ValueError('nonqualified session cannot produce package')
    if not referee_evidence['mandatory_parent_tests_passed'] or not referee_evidence['integrity_passed'] or referee_evidence['final_evaluations']!=1 or referee_evidence['violations']:raise ValueError('independent final prerequisites failed')
    if package['child']!=session_result['child'] or package['parent']!=session_result['parent'] or package['referee_evidence_ref']!=session_result['referee_evidence_ref']:raise ValueError('package identity mismatch')
    if read_ref(package['session_result_ref'])!=encoded(session_result) or read_ref(package['referee_evidence_ref'])!=encoded(referee_evidence):raise ValueError('assessed evidence bytes mismatch')
    target=__import__('json').loads(read_ref(package['target_profile_ref']))
    if set(package['mutable_paths_touched'])-set(target['mutable_paths']):raise ValueError('forbidden mutation path')
    for key in ('child_declaration_ref','parent_declaration_ref','diff_ref','provenance_ref','session_ref'):read_ref(package[key])
    root=Path(inbox)
    if not root.is_absolute() or any(p.is_symlink() for p in (root,*root.parents)):raise ValueError('Unsafe admission inbox path')
    root.mkdir(mode=0o2750,parents=True,exist_ok=True)
    metadata=root.stat()
    if metadata.st_uid!=custodian_uid or metadata.st_mode&0o022:raise ValueError('Admission inbox permits an untrusted writer')
    os.chmod(root,0o2750)
    path=root/(uuid.uuid4().hex+'.json')
    with path.open('xb') as f:
        os.fchmod(f.fileno(),0o640);f.write(encoded(package));f.flush();os.fsync(f.fileno())
    directory=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)
    # This file is an inbox candidate, with no library standing side effect.
    return path
