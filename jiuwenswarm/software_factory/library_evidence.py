"""Read-only access to real Library onboarding and component-check records.

Recorded component checks are deliberately separate from Agent plans. This
module never dispatches a process, rewrites a run, or invents an execution event.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re


class EvidenceConflict(RuntimeError):
    pass


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(path, *, limit=8_000_000):
    path=Path(path)
    if not path.is_file() or path.stat().st_size>limit:
        raise EvidenceConflict('Evidence is absent or exceeds its read limit')
    try:
        return json.loads(path.read_text())
    except (ValueError,UnicodeError) as error:
        raise EvidenceConflict('Evidence is not valid JSON') from error


def _inside(path, root):
    try:
        original=Path(path)
        resolved=original.resolve(strict=True)
    except OSError as error:
        raise EvidenceConflict('Recorded evidence file is no longer available') from error
    if original.is_symlink() or not resolved.is_relative_to(Path(root).resolve()):
        raise EvidenceConflict('Evidence path is outside its approved record directory')
    return resolved


def _canonical_version(value, *, workflow=False):
    canonical=deepcopy(value)
    canonical.pop('version',None)
    if workflow:
        for part in canonical.get('subworkflows',[]):
            part.get('implementation',{}).pop('prompt_path',None)
    raw=json.dumps(canonical,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return 'sha256:'+_sha(raw)


def import_materials(library_root, job):
    """Return only exact files derived from this owned, recorded import.

    The original bundle version binds wrapper declaration contents; MD and
    decomposition files also have recorded byte hashes. No file-path parameter
    from the browser is accepted.
    """
    root=Path(library_root).resolve()
    workflow=job.get('workflow')
    if not workflow:
        return []
    project_root=root/'projects'/job['id']
    raw_path=_inside(Path(workflow['source']['decomposition_path']).parent/'workflow-bundle.json',project_root)
    raw=_json(raw_path)
    if _canonical_version(raw)!=raw.get('version'):
        raise EvidenceConflict('Original import bundle content no longer matches its recorded version')
    registered=root/'definitions'/workflow['id']/workflow['version'].removeprefix('sha256:')/'workflow.json'
    registered=_inside(registered,root/'definitions')
    recorded=_json(registered)
    if recorded!=workflow or _canonical_version(recorded,workflow=True)!=workflow['version']:
        raise EvidenceConflict('Registered workflow no longer matches this import record')
    rows=[]

    def add(identity,name,kind,path,*,expected_sha=None,expected_content=None,scope=project_root):
        file=_inside(path,scope)
        data=file.read_bytes()
        if len(data)>2_000_000:
            raise EvidenceConflict('Import material exceeds its bounded read limit')
        if expected_sha and _sha(data)!=expected_sha:
            raise EvidenceConflict('Recorded import material bytes changed')
        if expected_content is not None and _json(file)!=expected_content:
            raise EvidenceConflict('Recorded wrapper declaration changed')
        rows.append({'id':identity,'name':name,'kind':kind,'path':str(file),'sha256':_sha(data),
                     'integrity':'recorded-sha256' if expected_sha else 'recorded-content' if expected_content is not None else 'observed-bytes'})

    add('source-decomposition','Source decomposition','decomposition',workflow['source']['decomposition_path'],
        expected_sha=workflow['source']['decomposition_sha256'])
    add('acquisition','Source acquisition commands','commands',raw_path.with_name('acquisition.json'))
    add('workflow-bundle','Original workflow bundle','definition',raw_path,expected_content=raw)
    add('registered-workflow','Registered workflow.json','definition',registered,
        expected_content=workflow,scope=root/'definitions')
    current_format=(raw.get('composition',{}).get('schema')=='factory.workflow-composition.v1'
                    and raw.get('default_flow_role')=='display_only')
    if raw.get('composition_manifest'):
        if (not current_format or raw.get('composition')!=workflow.get('composition')
                or raw.get('composition_sha256')!=workflow.get('composition_sha256')):
            raise EvidenceConflict('Recorded parent composition format or identity is inconsistent')
        add('parent-composition','Parent workflow composition','composition',raw['composition_manifest'],
            expected_sha=raw['composition_sha256'],expected_content=raw['composition'])
    for part in raw['subworkflows']:
        identity=part['id']
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,95}',identity):
            raise EvidenceConflict('Invalid recorded wrapper identity')
        manifest=_inside(part['wrapper_manifest'],project_root)
        declared=deepcopy(part)
        wrapper=part.get('inspection',{}).get('wrapper')
        if current_format:
            if not isinstance(wrapper,dict) or wrapper.get('manifest')!=part['wrapper_manifest']:
                raise EvidenceConflict('Current wrapper format requires its recorded self-reference')
        else:
            if wrapper is not None:
                raise EvidenceConflict('Unrecognized import wrapper format')
            declared.pop('wrapper_manifest',None)
        add('part.'+identity+'.definition',part['name']+' — workflow.json','definition',manifest,expected_content=declared)
        implementation=part['implementation']
        expected_entry=manifest.with_name('execute.py' if implementation['type']=='python' else 'instructions.md')
        expected_sha=None
        if wrapper is not None:
            if _inside(wrapper['entry'],project_root)!=expected_entry or not re.fullmatch(r'[a-f0-9]{64}',str(wrapper.get('sha256',''))):
                raise EvidenceConflict('Recorded wrapper entry path or SHA is invalid')
            expected_sha=wrapper['sha256']
        if implementation['type']=='python':
            add('part.'+identity+'.entrypoint',part['name']+' — execute.py','python',expected_entry,expected_sha=expected_sha)
        elif implementation['type']=='agent':
            if expected_sha and expected_sha!=implementation['prompt_sha256']:
                raise EvidenceConflict('Recorded Agent wrapper differs from its pinned instruction')
            add('part.'+identity+'.instruction',part['name']+' — instructions.md','instruction',expected_entry,
                expected_sha=implementation['prompt_sha256'])
    return rows


def import_material(library_root,job,material_id):
    value=next((row for row in import_materials(library_root,job) if row['id']==material_id),None)
    if value is None:
        raise FileNotFoundError(material_id)
    raw=Path(value['path']).read_bytes()
    if _sha(raw)!=value['sha256']:
        raise EvidenceConflict('Import material changed while reading')
    return {**value,'content':raw.decode('utf-8')}


MODEL_ATTEMPT_FIELDS=('schema','recorded_at','driver','model','exit_code','outcome','reason_code',
                      'observed_http_statuses','receipt_sha256','evidence_kind','live_probe')


def model_attempt_projection(receipt_path):
    """Project scalar facts from an actual invocation, without exposing logs."""
    receipt_path=Path(receipt_path).resolve(strict=True)
    value=_json(receipt_path,limit=1_000_000)
    if not isinstance(value,dict) or type(value.get('exit_code')) is not int:
        raise EvidenceConflict('Model invocation receipt has no actual exit status')
    recorded_at=value.get('finished_at')
    try:
        if datetime.fromisoformat(recorded_at).tzinfo is None:raise ValueError('Completion time needs a timezone')
    except (ValueError,TypeError):raise EvidenceConflict('Model invocation receipt has no recorded completion time')
    diagnostic='\n'.join(str(value.get(name,''))[-64_000:] for name in ('stdout','stderr'))
    statuses=sorted({int(status) for status in re.findall(
        r'(?i)(?:HTTP(?:/\d(?:\.\d)?)?\s*|status(?: code)?[: ]+|response:\s*)([45]\d{2})',diagnostic)})
    failed=value['exit_code']!=0 or value.get('timed_out') is True
    error_messages=[]
    for line in str(value.get('stdout',''))[-64_000:].splitlines():
        try:
            event=json.loads(line)
            if isinstance(event,dict) and event.get('type') in {'error','turn.failed'}:
                error_messages.append(str(event.get('message') or event.get('error',{}).get('message','')))
        except (ValueError,TypeError,AttributeError):pass
    reason_text='\n'.join(error_messages) if error_messages else str(value.get('stderr',''))[-64_000:]
    reason='no_error_recorded'
    if failed:
        if value.get('timed_out') is True:reason='timeout'
        elif re.search(r'access token|authentication|unauthorized|sign in again',reason_text,re.I):reason='authentication_failed'
        else:reason='process_failed'
    def label(key,default):
        text=str(value.get(key,default))
        return text if re.fullmatch(r'[A-Za-z0-9_.:/-]{1,120}',text) else default
    return {'schema':'factory.model-connection-attempt.v1','recorded_at':recorded_at,
            'driver':label('driver','unknown'),'model':label('model','configured-default'),
            'exit_code':value['exit_code'],'outcome':'failed' if failed else 'finished','reason_code':reason,
            'observed_http_statuses':statuses,'receipt_sha256':_sha(receipt_path.read_bytes()),
            'evidence_kind':'recorded_invocation','live_probe':False}


def publish_model_attempt(receipt_path,factory_root):
    """Explicit local evidence preparation; never a model request or UI action."""
    from .workflow_library import write_json
    projection=model_attempt_projection(receipt_path)
    path=Path(factory_root).resolve()/'model-connections'/(projection['receipt_sha256']+'.json')
    write_json(path,{**projection,'source_receipt_path':str(Path(receipt_path).resolve(strict=True))})
    return path


def latest_model_attempt(factory_root,owner):
    if owner!='local-operator':return None
    root=Path(factory_root).resolve()/'model-connections'
    if not root.is_dir() or root.is_symlink():return None
    candidates=[]
    for path in sorted(root.glob('*.json'),key=lambda file:file.stat().st_mtime,reverse=True)[:64]:
        try:
            record=_json(_inside(path,root),limit=8_000)
            source=Path(record['source_receipt_path'])
            if source.name!='invocation.json':raise EvidenceConflict('Projection has no identified invocation source')
            projected=model_attempt_projection(source)
            if any(record.get(key)!=projected[key] for key in MODEL_ATTEMPT_FIELDS):
                raise EvidenceConflict('Recorded model-attempt projection changed')
            candidates.append(projected)
        except (EvidenceConflict,OSError,ValueError,KeyError,TypeError):
            continue
    return max(candidates,key=lambda row:datetime.fromisoformat(row['recorded_at'])) if candidates else None


class ComponentChecks:
    """Inspect existing local-operator checks without turning them into plans."""
    def __init__(self, factory_root, library_root):
        self.factory_root=Path(factory_root).resolve()
        self.root=self.factory_root/'checks'
        self.library_root=Path(library_root).resolve()

    def _directory(self,identity,owner):
        if owner!='local-operator' or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',identity):
            raise FileNotFoundError(identity)
        if self.root.is_symlink() or not self.root.resolve().is_relative_to(self.factory_root):
            raise FileNotFoundError(identity)
        directory=self.root/identity
        if not directory.is_dir() or directory.is_symlink():
            raise FileNotFoundError(identity)
        return _inside(directory,self.root)

    def list(self,owner):
        if owner!='local-operator' or not self.root.is_dir() or self.root.is_symlink():
            return []
        values=[]
        for path in sorted(self.root.glob('*/run.json')):
            try:
                value=self.get(path.parent.name,owner)
            except (FileNotFoundError,EvidenceConflict,OSError,ValueError,KeyError,TypeError):
                continue
            run=value['run']
            values.append({'id':value['id'],'status':run['status'],'read_only':True,
                           'selection_source':value['selection_source'],'created_at':run.get('created_at'),
                           'artifact_count':len(run.get('artifacts',[])),'run_dir':run['run_dir'],
                           'verification_status':(value.get('verification') or {}).get('status')})
        return sorted(values,key=lambda row:row.get('created_at') or '',reverse=True)

    def get(self,identity,owner):
        directory=self._directory(identity,owner)
        run_path=_inside(directory/'run.json',directory)
        run=_json(run_path)
        if not isinstance(run,dict) or not isinstance(run.get('graph'),dict) or not isinstance(run.get('artifacts'),list):
            raise EvidenceConflict('Recorded run is not a valid execution snapshot')
        if run.get('id')!=identity or Path(run.get('run_dir','')).resolve()!=directory:
            raise EvidenceConflict('Recorded run identity does not match its directory')
        selection=run.get('graph',{}).get('selection_source')
        if not isinstance(selection,str) or not selection:
            raise EvidenceConflict('Component check has no recorded selection provenance')
        graph_path=_inside(directory/'graph.json',directory)
        if _json(graph_path)!=run['graph']:
            raise EvidenceConflict('Recorded graph changed')
        events_path=_inside(directory/'events.jsonl',directory)
        if events_path.stat().st_size>32_000_000:
            raise EvidenceConflict('Recorded event stream exceeds its bounded read limit')
        events=[json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
        if not all(isinstance(event,dict) and isinstance(event.get('payload'),dict) for event in events):
            raise EvidenceConflict('Recorded event stream contains invalid events')
        if [event.get('sequence') for event in events]!=list(range(1,len(events)+1)) or run.get('sequence')!=len(events):
            raise EvidenceConflict('Recorded event stream is not the original complete sequence')
        verification=None;verification_path=None;commands=[]
        for candidate in sorted(self.root.glob('*.json')):
            report=_json(_inside(candidate,self.root))
            if isinstance(report,dict) and Path(report.get('run_dir','')).resolve()==directory:
                if verification is not None:
                    raise EvidenceConflict('Multiple independent verification reports identify the same check')
                verification,verification_path=report,candidate
        if verification:
            if verification.get('selection_source')!=selection:
                raise EvidenceConflict('Independent verification has different selection provenance')
            if not isinstance(verification.get('commands',[]),list):
                raise EvidenceConflict('Independent verification commands are not valid records')
            for record in verification.get('commands',[]):
                if not isinstance(record,dict):
                    raise EvidenceConflict('Independent verification commands are not valid records')
                stdout=_inside(record['stdout_path'],self.root)
                stderr=_inside(record['stderr_path'],self.root)
                invocation=_inside(stdout.with_name('invocation.json'),self.root)
                actual=_json(invocation)
                if actual!=record:
                    raise EvidenceConflict('Independent command record changed')
                if stdout.read_text()[-16000:]!=record.get('stdout','') or stderr.read_text()[-16000:]!=record.get('stderr',''):
                    raise EvidenceConflict('Independent command output changed')
                commands.append(actual)
        definitions=[];definition_errors=[];seen=set()
        for node in run['graph'].get('nodes',[]):
            ref=node.get('workflow',{});key=(ref.get('id'),ref.get('version'))
            if key in seen:continue
            seen.add(key)
            try:
                if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,95}',str(key[0])) or not re.fullmatch(r'sha256:[a-f0-9]{64}',str(key[1])):
                    raise EvidenceConflict('Invalid recorded workflow reference')
                path=_inside(self.library_root/'definitions'/key[0]/key[1].split(':')[1]/'workflow.json',self.library_root/'definitions')
                definition=_json(path)
                if definition.get('id')!=key[0] or definition.get('version')!=key[1] or _canonical_version(definition,workflow=True)!=key[1]:
                    raise EvidenceConflict('Frozen workflow declaration changed')
                definitions.append(definition)
            except (EvidenceConflict,OSError,ValueError,KeyError,TypeError) as error:
                definition_errors.append({'workflow_id':key[0],'version':key[1],'message':str(error)})
        provenance={'run_path':str(run_path),'run_sha256':_sha(run_path.read_bytes()),
                    'graph_sha256':_sha(graph_path.read_bytes()),'events_sha256':_sha(events_path.read_bytes()),
                    'event_count':len(events),'post_run_verification_is_separate':True}
        if verification_path:
            provenance.update(verification_path=str(verification_path),verification_sha256=_sha(verification_path.read_bytes()))
        return {'id':identity,'read_only':True,'selection_source':selection,'run':run,'events':events,
                'verification':verification,'command_records':commands,'recording_provenance':provenance,
                'workflow_definitions':definitions,'definition_errors':definition_errors}

    def artifact(self,identity,artifact_id,owner):
        value=self.get(identity,owner)
        run=value['run']
        artifact=next((a for a in run.get('artifacts',[]) if a.get('id')==artifact_id),None)
        if artifact is None:raise FileNotFoundError(artifact_id)
        published=[event['payload'].get('artifact') for event in value['events'] if event.get('type')=='artifact.published']
        if artifact not in published:
            raise EvidenceConflict('Artifact is not present in the original publication events')
        path=_inside(artifact['path'],self.root/identity)
        if not path.is_file() or path.stat().st_size!=artifact.get('size') or _sha(path.read_bytes())!=artifact.get('sha256'):
            raise EvidenceConflict('Published component artifact bytes changed')
        return path,artifact

    def project_file(self,identity,artifact_id,relative,owner):
        manifest,artifact=self.artifact(identity,artifact_id,owner)
        if artifact.get('kind')!='source.project':raise FileNotFoundError(artifact_id)
        project=_json(manifest)
        if project.get('schema')!='factory.source-project.v1':
            raise EvidenceConflict('Invalid source-project manifest')
        expected=project.get('files',{}).get(relative)
        if not expected:raise FileNotFoundError(relative)
        source=_inside(project['source_dir'],self.root/identity)
        path=_inside(source/relative,source)
        if not path.is_file() or _sha(path.read_bytes())!=expected:
            raise EvidenceConflict('Published project member bytes changed')
        return path,expected
