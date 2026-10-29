"""Frozen V18 ABI and actual canonical kernel code, with synthetic pipes only."""
import asyncio
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).parents[3]
spec=importlib.util.spec_from_file_location('unit_v18_bounded_admin',ROOT/'deploy/m1/rsi_development_run.py')
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
FROZEN=ROOT.parent/'rsi-review-evidence/2026-10-25/frozen-v18-public-development-api-source-r1/research/executor.py'


def frozen():
    if not FROZEN.exists():pytest.skip('Read-only independently exported V18 public source unavailable')
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest()==d.V18_EXECUTOR_SHA256
    name='unit_actual_frozen_v18_executor'
    spec=importlib.util.spec_from_file_location(name,FROZEN)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def test_actual_v18_job_and_kernel_signatures_support_only_real_fields():
    import inspect
    module=frozen()
    assert 'output_limit_bytes' not in inspect.signature(module.ExecutionJob).parameters
    assert list(inspect.signature(module.RestrictedExecutor._run_kernel).parameters)==[
        'self','job','command','output_parent','stdin_bytes','stdout_line_observer','stdout_line_limit']
    # Every job keyword in the actual admin evaluator is accepted by V18.
    import ast
    tree=ast.parse((ROOT/'deploy/m1/rsi_development_run.py').read_text())
    call=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='ExecutionJob')
    assert {kw.arg for kw in call.keywords}<=set(inspect.signature(module.ExecutionJob).parameters)


def test_admin_constructor_keywords_match_all_exported_frozen_public_apis():
    import ast,json
    directory=FROZEN.parents[1]
    if not directory.exists():pytest.skip('Exported frozen public source unavailable')
    manifest=json.loads((directory/'public-source-manifest.json').read_text())
    for row in manifest['files']:
        assert hashlib.sha256((directory/row['path']).read_bytes()).hexdigest()==row['sha256']
    classes={'SQLiteRunStore':'research/state.py','LibraryService':'research/library.py',
        'ContractFactory':'research/binding.py','UploadManager':'research/uploads.py',
        'RecordStore':'research_rsi/records.py','IsolatedResources':'research/isolated_resources.py'}
    signatures={}
    for name,file in classes.items():
        tree=ast.parse((directory/file).read_text())
        cls=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name==name)
        method=next((node for node in cls.body if isinstance(node,ast.FunctionDef) and node.name=='__init__'),None)
        signatures[name]=(set(arg.arg for arg in [*method.args.args,*method.args.kwonlyargs]) if method else
            {node.target.id for node in cls.body if isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name)})
    checked=set()
    for filename in ('rsi_development_run.py','rsi_development_seed.py','rsi_development_prepare.py'):
        tree=ast.parse((ROOT/'deploy/m1'/filename).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in signatures:
                assert {kw.arg for kw in node.keywords}<=signatures[node.func.id],(filename,node.func.id)
                checked.add(node.func.id)
    assert checked==set(classes)


def test_frozen_attempt_cas_is_unissued_then_prepared_and_never_replayable(tmp_path):
    import ast,json,types
    from jiuwenswarm.research.state import SQLiteRunStore,json_bytes
    from jiuwenswarm.research.contracts import ResearchError
    source=FROZEN.parents[1]/'research/state.py'
    if not source.exists():pytest.skip('Frozen public state source unavailable')
    tree=ast.parse(source.read_text())
    cls=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='SQLiteRunStore')
    method=next(node for node in cls.body if isinstance(node,ast.FunctionDef) and node.name=='claim_attempt')
    namespace={'Ref':dict,'Mapping':dict,'json':json,'json_bytes':json_bytes,'ResearchError':ResearchError}
    exec(compile(ast.Module(body=[method],type_ignores=[]),str(source),'exec'),namespace)
    core=SQLiteRunStore(tmp_path/'core',recover=False)
    try:
        core.create_run('run',account_id='unit',workspace_id='local',submission={})
        contract={'run_id':'run','node_id':'node','subnode_id':'proposal','attempt_id':'a1'}
        key=tuple(contract.values());pin={'id':'actual-work-not-intake','sha256':'a'*64}
        row=lambda:core.connection.execute('SELECT state,contract_ref FROM attempts WHERE run_id=? AND node_id=? AND subnode_id=? AND attempt_id=?',key).fetchone()
        d.require_unissued_attempt(row())
        claim=types.MethodType(namespace['claim_attempt'],core)
        assert claim(pin,contract) is True and row()[0]=='prepared'
        with pytest.raises(ValueError,match='NO_REPLAY'):d.require_unissued_attempt(row())
        assert claim(pin,contract) is False
        assert core.connection.execute('SELECT COUNT(*) FROM model_calls').fetchone()[0]==0
    finally:core.close()


