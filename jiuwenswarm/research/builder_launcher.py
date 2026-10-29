"""One governed headless Builder call, with protected custody and event budgets.

This is a broker-side module. Runtime bindings are captured protected resources,
never Capsule inputs. Missing external credential or live CLI sandbox evidence
blocks construction; transcript fixtures cannot qualify a production runtime.
"""
from __future__ import annotations

import copy
import asyncio
import hashlib
import inspect
import json
import math
import os
import re
import shlex
import shutil
import stat
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from .executor import ExecutorBlocked


FILES = frozenset({'requirements.txt', 'poc_patch.py', 'run_benchmark.py'})
TOOL_TYPES = frozenset({'command_execution', 'file_change', 'mcp_tool_call', 'web_search'})
PASSIVE_TYPES = frozenset({'agent_message', 'reasoning', 'todo_list'})


async def _await(value):
    return await value if inspect.isawaitable(value) else value


def _ref(value):
    return (isinstance(value, dict) and set(value) == {'id', 'sha256'}
            and isinstance(value['id'], str) and bool(value['id'])
            and isinstance(value['sha256'], str) and re.fullmatch('[a-f0-9]{64}', value['sha256']))


def _read(store, ref):
    if not _ref(ref):
        raise ExecutorBlocked('BUILDER_CAPTURE_REFERENCE_INVALID')
    data = store.read_blob(ref)
    if hashlib.sha256(data).hexdigest() != ref['sha256']:
        raise ExecutorBlocked('BUILDER_CAPTURE_BYTES_CHANGED')
    return data


def _record(store, ref):
    value = json.loads(_read(store, ref))
    if not isinstance(value, dict):
        raise ExecutorBlocked('BUILDER_CAPTURE_RECORD_INVALID')
    return value


def _readonly_command(command):
    """Conservative classification; unrecognized commands cannot certify no trial."""
    if not isinstance(command, str) or re.search(r'[\n\r;&|><`$\\]', command):
        return False
    quote = None
    for char in command:
        if char in {'"', "'"}:
            if quote == char: quote = None
            elif quote is None: quote = char
        elif quote is None and char in '*?[]{}~':
            # Shell glob expansion could introduce option-looking filenames.
            return False
    try:
        argv = shlex.split(command)
    except ValueError:
        return False
    if not argv or argv[0] not in {'pwd', 'ls', 'cat', 'head', 'tail', 'wc', 'rg', 'grep', 'sed'}:
        return False
    if argv[0] == 'sed':
        # Only an explicit numeric print range. No e/r/w commands or scripts.
        return (len(argv) == 4 and argv[1] == '-n'
                and re.fullmatch(r'[0-9]+(?:,[0-9]+)?p', argv[2]) is not None)
    if argv[0] == 'rg':
        # ripgrep's --pre and --hostname-bin execute external programs; do not
        # classify arbitrary flags (or future flags) as read-only.
        safe = {'--','--files','--hidden','--line-number','--smart-case','--ignore-case','--fixed-strings',
                '--files-with-matches','--no-ignore','--no-heading','--with-filename',
                '-n','-i','-l','-r','-H','-S','-F','-w','-e','-g','--regexp','--glob'}
        if any(arg.startswith('-') and arg not in safe for arg in argv[1:]): return False
    return True


def _command_effect(command):
    if _readonly_command(command): return 'read', True
    if isinstance(command, str):
        if re.search(r'\b(?:pip|pip3|uv|conda|npm|apt|apt-get)\b.*\b(?:install|sync|add)\b', command):
            return 'package_install', False
        if re.search(r'\b(?:python[0-9.]*|node|sh|bash|pytest)\b', command):
            return 'trial', False
        if re.search(r'\b(?:curl|wget|ssh|scp)\b', command): return 'network', False
    return 'unclassified', False


