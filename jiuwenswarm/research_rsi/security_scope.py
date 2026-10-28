"""Finite current-worker scope observation, never thirteen-case qualification.

The trusted Python launcher supplies an actual WorkerBroker and independently
approved scope. A separate OS-root host capture binds the current container to
its inspected image. No scope field selects a module, callback or filesystem
root. App admission must validate this producer's approved scope; measuring the
app container here would attest the wrong runtime.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path,PurePosixPath
import platform
import re
import stat
import subprocess

from .records import encoded
from .session_policy import validate_private
from .worker import WorkerBroker, PublicBytes, validate_profile, ref
from jiuwenswarm.research.executor import RestrictedExecutor

OBSERVATION_SCHEMA='urn:ai4r:private:rsi-runtime-observation:1'
SCOPE_SCHEMA='urn:ai4r:private:rsi-security-scope:1'
MAX_BYTES=4*1024*1024


class ScopeUnavailable(ValueError):
    """Current independently pinned producer runtime cannot be established."""


def _need(condition):
    if not condition:raise ScopeUnavailable('Current protected RSI producer scope is unavailable or stale')


def _json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            _need(key not in result);result[key]=value
        return result
    return json.loads(raw.decode('utf8'),object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(ScopeUnavailable('Nonfinite runtime capture')))


def _path(value):
    path=Path(value)
    _need(path.is_absolute() and '..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents)))
    return path


def _root_bytes(value,maximum=MAX_BYTES):
    path=_path(value)
    descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        meta=os.fstat(descriptor)
        _need(stat.S_ISREG(meta.st_mode) and meta.st_uid==0 and not meta.st_mode&0o022
              and meta.st_nlink==1 and 0<=meta.st_size<=maximum)
        with os.fdopen(descriptor,'rb',closefd=False) as stream:raw=stream.read(maximum+1)
        _need(len(raw)<=maximum)
        return raw
    finally:os.close(descriptor)


def _capture_ancestry(path):
    if os.name!='posix':return
    for parent in path.parents:
        meta=parent.stat()
        # Root-owned sticky /tmp is safe for an exclusively owned child.
        _need(meta.st_uid==0 and (not meta.st_mode&0o022 or meta.st_mode&stat.S_ISVTX))


def _original(public,pin):
    ref(pin);raw=public.read(pin)
    _need(isinstance(raw,bytes) and 0<len(raw)<=MAX_BYTES and hashlib.sha256(raw).hexdigest()==pin['sha256'])
    return raw


def _mounts():
    result=[]
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        left,right=line.split(' - ',1);fields=left.split()
        name=re.sub(r'\\([0-7]{3})',lambda m:chr(int(m[1],8)),fields[4])
        result.append((Path(name),set(fields[5].split(',')),right.split()[0]))
    return result


def _mount_for(path):
    choices=[row for row in _mounts() if row[0]==path or row[0] in path.parents]
    _need(bool(choices));return max(choices,key=lambda row:len(row[0].parts))


def _start_ticks(proc):
    raw=(proc/'stat').read_text()
    # comm can contain spaces and parentheses; the final ')' precedes state.
    value=int(raw[raw.rindex(')')+2:].split()[19]);_need(value>0);return value


def _identity(proc=Path('/proc/self'),init=Path('/proc/1')):
    _need(platform.system()=='Linux')
    ids=set(re.findall(r'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])',(proc/'cgroup').read_text()))
    _need(len(ids)==1)
    machine=platform.machine().lower();architecture={'x86_64':'amd64','amd64':'amd64','aarch64':'arm64','arm64':'arm64'}.get(machine)
    _need(architecture is not None)
    return {'container_id':ids.pop(),'pid_namespace':os.readlink(proc/'ns/pid'),
        'mount_namespace':os.readlink(proc/'ns/mnt'),
        'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'kernel_release':platform.release(),'platform':'linux/'+architecture,
        'init_start_ticks':_start_ticks(init)}


def _installed_roots():
    import jiuwenswarm
    # These roots come from installed Python ownership, never capture fields.
    package=_path(Path(jiuwenswarm.__file__).parent)
    installed=_path(importlib.metadata.distribution('workswarm').locate_file('jiuwenswarm'))
    tui=_path(importlib.metadata.distribution('workswarm-tui').locate_file('jiuwenswarm_tui'))
    return package,installed,tui


def _inventory(root):
    files=[];links=[];total=0
    paths=sorted(root.rglob('*'))
    _need(len(paths)<=20000)
    for path in paths:
        if path.suffix=='.pyc' or '__pycache__' in path.parts:continue
        name=path.relative_to(root).as_posix()
        if path.is_symlink():
            target=os.readlink(path)
            _need(not Path(target).is_absolute() and path.resolve(strict=True).is_relative_to(root))
            meta=path.lstat();_need(meta.st_uid==0)
            links.append({'path':name,'target':target});continue
        if path.is_dir():
            meta=path.stat();_need(meta.st_uid==0 and not meta.st_mode&0o022);continue
        # The frozen native runtime includes a 4.4MB compiled component.
        # Keep small capture bounds separate from bounded installed assets.
        raw=_root_bytes(path,16*1024*1024);total+=len(raw);_need(total<=128*1024*1024)
        _need(path.name not in {'auth.json','credentials.json','secrets.json','.env'} and
              not (path.name.startswith('.env.') and path.name!='.env.template'))
        files.append({'path':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    _need(bool(files));return {'files':files,'links':links}


def _dependencies():
    return sorted(({'name':d.metadata['Name'],'version':d.version} for d in importlib.metadata.distributions()),
                  key=lambda row:row['name'].lower())


def _source_files():
    executor=Path(inspect.getsourcefile(RestrictedExecutor))
    return {'worker_driver_ref':Path(inspect.getsourcefile(WorkerBroker)),
            'executor_ref':executor,'probe_ref':executor.with_name('_executor_probe.py')}


def _installed_build(public,build):
    _need(isinstance(build,dict) and bool(build.get('candidate_id',build.get('candidate_sha256'))))
    manifest=_json(_original(public,build['installed_build_ref']))
    _need(manifest.get('schema')=='ai4r-installed-build:2')
    payload={key:value for key,value in manifest.items() if key!='build_id'}
    calculated=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    _need(manifest.get('build_id')==calculated)
    package,installed,tui=_installed_roots()
    current=_inventory(package);installed_current=current if installed==package else _inventory(installed)
    current_tui=_inventory(tui)
    _need(manifest.get('files')==current['files'] and manifest.get('links')==current['links'] and
          current==installed_current and
          manifest.get('components')=={'jiuwenswarm_tui':current_tui} and manifest.get('dependencies')==_dependencies())
    # Every measured entrypoint belongs to the full independently pinned tree.
    for path in _source_files().values():_need(_path(path).is_relative_to(package))


class RuntimeScopeObserver:
    """Callable for captured_qualification(..., scope_observer=observer).

    Construct only beside the actual root WorkerBroker, using independently
    approved original scope and a current root-owned host observation. This
    class does not create the separate validation-profile/case authority.
    """
    def __init__(self,*,worker_owner,approved_scope,runtime_capture_file):
        _need(type(worker_owner) is WorkerBroker and type(worker_owner.public) is PublicBytes)
        validate_private(SCOPE_SCHEMA,approved_scope)
        self._owner=worker_owner
        self._approved=copy.deepcopy(approved_scope)
        self._capture_file=_path(runtime_capture_file)
        _capture_ancestry(self._capture_file)

    def __call__(self,claimed_scope):
        try:return self._observe(claimed_scope)
        except (ValueError,KeyError,TypeError,OSError,AttributeError,ImportError,RecursionError):
            raise ScopeUnavailable('Current protected RSI producer scope is unavailable or stale') from None

    def _observe(self,claimed_scope):
        _need(claimed_scope==self._approved and hasattr(os,'geteuid') and os.geteuid()==0)
        scope=self._approved;owner=self._owner;executor=owner.executor
        _need(type(owner) is WorkerBroker and isinstance(executor,RestrictedExecutor) and executor.broker is None
              and executor.uid==12003 and executor.gid==12003)
        # Invoke the actual installed core implementation, not an owner-supplied
        # ready boolean or an overriding method returning an attestation.
        _need(RestrictedExecutor.prerequisites(executor)==[])
        _need(executor.cgroup_root is not None and _mount_for(_path(executor.cgroup_root))[2]=='cgroup2')
        _need('ro' in _mount_for(Path('/'))[1])
        _capture_ancestry(self._capture_file)
        captured=_json(_root_bytes(self._capture_file,65536));validate_private(OBSERVATION_SCHEMA,captured)
        identity=_identity()
        _need(all(captured[key]==value for key,value in identity.items()))
        _need(captured['read_only_rootfs'] is True and captured['kernel_release']==scope['kernel_release']
              and captured['platform']==scope['platform'])
        for key in ('runtime_build_ref','environment_ref','worker_profile_refs'):_need(captured[key]==scope[key])
        build=_json(_original(owner.public,scope['runtime_build_ref']))
        environment=_json(_original(owner.public,scope['environment_ref']))
        _need(environment.get('image_digest')==captured['image_digest'] and environment.get('platform')==identity['platform'])
        if environment.get('image_id') is not None:_need(environment['image_id']==captured['image_id'])
        _installed_build(owner.public,build)
        for key,path in _source_files().items():
            installed=_root_bytes(path)
            _need(hashlib.sha256(installed).hexdigest()==scope[key]['sha256'] and _original(owner.public,scope[key])==installed)
        profiles=scope['worker_profile_refs'];_need(bool(profiles) and len({encoded(p) for p in profiles})==len(profiles))
        _need(set(owner.profiles)=={encoded(pin) for pin in profiles})
        from .profiles import freeze_profile,Limits
        from .session_policy import _contracts
        for pin in profiles:
            profile=validate_profile(_json(_original(owner.public,pin)))
            _need(profile['schema']=='ai4r-rsi-worker-profile:3')
            _need(owner.profiles[encoded(pin)]==profile and profile['environment_ref']==scope['environment_ref'])
            session=_json(_original(owner.public,profile['session_ref']));_contracts().validate('rsi-session',session)
            target=_json(_original(owner.public,profile['target_ref']))
            parent=_json(_original(owner.public,target['parent_declaration_ref']))
            freeze_profile(target,parent,_contracts().validate)
            limits=Limits.from_mapping(session['limits'])
            _need(session['target_profile_ref']==profile['target_ref'] and session['parent_declaration_ref']==target['parent_declaration_ref']
                  and profile['parent_ref']==target['parent_ref'] and profile['memory_mb']<=target['limits']['memory_mb']
                  and profile['timeout_s']<=min(target['limits']['time_s'],limits.per_call_s) and session['pass_count_repeats']==1)
            for key in ('parent_ref','contract_ref','hardware_ref'):_original(owner.public,profile[key])
        return copy.deepcopy(scope)


def _docker_json(arguments):
    # Host operator only. Pin the local daemon socket; ambient Docker contexts,
    # credentials or caller-selected executables cannot change the observer.
    result=subprocess.run(['/usr/bin/docker','--host','unix:///var/run/docker.sock',*arguments],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15,
        env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8'})
    _need(result.returncode==0 and 0<len(result.stdout)<=MAX_BYTES)
    values=_json(result.stdout);_need(isinstance(values,list) and len(values)==1 and isinstance(values[0],dict))
    return values[0]


def capture_worker_scope(store,*,worker_owner,runtime_build_ref,environment_ref):
    """Capture actual installed worker identities for separate root approval.

    This does not assert prerequisites, run a case, publish authority or replace
    the fresh host/process observation required by RuntimeScopeObserver.
    """
    from .security_campaign import _protected_store
    _protected_store(store)
    _need(os.geteuid()==0 and type(worker_owner) is WorkerBroker)
    owner=worker_owner
    _need(type(owner.public) is PublicBytes and isinstance(owner.executor,RestrictedExecutor)
          and owner.executor.broker is None and owner.executor.uid==owner.executor.gid==12003)
    class Originals:
        def read(self,pin):return store.read_blob(pin)
    _installed_build(Originals(),_json(store.read_blob(runtime_build_ref)))
    _json(store.read_blob(environment_ref))
    identity=_identity();profiles=[]
    for key,value in owner.profiles.items():
        pin=_json(key);actual=validate_profile(_json(store.read_blob(pin)))
        _need(value==actual and actual['schema']=='ai4r-rsi-worker-profile:3'
              and actual['environment_ref']==environment_ref)
        profiles.append(pin)
    _need(bool(profiles))
    scope={'schema':'ai4r-rsi-security-scope:1','id':'pending',
        'runtime_build_ref':runtime_build_ref,'environment_ref':environment_ref,
        'worker_profile_refs':sorted(profiles,key=lambda pin:(pin['id'],pin['sha256'])),
        **{key:identity[key] for key in ('kernel_release','platform')},
        **{key:store.put_blob(_root_bytes(path)) for key,path in _source_files().items()}}
    scope['id']='security-scope:'+hashlib.sha256(encoded({key:value for key,value in scope.items() if key!='id'})).hexdigest()
    validate_private(SCOPE_SCHEMA,scope)
    return {'status':'CAPTURED_NOT_APPROVED','scope_ref':store.append_record('rsi-security-scope',scope)}


def build_runtime_observation(*,container_id,approved_scope,public_reader):
    """Construct data from actual local Docker/host inspection; never publish.

    Run on the Linux Docker daemon's host as OS root, outside the RSI worker.
    The existing root launcher may exclusively publish these returned bytes to
    its protected read-only mount. This function neither launches containers
    nor issues qualification. A WSL/remote client whose /proc is not the Docker
    host's cannot establish identity here and must fail closed.
    """
    try:
        _need(hasattr(os,'geteuid') and os.geteuid()==0 and type(public_reader) is PublicBytes
              and isinstance(container_id,str) and re.fullmatch('[0-9a-f]{64}',container_id))
        validate_private(SCOPE_SCHEMA,approved_scope)
        environment=_json(_original(public_reader,approved_scope['environment_ref']))
        container=_docker_json(['container','inspect',container_id])
        _need(container.get('Id')==container_id and container.get('State',{}).get('Running') is True
              and container.get('HostConfig',{}).get('ReadonlyRootfs') is True)
        # An image identity cannot authenticate code overlaid from another
        # host mount or a caller's Python search path. Role data mounts remain
        # independent and are not mistaken for installed source.
        mounts=container.get('Mounts');_need(isinstance(mounts,list))
        for mount in mounts:
            destination=PurePosixPath(mount['Destination'])
            _need(destination.is_absolute() and '..' not in destination.parts and not any(destination==PurePosixPath(base) or destination.is_relative_to(base)
                or PurePosixPath(base).is_relative_to(destination) for base in ('/opt','/usr','/bin','/sbin','/lib','/lib64')))
        environment_rows=container.get('Config',{}).get('Env');_need(isinstance(environment_rows,list))
        interpreter={}
        for row in environment_rows:
            if isinstance(row,str) and '=' in row:
                key,value=row.split('=',1)
                if key in {'PYTHONPATH','PYTHONHOME','PYTHONUSERBASE'}:
                    _need(key not in interpreter);interpreter[key]=value
        _need(interpreter.get('PYTHONPATH') in {None,'/opt/ai4r'} and not {'PYTHONHOME','PYTHONUSERBASE'}&interpreter.keys())
        pid=container['State']['Pid'];_need(type(pid) is int and pid>0)
        image_id=container['Image'];_need(isinstance(image_id,str) and re.fullmatch('sha256:[0-9a-f]{64}',image_id))
        image=_docker_json(['image','inspect',image_id]);_need(image.get('Id')==image_id)
        identities={image_id}
        for value in image.get('RepoDigests') or []:
            if isinstance(value,str) and '@sha256:' in value:identities.add(value.rsplit('@',1)[1])
        digest=environment['image_digest'];_need(digest in identities)
        identity=_identity(Path('/proc')/str(pid),Path('/proc')/str(pid))
        _need(identity['container_id']==container_id and identity['platform']==image.get('Os')+'/'+image.get('Architecture')
              and identity['kernel_release']==approved_scope['kernel_release'] and identity['platform']==approved_scope['platform']
              and environment.get('platform')==identity['platform'])
        observation={'schema':'ai4r-rsi-runtime-observation:1',**identity,'image_id':image_id,'image_digest':digest,
            'read_only_rootfs':True,**{key:copy.deepcopy(approved_scope[key]) for key in ('runtime_build_ref','environment_ref','worker_profile_refs')}}
        validate_private(OBSERVATION_SCHEMA,observation)
        return observation
    except (ValueError,KeyError,TypeError,OSError,AttributeError,ImportError,RecursionError,subprocess.TimeoutExpired):
        raise ScopeUnavailable('Actual root-owned local Docker producer observation is unavailable') from None