@pytest.mark.parametrize('out,err,overflow',[(b'{}',b'',False),(b'x'*100000,b'',True),
    (b'{}',b'e'*100000,True),(b'o'*6000,b'e'*6000,True),(b'o'*4096,b'e'*4096,False)],
    ids=['small','stdout-flood','stderr-flood','combined-overflow','exact-boundary'])
def test_unchanged_frozen_kernel_caps_both_streams_before_any_file_write(tmp_path,monkeypatch,out,err,overflow):
    module=frozen(); real_asyncio=module.asyncio
    class Process:
        pid=12345;returncode=None;stdin=None
        def __init__(self,gate):
            self.gate=gate
            self.stdout=asyncio.StreamReader();self.stderr=asyncio.StreamReader()
            self.stdout.feed_data(b'AI4R_EXECUTOR_PROBE_V1 {"ready":true,"network":"none"}\n'+out);self.stdout.feed_eof()
            self.stderr.feed_data(err);self.stderr.feed_eof()
        async def wait(self):
            await asyncio.sleep(.01);self.returncode=0
            if self.gate is not None:os.close(self.gate);self.gate=None
            return 0
    class Facade:
        def __getattr__(self,name):return getattr(real_asyncio,name)
        async def create_subprocess_exec(self,*args,**kwargs):return Process(os.dup(kwargs['pass_fds'][0]))
    # Only this separately loaded unit-test module gets synthetic transport.
    facade=Facade();monkeypatch.setattr(module,'asyncio',facade)
    group=tmp_path/'group';group.mkdir()
    for name,value in {'cgroup.procs':'','cgroup.kill':'0','memory.events':'oom_kill 0\n',
                       'pids.events':'max 0\n','memory.max':'268435456','pids.max':'16'}.items():(group/name).write_text(value)
    typ=d.bounded_executor(module.RestrictedExecutor);executor=object.__new__(typ)
    foreign=tmp_path/'foreign';foreign.mkdir();(foreign/'cgroup.kill').write_text('0')
    executor.active={'foreign':(None,foreign)};executor.uid=executor.gid=12003;executor.lifecycle_observer=None
    executor._cgroup=lambda job:group
    emptied=[]
    async def empty(actual):assert actual==group;emptied.append(True)
    executor._wait_empty=empty
    captured=[]
    def capture(raw,**kwargs):captured.append(raw);return {'id':str(len(captured)),'sha256':d.digest(raw)}
    executor.capture=capture
    ref={'id':'synthetic-only','sha256':'a'*64}
    job=module.ExecutionJob('unit','unit',ref,'run','node','a1',1,'treatment',0,0,('/fixed/public-program',),
        tmp_path,1,256,16,ref,ref,ref,ref,ref)
    receipt=asyncio.run(executor._run_kernel(job,['/fixed/public-program'],output_parent=tmp_path))
    files=tmp_path/'unit.capture'
    actual=(files/'stdout').read_bytes()+(files/'stderr').read_bytes()
    assert len(actual)<=8192 and receipt['observed_limits']['admin_output_captured_bytes']==len(actual)
    assert receipt['observed_limits']['admin_output_truncated'] is overflow
    assert receipt['termination_reason']==('output_limit_exceeded' if overflow else 'completed')
    assert receipt['observed_limits']['admin_kernel_source_sha256']==d.V18_EXECUTOR_SHA256
    assert emptied and set(executor.active)=={'foreign'} and (foreign/'cgroup.kill').read_text()=='0'
    assert module.asyncio is facade and asyncio is real_asyncio
    assert len(captured[0])<4096 and captured[1]+captured[2]==actual