class BuilderEvents:
    """Pinned exec JSONL adapter; one reported tool item counts once by ID."""
    def __init__(self, tool_limit):
        if type(tool_limit) is not int or not 0 < tool_limit <= 40:
            raise ExecutorBlocked('BUILDER_TOOL_LIMIT_INVALID')
        self.limit, self.tool_count = tool_limit, 0
        self.seen, self.tools, self.events = {}, [], []
        self.stop_reason, self.text, self.usage = None, '', {}
        self.turns, self.completed, self.thread_id = 0, False, None

    @property
    def success(self):
        return self.stop_reason is None and self.completed and bool(self.text)

    def _stop(self, reason):
        self.stop_reason = self.stop_reason or reason
        return self.stop_reason

    def feed(self, line):
        try:
            event = json.loads(line)
            if not isinstance(event, dict): raise ValueError()
            self.events.append(bytes(line))
            kind = event.get('type')
            if kind == 'thread.started':
                if self.thread_id is not None or not isinstance(event.get('thread_id'), str): raise ValueError()
                self.thread_id = event['thread_id']
            elif kind == 'turn.started':
                self.turns += 1
                if self.turns > 1 or self.completed: raise ValueError()
            elif kind == 'turn.completed':
                if self.completed: raise ValueError()
                self.completed = True
                usage = event.get('usage', {})
                if not isinstance(usage, dict): raise ValueError()
                for key in ('input_tokens', 'output_tokens', 'cached_input_tokens', 'reasoning_output_tokens'):
                    if key in usage:
                        if type(usage[key]) is not int or usage[key] < 0: raise ValueError()
                        self.usage[key] = usage[key]
            elif kind in {'turn.failed', 'error'}:
                return self._stop('provider_error')
            elif kind in {'item.started', 'item.updated', 'item.completed'}:
                item = event.get('item')
                if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id']: raise ValueError()
                identifier, item_type = item['id'], item.get('type')
                if item_type not in TOOL_TYPES | PASSIVE_TYPES: raise ValueError()
                if identifier in self.seen and self.seen[identifier] != item_type: raise ValueError()
                fresh = identifier not in self.seen
                self.seen[identifier] = item_type
                if item_type in TOOL_TYPES:
                    if self.completed: raise ValueError()
                    if fresh:
                        self.tool_count += 1
                        effect, allowed = self._classify(item)
                        self.tools.append({'id':identifier, 'name':item_type, 'effect':effect, 'allowed':allowed})
                    else:
                        effect, allowed = self._classify(item)
                        existing = next(tool for tool in self.tools if tool['id'] == identifier)
                        existing['allowed'] = existing['allowed'] and allowed
                    if not allowed: self._stop('prohibited_tool')
                    if self.tool_count >= self.limit: self._stop('budget_exceeded')
                elif item_type == 'agent_message' and kind == 'item.completed':
                    text = item.get('text')
                    if not isinstance(text, str): raise ValueError()
                    self.text = text
            else:
                raise ValueError()
        except (ValueError, TypeError, UnicodeError, KeyError):
            return self._stop('invalid_output')
        return self.stop_reason

    @staticmethod
    def _classify(item):
        kind = item['type']
        if kind == 'command_execution':
            return _command_effect(item.get('command'))
        if kind == 'file_change':
            changes = item.get('changes')
            if not isinstance(changes, list) or not changes: return 'write', False
            for entry in changes:
                path = entry.get('path') if isinstance(entry, dict) else None
                if not isinstance(path, str): return 'write', False
                if path.startswith('/workspace/poc/'): path = path[len('/workspace/poc/'):]
                if path not in FILES or entry.get('kind') not in {'add', 'update', 'delete'}:
                    return 'write', False
            return 'write', True
        return 'network' if kind == 'web_search' else 'external_tool', False


@dataclass(frozen=True)
class BuilderRuntime:
    """Closed, protected deployment binding; no credential bytes are serializable."""
    build_id: str
    codex_path: Path
    codex_sha256: str
    codex_version: str
    workspace_root: Path
    credential_source: Path
    credential_sha256: str
    credential_budget_ref: dict
    credential_revocation_ref: dict
    qualification_ref: dict
    memory_mb: int
    pids_max: int
    max_event_bytes: int

    @classmethod
    def from_capture(cls, store, ref, *, build_id):
        value = _record(store, ref)
        fields = set(cls.__dataclass_fields__)
        if set(value) != fields | {'schema'} or value.pop('schema') != 'ai4r-builder-runtime:1':
            raise ExecutorBlocked('BUILDER_RUNTIME_BINDING_INVALID')
        if value['build_id'] != build_id or value['codex_version'] != '0.144.4':
            raise ExecutorBlocked('BUILDER_RUNTIME_QUALIFICATION_MISMATCH')
        for field in ('codex_sha256', 'credential_sha256'):
            if not isinstance(value[field], str) or not re.fullmatch('[a-f0-9]{64}', value[field]):
                raise ExecutorBlocked('BUILDER_RUNTIME_HASH_INVALID')
        for field in ('credential_budget_ref', 'credential_revocation_ref', 'qualification_ref'):
            _read(store, value[field])
        for field in ('memory_mb', 'pids_max', 'max_event_bytes'):
            if type(value[field]) is not int or value[field] <= 0:
                raise ExecutorBlocked('BUILDER_RUNTIME_LIMIT_INVALID')
        for field in ('codex_path', 'workspace_root', 'credential_source'):
            value[field] = Path(value[field])
        if (value['workspace_root'] != Path('/var/lib/ai4r-executor/builder')
                or not value['credential_source'].is_relative_to('/var/lib/ai4r-builder-credentials')
                or value['credential_source'] == Path('/var/lib/ai4r-builder-credentials')):
            raise ExecutorBlocked('BUILDER_RUNTIME_PATH_INVALID')
        if (not value['codex_path'].is_absolute() or not value['codex_path'].is_relative_to('/usr/local')
                or value['codex_path'].name != 'codex'):
            raise ExecutorBlocked('BUILDER_RUNTIME_PATH_INVALID')
        return cls(**value)


def _custody(path, *, owner, mode=None, directory=False):
    path = Path(path)
    if not path.is_absolute() or any(part.is_symlink() for part in (path, *path.parents)):
        raise ExecutorBlocked('BUILDER_PATH_ALIAS_DENIED')
    info = path.lstat()
    if (info.st_uid != owner or (not directory and not stat.S_ISREG(info.st_mode))
            or (directory and not stat.S_ISDIR(info.st_mode))
            or (mode is not None and stat.S_IMODE(info.st_mode) != mode)):
        raise ExecutorBlocked('BUILDER_FILE_CUSTODY_INVALID')
    for ancestor in path.parents:
        metadata = ancestor.lstat()
        # Temporary test roots can be under /tmp; every production root is
        # separately fixed by the closed captured binding above.
        if ancestor != Path('/tmp') and (metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o022):
            raise ExecutorBlocked('BUILDER_ANCESTOR_CUSTODY_INVALID')
    return info


def _not_expired(record):
    try:
        expiry = datetime.fromisoformat(record['expires_at'].replace('Z', '+00:00'))
        return expiry.tzinfo is not None and expiry > datetime.now(timezone.utc)
    except (KeyError, ValueError, TypeError):
        return False


@dataclass(frozen=True)
class BuilderStage:
    job_id: str
    parent: Path
    workspace: Path
    resources: Path


@dataclass(frozen=True)
class BuilderKernelJob:
    job_id: str
    contract_ref: dict
    invocation_id: str
    argv: tuple[str, ...]
    timeout_s: float
    memory_mb: int
    pids_max: int


class BuilderCredentialLease:
    """Copy only the configured dedicated credential; executor access is temporary."""
    def __init__(self, runtime, store, stage):
        self.runtime, self.store, self.stage = runtime, store, stage
        self.home = stage.parent / 'codex-home'
        self.active = False

    @staticmethod
    def validate(runtime, store):
        _custody(runtime.credential_source.parent, owner=0, mode=0o700, directory=True)
        _custody(runtime.credential_source, owner=0, mode=0o600)
        original = runtime.credential_source.read_bytes()
        if not original or hashlib.sha256(original).hexdigest() != runtime.credential_sha256:
            raise ExecutorBlocked('BUILDER_DEDICATED_CREDENTIAL_CHANGED')
        for ref, kind in ((runtime.credential_budget_ref, 'builder-credential-budget1'),
                          (runtime.credential_revocation_ref, 'builder-credential-revocation1')):
            record = _record(store, ref)
            if (record.get('kind') != kind or record.get('purpose') != 'research.builder'
                    or record.get('credential_sha256') != runtime.credential_sha256
                    or record.get('observed_runtime') is not True or not _not_expired(record)
                    or not isinstance(record.get('provider_reference'), str) or not record['provider_reference']
                    or not record.get('evidence_refs')):
                raise ExecutorBlocked('BUILDER_EXTERNAL_CREDENTIAL_QUALIFICATION_UNAVAILABLE')
            for evidence in record['evidence_refs']: _read(store, evidence)
            if kind.endswith('budget1'):
                limit = record.get('budget_limit')
                if (type(limit) not in (int, float) or not math.isfinite(limit) or limit <= 0
                        or not isinstance(record.get('budget_unit'), str) or not record['budget_unit']):
                    raise ExecutorBlocked('BUILDER_EXTERNAL_CREDENTIAL_BUDGET_UNAVAILABLE')
        return original

    def open(self):
        original = self.validate(self.runtime,self.store)
        self.home.mkdir(mode=0o700)
        try:
            auth = self.home / 'auth.json'
            fd = os.open(auth, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as output: output.write(original)
            os.chown(auth, 10002, 10002)
            os.chown(self.home, 10002, 10002)
            self.active = True
            return self.home
        except BaseException:
            self.close()
            raise

    def close(self):
        # Only this broker-created directory, below a root-owned unrenameable
        # parent. Do not follow executor-created symlinks during cleanup.
        if self.home.exists() and not self.home.is_symlink():
            for directory, dirs, files in os.walk(self.home, topdown=False, followlinks=False):
                for name in files: (Path(directory) / name).unlink()
                for name in dirs:
                    path = Path(directory) / name
                    path.unlink() if path.is_symlink() else path.rmdir()
            self.home.rmdir()
        self.active = False


class BuilderLauncher:
    def __init__(self, *, store, executor, runtime: BuilderRuntime, authorize):
        self.store, self.executor, self.runtime, self.authorize = store, executor, runtime, authorize
        self.observations, self.stages, self.claimed, self.receipt_refs = {}, {}, set(), {}

    def _qualify(self):
        runtime = self.runtime
        _custody(runtime.codex_path, owner=0)
        if (runtime.codex_version != '0.144.4' or runtime.codex_path.stat().st_mode & 0o022
                or hashlib.sha256(runtime.codex_path.read_bytes()).hexdigest() != runtime.codex_sha256):
            raise ExecutorBlocked('BUILDER_PINNED_RUNTIME_CHANGED')
        proof = _record(self.store, runtime.qualification_ref)
        denied = proof.get('denied_paths', {})
        if (proof.get('kind') != 'builder-tool-sandbox-qualification1'
                or proof.get('build_id') != runtime.build_id or proof.get('codex_sha256') != runtime.codex_sha256
                or proof.get('observed_runtime') is not True or proof.get('executor_uid') != 10002
                or proof.get('executor_gid') != 10002 or proof.get('sandbox') != 'workspace-write'
                or proof.get('approvals') != 'never' or proof.get('tool_network') != 'none'
                or not isinstance(denied, dict) or set(denied) != {'run_state', 'main_credential', 'fixture'}
                or not all(value is True for value in denied.values()) or not proof.get('evidence_refs')):
            raise ExecutorBlocked('BUILDER_ACTUAL_CLI_TOOL_QUALIFICATION_UNAVAILABLE')
        for ref in proof['evidence_refs']: _read(self.store, ref)
        # A JSON payload claiming actual observation is insufficient. The
        # independently completed producer must have protected store metadata
        # and exact real call/start/event/positive-control provenance.
        from .builder_qualification import validate_tool_qualification
        validate_tool_qualification(self.store, proof, runtime)
        BuilderCredentialLease.validate(runtime,self.store)
        failures = self.executor.prerequisites()
        if failures: raise ExecutorBlocked(';'.join(failures))

    def _join(self, protected, prompt, facts):
        for name in ('contract_ref', 'route_ref', 'model_call_start_ref', 'input_ref'):
            _read(self.store, protected.get(name))
        start = _record(self.store, protected['model_call_start_ref'])
        input_record = _record(self.store, protected['input_ref'])
        route = _record(self.store, protected['route_ref'])
        keys = ('contract_ref', 'invocation_id', 'execution_id', 'call_id', 'route_ref', 'input_ref')
        if (any(start.get(key) != protected.get(key) for key in keys)
                or any(facts.get(key) != protected.get(key) for key in ('contract_ref', 'invocation_id', 'execution_id'))
                or any(input_record.get(key) != protected.get(key) for key in ('run_id', 'invocation_id', 'call_id'))
                or input_record.get('prompt') != prompt or start.get('run_id') != protected.get('run_id')
                or route.get('run_id') != protected.get('run_id') or route.get('invocation_id') != protected.get('invocation_id')
                or route.get('route_id') != start.get('route_id') or protected.get('cc_name') != 'research.builder'):
            raise ExecutorBlocked('BUILDER_GOVERNED_CALL_JOIN_INVALID')
        contract = facts.get('contract')
        if not isinstance(contract, dict) or _record(self.store, protected['contract_ref']) != contract:
            raise ExecutorBlocked('BUILDER_FROZEN_CONTRACT_INVALID')
        authority = contract['bindings'][0].get('effective_authority',{})
        roots = authority.get('write_roots')
        if (not isinstance(roots,list) or not roots
                or any(root not in {'/workspace/poc','/workspace/poc/'} for root in roots)
                or authority.get('network') != 'none' or authority.get('network_allowlist') != []):
            raise ExecutorBlocked('BUILDER_EFFECTIVE_AUTHORITY_INVALID')
        return contract

    def _stage(self, protected, contract):
        root = self.runtime.workspace_root
        root.mkdir(mode=0o711, parents=False, exist_ok=True)
        _custody(root, owner=0, mode=0o711, directory=True)
        key = hashlib.sha256(json.dumps([protected['contract_ref'],protected['invocation_id'],protected['call_id']], sort_keys=True).encode()).hexdigest()
        parent = root / key
        parent.mkdir(mode=0o711)  # no after-start retry, reuse or foreign workspace
        workspace, resources = parent / 'work', parent / 'resources'
        workspace.mkdir(mode=0o700); os.chown(workspace,10002,10002)
        resources.mkdir(mode=0o755)
        for port in contract['inputs']:
            name = port['name']
            if name not in {'blueprint','baseline_resource','validation_resource','lock'}: continue
            if len(port['artifact_refs']) != 1: raise ExecutorBlocked('BUILDER_INPUT_INVENTORY_INVALID')
            raw = _read(self.store, port['artifact_refs'][0])
            value = json.loads(raw)
            target = resources / (name + '.json'); target.write_bytes(raw); target.chmod(0o444)
            if name.endswith('_resource'):
                directory = resources / name; directory.mkdir(mode=0o755)
                seen = set()
                for file in value['files']:
                    path = PurePosixPath(file['path'])
                    if (path.is_absolute() or '..' in path.parts or str(path) != file['path'] or path in seen):
                        raise ExecutorBlocked('BUILDER_RESOURCE_PATH_INVALID')
                    seen.add(path)
                    destination = directory.joinpath(*path.parts)
                    destination.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
                    destination.write_bytes(_read(self.store,file['artifact_ref'])); destination.chmod(0o444)
                for entry in sorted(directory.rglob('*'),reverse=True):
                    if entry.is_dir(): entry.chmod(0o555)
                directory.chmod(0o555)
        if {path.name for path in resources.glob('*.json')} != {'blueprint.json','baseline_resource.json','validation_resource.json','lock.json'}:
            raise ExecutorBlocked('BUILDER_REQUIRED_INPUT_MISSING')
        resources.chmod(0o555)
        return BuilderStage('builder-'+key[:48], parent, workspace, resources)

    def _command(self, stage, home, argv):
        # Share only the parent network for the CLI model connection. The
        # separately qualified Codex tool sandbox disables tool networking.
        command = [shutil.which('bwrap'),'--unshare-all','--share-net','--unshare-user','--die-with-parent','--new-session',
            '--clearenv','--uid','10002','--gid','10002','--cap-drop','ALL',
            '--ro-bind','/usr','/usr','--ro-bind','/usr/local','/usr/local','--ro-bind','/lib','/lib',
            '--proc','/proc','--dev','/dev','--tmpfs','/tmp','--dir','/workspace',
            '--bind',str(stage.workspace),'/workspace/poc','--ro-bind',str(stage.resources),'/resources',
            '--bind',str(home),'/builder-home','--chdir','/workspace/poc',
            '--setenv','PATH','/usr/local/bin:/usr/bin:/bin','--setenv','HOME','/builder-home',
            '--setenv','CODEX_HOME','/builder-home','--setenv','LANG','C.UTF-8']
        if Path('/lib64').exists(): command += ['--ro-bind','/lib64','/lib64']
        # DNS/CA configuration is immutable, not host credentials or run state.
        for path in ('/etc/resolv.conf','/etc/hosts','/etc/ssl/certs'):
            if Path(path).exists(): command += ['--ro-bind',path,path]
        probe = Path(__file__).with_name('_builder_probe.py')
        command += ['--ro-bind',str(probe),'/builder-probe.py','--','/usr/local/bin/python3','-I','/builder-probe.py',
            json.dumps({'uid':10002,'gid':10002,'parent_network_namespace':os.readlink('/proc/self/ns/net'),
                        'denied_paths':['/var/lib/ai4r','/var/lib/ai4r-accounts','/run/ai4r','/hidden-fixtures','/var/run/docker.sock']}),*argv]
        return command

    async def invoke(self, protected, prompt, *, timeout_s):
        if not isinstance(protected, dict) or not isinstance(prompt,str) or not prompt:
            raise ExecutorBlocked('BUILDER_PROTECTED_CALL_REQUIRED')
        facts = await _await(self.authorize(copy.deepcopy(protected)))
        contract = self._join(protected,prompt,facts)
        deadline = facts.get('execution_deadline_monotonic_s')
        if type(deadline) not in (int,float) or not math.isfinite(deadline):
            raise ExecutorBlocked('BUILDER_PROTECTED_DEADLINE_REQUIRED')
        declaration = _record(self.store,contract['bindings'][0]['declaration_ref'])
        if declaration.get('identity',{}).get('name') != 'research.builder':
            raise ExecutorBlocked('BUILDER_DECLARATION_BINDING_INVALID')
        budget = declaration['budget']['per_call']
        if budget['invocations'] != 1:
            raise ExecutorBlocked('BUILDER_SINGLE_CALL_REQUIRED')
        wall = min(timeout_s,protected['limits']['time_s'],contract['subnode_limits']['time_s'],
                   contract['bindings'][0]['limits']['time_s'],budget['wall_s'],600,deadline-time.monotonic())
        tools = budget['tool_calls']
        if not 0 < wall <= 600: raise ExecutorBlocked('BUILDER_WALL_BUDGET_EXHAUSTED')
        launch_deadline = min(deadline,time.monotonic()+wall)
        events = BuilderEvents(tools)
        self._qualify()
        claim = protected['invocation_id']
        if claim in self.claimed: raise ExecutorBlocked('BUILDER_CALL_REPLAY_DENIED')
        self.claimed.add(claim)
        stage = self._stage(protected,contract)
        self.stages[protected['invocation_id']] = stage
        lease = BuilderCredentialLease(self.runtime,self.store,stage)
        result = None
        argv = (str(self.runtime.codex_path), '--ask-for-approval','never','--sandbox','workspace-write',
            '-c','web_search="disabled"',
            '-c','sandbox_workspace_write.network_access=false','-c','sandbox_workspace_write.writable_roots=["/workspace/poc"]',
            'exec','--json','--ephemeral','--ignore-user-config','--ignore-rules','--skip-git-repo-check','-')
        requested_model = protected.get('requested_model')
        if requested_model is not None:
            if not isinstance(requested_model,str) or not re.fullmatch(r'[A-Za-z0-9_.:/-]+',requested_model):
                raise ExecutorBlocked('BUILDER_REQUESTED_MODEL_INVALID')
            argv = (*argv[:-1], '--model', requested_model, '-')
        memory_mb = min(self.runtime.memory_mb,protected['limits']['memory_mb'],contract['subnode_limits']['memory_mb'],
                        contract['bindings'][0]['limits']['memory_mb'])
        try:
            home = lease.open()
            command = self._command(stage,home,argv)
            remaining = launch_deadline-time.monotonic()
            if remaining <= 0: raise ExecutorBlocked('BUILDER_WALL_BUDGET_EXHAUSTED')
            job = BuilderKernelJob(stage.job_id,protected['contract_ref'],protected['invocation_id'],argv,remaining,
                                   memory_mb,self.runtime.pids_max)
            result = await self.executor._run_kernel(job,command,output_parent=stage.parent,
                stdin_bytes=prompt.encode('utf-8'),stdout_line_observer=events.feed,
                stdout_line_limit=self.runtime.max_event_bytes)
            proof = _record(self.store,result['observed_limits']['isolation_probe_ref'])
            if (proof.get('ready') is not True or proof.get('profile') != 'builder-parent'
                    or proof.get('executor_uid') != 10002 or proof.get('executor_gid') != 10002
                    or result.get('observed_runtime') is not True or result['contract_ref'] != protected['contract_ref']
                    or result['invocation_id'] != protected['invocation_id']
                    or not 0 < int(result['observed_limits']['memory_max']) <= memory_mb*1024*1024
                    or not 0 < int(result['observed_limits']['pids_max']) <= self.runtime.pids_max):
                result = dict(result,termination_reason='isolation_failure')
        except (ExecutorBlocked,OSError,asyncio.CancelledError) as exc:
            if stage.job_id not in getattr(self.executor,'owned_groups',{}):
                raise
            # A claimed kernel group with an incomplete lifecycle has uncertain
            # effects. Capture only bytes that actually exist; do not fabricate
            # empty logs, a stopped process tree or a successful identity probe.
            partial = {}
            directory = stage.parent/(stage.job_id+'.capture')
            for name in ('stdout','stderr'):
                path=directory/name
                try: fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
                except FileNotFoundError: continue
                with os.fdopen(fd,'rb') as stream:
                    metadata=os.fstat(stream.fileno())
                    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid!=0:
                        raise ExecutorBlocked('BUILDER_PARTIAL_CAPTURE_CUSTODY_INVALID') from None
                    partial[name+'_ref']=self.store.put_blob(stream.read(),media_type='text/plain')
            result={'termination_reason':'containment_unknown','exit_code':None,'identity':{},
                    'observed_runtime':True,'containment_error':type(exc).__name__,**partial}
        finally:
            # Kernel cancellation returns only after the complete owned cgroup
            # is empty. An uncertain cleanup must never report model success.
            lease.close()
            if result is not None:
                event_refs = [self.store.put_blob(line,media_type='application/x-ndjson') for line in events.events]
                terminal = result['termination_reason']
                if terminal == 'completed':
                    terminal = events.stop_reason or ('completed' if result['exit_code']==0 and events.success else 'invalid_output')
                observed = {'contract_ref':protected['contract_ref'],'invocation_id':protected['invocation_id'],
                    'execution_id':protected['execution_id'],'call_id':protected['call_id'],'event_refs':event_refs,
                    'output_refs':[result[key] for key in ('stdout_ref','stderr_ref') if key in result], 'tool_events':events.tools,
                    'tool_count':events.tool_count,'terminal_reason':terminal,'trial_executed':any(row['effect']=='trial' for row in events.tools),
                    'packages_installed':any(row['effect']=='package_install' for row in events.tools),
                    'route_ref':protected['route_ref'],'model_call_start_ref':protected['model_call_start_ref'],
                    'input_ref':protected['input_ref'],'identity':result['identity'],'cli_thread_id':events.thread_id,
                    'runtime_ref':self.runtime.qualification_ref,'kernel_receipt':result,
                    'credential_removed':not lease.home.exists(),'observed_runtime':True}
                self.observations[protected['invocation_id']] = copy.deepcopy(observed)
                ref = self.store.append_record('builder_execution',{**observed,'run_id':protected['run_id'],'node_id':protected['node_id']})
                _read(self.store,ref)
                self.receipt_refs[protected['invocation_id']] = ref
        observed = self.observations[protected['invocation_id']]
        terminal = observed['terminal_reason']
        return {'text':events.text if terminal=='completed' else None,
                'identity':{'effective':None,'basis':'Pinned CLI runtime; effective model not reported'},
                'usage':events.usage,'provider_request_id':None,'observed_runtime':True,
                'evidence_refs':[self.receipt_refs[protected['invocation_id']]],'terminal_reason':terminal,
                'outcome':'completed' if terminal=='completed' else 'outcome_unknown' if terminal=='containment_unknown' else 'failed',
                'error_code':None if terminal=='completed' else 'CONTAINMENT_UNCERTAIN' if terminal=='containment_unknown'
                    else terminal if terminal in {'timeout','cancelled','provider_error','budget_exceeded'} else 'invalid_output'}

    async def builder_observation(self, contract, *, binding):
        observed = self.observations.get(binding.invocation_id)
        if (binding.contract != contract or observed is None or observed['contract_ref'] != binding.contract_ref):
            raise ExecutorBlocked('BUILDER_RUNTIME_OBSERVATION_UNAVAILABLE')
        return copy.deepcopy(observed)

    async def collect_builder(self, contract, *, binding):
        observed = await self.builder_observation(contract,binding=binding)
        if observed['terminal_reason'] != 'completed' or not observed['credential_removed']:
            raise ExecutorBlocked('BUILDER_CALL_NOT_ACCEPTABLE')
        stage = self.stages[binding.invocation_id]
        names = {path.name for path in stage.workspace.iterdir()}
        if names != FILES: raise ExecutorBlocked('BUILDER_EXACT_THREE_FILES_REQUIRED')
        files = {}
        for name in sorted(FILES):
            path = stage.workspace / name
            fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            with os.fdopen(fd,'rb') as source:
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 1024*1024:
                    raise ExecutorBlocked('BUILDER_OUTPUT_FILE_INVALID')
                files[name] = source.read(1024*1024+1)
                if len(files[name]) > 1024*1024: raise ExecutorBlocked('BUILDER_OUTPUT_BUNDLE_TOO_LARGE')
        if sum(map(len,files.values())) > 1024*1024:
            raise ExecutorBlocked('BUILDER_OUTPUT_BUNDLE_TOO_LARGE')
        return files


def create_builder_launcher(*, store, executor, authorize, environ, build_id):
    """Production assembly, called only inside the protected executor broker."""
    locator = environ.get('JIUWENSWARM_M1_BUILDER_BINDINGS')
    if not locator: return None
    if os.name != 'posix' or os.geteuid() != 0:
        raise ExecutorBlocked('BUILDER_ROOT_BROKER_REQUIRED')
    path = Path(locator)
    _custody(path,owner=0)
    if path.stat().st_mode & 0o022 or path.stat().st_size > 65536:
        raise ExecutorBlocked('BUILDER_BINDING_LOCATOR_CUSTODY_INVALID')
    value = json.loads(path.read_bytes())
    if not isinstance(value,dict) or set(value) != {'binding_ref'}:
        raise ExecutorBlocked('BUILDER_BINDING_LOCATOR_INVALID')
    runtime = BuilderRuntime.from_capture(store,value['binding_ref'],build_id=build_id)
    launcher = BuilderLauncher(store=store,executor=executor,runtime=runtime,authorize=authorize)
    launcher._qualify()
    return launcher
