"""Node checks: the host verifies every output of a task graph node before the node can be done.

A node's ``check`` lists its outputs, one verifier each, like M1's one verifier subnode
per output. Nodes planned from node contracts get it from their contract
(``node_contract.check_spec``); a hand-written node can carry the short form
``{verifier, stage, review}``, which means one ``diff`` output named ``change``; a task
can set one per node kind in ``constraints.node_checks``.

The done rule: a checked node closes only by citing, for every required output, the
latest ``node_check`` observation of that output, and that check must have passed with
the same settings. Only the host writes those observations.

How each output kind is checked, cheapest first:

* ``diff``: the capsule's own ``verify`` capability on the exact change (sealed release,
  digests recomputed), up to a required stage; then, if asked, an **independent
  reviewer**. The reviewer reads a packet with only the node's objective and criteria,
  the capsule's method materials, the verifier's checks and the diff. It runs in its own
  process and session, in an empty directory, with no factory environment, so the agent
  that made a change never approves it. A blocker finding fails the check. Review runs
  only after the verifier passes. A reviewer needs no capsule: the node's criteria are
  enough, and the capsule's method makes it sharper when there is one.
* ``source_bundle``: each named lab source bundle is stored, readable and intact.
* ``image``: a successful build attempt of this task whose receipt names the image.
* ``lab_request``: a request sent through the lab manager from this node, whose lab task
  covers the node's arms, checks and metrics.
* ``evidence``: the cited records exist in this task.

Diff checks run in the background (a reviewer can take minutes) and are cached by the
exact work, settings and reviewer. Host checks run at once. Expensive evidence (real-model
parity, speed) belongs to the lab, after the deliver node.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

import yaml

KIND = 'node_check'
FORMAT = 'factory.node-check/2'
SHORT_FIELDS = {'verifier', 'stage', 'review'}
OUTPUT_FIELDS = {'name', 'kind', 'required', 'verifier', 'stage', 'review', 'criteria'}
OUTPUT_KINDS = ('diff', 'source_bundle', 'image', 'lab_request', 'evidence')
# Evidence ladder used by the capsule verifiers (see each VALIDATION.md), weakest first.
STAGES = ('fixture', 'native CC execution', 'compile', 'runtime acceptance', 'hardware measurement')
VERIFIER_GRANTS = ['workspace.read', 'process.exec']
MAX_DIFF = int(os.environ.get('FACTORY_REVIEW_MAX_DIFF', 120_000))
MAX_MATERIAL = 24_000
REVIEW_MATERIALS = ('method', 'validation', 'guide')
SEVERITIES = ('blocker', 'major', 'minor')
REVIEW_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['verdict', 'summary', 'findings'],
    'properties': {
        'verdict': {'enum': ['pass', 'fail']},
        'summary': {'type': 'string'},
        'findings': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False, 'required': ['severity', 'file', 'line', 'problem'],
            'properties': {'severity': {'enum': list(SEVERITIES)}, 'file': {'type': 'string'},
                           'line': {'type': ['integer', 'null']}, 'problem': {'type': 'string'}}}}}}


class CheckError(ValueError):
    pass


def _sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else json.dumps(data, sort_keys=True).encode()).hexdigest()


# ---- the check spec and the done rule ---------------------------------------------------
def _capability(value):
    return isinstance(value, str) and value.count('.') >= 2 and all(value.split('.'))


def _check_output(entry):
    if not isinstance(entry, dict) or set(entry) - OUTPUT_FIELDS or not isinstance(entry.get('name'), str) or not entry['name']:
        raise ValueError(f'A check output has fields {sorted(OUTPUT_FIELDS)} and a name')
    if entry.get('kind') not in OUTPUT_KINDS:
        raise ValueError(f'Check output {entry["name"]}: kind is one of {", ".join(OUTPUT_KINDS)}')
    if entry.get('verifier') is not None and not _capability(entry['verifier']):
        raise ValueError('A check verifier is a capsule capability such as engine.build_x.verify')
    if entry.get('stage') is not None and (entry['stage'] not in STAGES or not entry.get('verifier')):
        raise ValueError(f'A check stage needs a verifier and is one of: {", ".join(STAGES)}')
    for flag in ('review', 'required'):
        if flag in entry and type(entry[flag]) is not bool:
            raise ValueError(f'Check {flag} must be true or false')
    if entry['kind'] != 'diff' and entry.get('verifier'):
        raise ValueError(f'Check output {entry["name"]}: capsule verifiers check diff outputs')
    if entry.get('review') and entry['kind'] not in ('diff', 'evidence'):
        raise ValueError(f'Check output {entry["name"]}: reviews read diffs and evidence; '
                         f'{entry["kind"]} outputs are checked by the host')
    if 'criteria' in entry and (not isinstance(entry['criteria'], list) or not all(isinstance(c, str) and c for c in entry['criteria'])):
        raise ValueError('Check criteria are a list of sentences')


def validate_spec(spec):
    """A node check: {outputs: [...]} or the short diff form {verifier?, stage?, review?}."""
    if isinstance(spec, dict) and 'outputs' in spec:
        if set(spec) != {'outputs'} or not isinstance(spec['outputs'], list) or not spec['outputs']:
            raise ValueError('A node check is {"outputs": [...]} with at least one output')
        for entry in spec['outputs']:
            _check_output(entry)
        names = [e['name'] for e in spec['outputs']]
        if len(set(names)) != len(names):
            raise ValueError('Check output names must be unique')
        return spec
    if not isinstance(spec, dict) or set(spec) - SHORT_FIELDS:
        raise ValueError('Node check fields are outputs, or verifier, stage and review')
    if not spec.get('verifier') and not spec.get('review'):
        raise ValueError('A node check needs a verifier, a review or both')
    _check_output(dict(name='change', kind='diff', **spec))
    return spec


def outputs_of(spec):
    """The checked outputs of a spec, short form expanded."""
    if 'outputs' in spec:
        return spec['outputs']
    return [dict(name='change', kind='diff', **spec)]


def effective_spec(task, node):
    """The node's own check, or the task's default for the node's kind."""
    if node.get('check'):
        return node['check']
    constraints = task.get('constraints')
    defaults = constraints.get('node_checks') if isinstance(constraints, dict) else None
    spec = (defaults or {}).get(node['kind'])
    return validate_spec(spec) if spec else None


def checks_for(host, task_id, node_id, output=None):
    rows = host._db.execute('SELECT obs_id, "values", source_artifacts FROM observations WHERE task_id=? AND kind=? '
                            'ORDER BY created, rowid', (task_id, KIND))
    found = []
    for obs_id, values, artifacts in rows:
        values = json.loads(values)
        if values.get('node_id') == node_id and (output is None or values.get('output', 'change') == output):
            found.append(dict(values, obs_id=obs_id, source_artifacts=json.loads(artifacts or '[]')))
    return found


def pending(host, task, node):
    """Why this node cannot be done yet, or None. Called inside the plan transaction."""
    spec = effective_spec(task, node)
    if not spec:
        return None
    reasons = []
    for entry in outputs_of(spec):
        if not entry.get('required', True):
            continue
        checks = checks_for(host, task['task_id'], node['node_id'], entry['name'])
        name = entry['name']
        if not checks:
            reasons.append(f'output {name} needs a passing node check (node_check.start)')
            continue
        latest = checks[-1]
        if latest.get('state') != 'finished':
            reasons.append(f"output {name}: node check {latest['obs_id']} has not finished")
        elif latest.get('entry') != entry:
            reasons.append(f"output {name}: the latest node check {latest['obs_id']} used other check settings")
        elif not latest['passed']:
            reasons.append(f"output {name}: the latest node check {latest['obs_id']} failed: {latest['reason']}")
        elif latest['obs_id'] not in node['evidence_ids']:
            reasons.append(f"output {name}: cite the latest passing node check {latest['obs_id']} in evidence_ids")
    return '; '.join(reasons) or None


def gate(host, task_id, before, after):
    """Refuse a patch that marks a checked node done without its passing checks."""
    task = host.get_task(task_id)
    for key, node in after.items():
        if node['state'] == 'done' and (before.get(key) or {}).get('state') != 'done':
            reason = pending(host, task, node)
            if reason:
                raise ValueError(f'Node {key} cannot be done: {reason}')


# ---- what is checked --------------------------------------------------------------------
def _git(checkout, *args, env=None, binary=False):
    done = subprocess.run(['git', '-C', str(checkout), *args], capture_output=True, env=env, check=False)
    if done.returncode:
        raise CheckError(f'git {args[0]} failed: {done.stderr.decode(errors="replace").strip()[:300]}')
    return done.stdout if binary else done.stdout.decode().strip()


def working_diff(checkout):
    """Staged, unstaged and untracked changes against HEAD, without touching the index."""
    with tempfile.TemporaryDirectory() as scratch:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(scratch) / 'index'))
        _git(checkout, 'read-tree', 'HEAD', env=env)
        _git(checkout, 'add', '-A', env=env)
        tree = _git(checkout, 'write-tree', env=env)
    return _git(checkout, 'diff', '--binary', '--full-index', '--no-renames', 'HEAD', tree, binary=True)


def capsule_folder(cc_id, roots=None):
    ccs = Path(__file__).resolve().parent / 'ccs'
    for root in roots or [ccs, ccs / 'expert_streaming/components']:
        for declaration in sorted(Path(root).glob('*/cc.yaml')):
            try:
                if yaml.safe_load(declaration.read_text(encoding='utf-8')).get('id') == cc_id:
                    return declaration.parent
            except yaml.YAMLError:
                continue
    raise CheckError(f'No capsule {cc_id}')


def _split(capability):
    cc_id, _, name = capability.rpartition('.')
    return cc_id, name


def _materials(bundle, declaration, names):
    out = {}
    for name in names:
        material = (declaration.get('materials') or {}).get(name)
        if not material:
            continue
        text = (Path(bundle) / material['path']).read_text(encoding='utf-8', errors='replace')
        out[name] = text if len(text) <= MAX_MATERIAL else text[:MAX_MATERIAL] + '\n[... truncated by the host]'
    return out


def assess(receipt, stage):
    """Pass/fail from a verifier receipt; never from the agent's account of it."""
    outputs = receipt.get('outputs') or {}
    if receipt.get('state') != 'succeeded':
        return False, None, f"verifier call {receipt.get('state')}: {receipt.get('reason')}"
    flag = outputs.get('done', outputs.get('verified'))
    if type(flag) is not bool:
        return False, None, 'the verifier gave no pass/fail output (done or verified)'
    checks = [c for c in outputs.get('checks') or [] if isinstance(c, dict)]
    failed = [c.get('name', '?') for c in checks if c.get('status') == 'fail']
    reached = max((STAGES.index(c['stage']) for c in checks if c.get('status') == 'pass' and c.get('stage') in STAGES),
                  default=None)
    reached_name = STAGES[reached] if reached is not None else None
    if failed:
        return False, reached_name, 'verifier checks failed: ' + ', '.join(failed)
    if not flag:
        return False, reached_name, 'the verifier reported not done'
    if stage and (reached is None or reached < STAGES.index(stage)):
        return False, reached_name, f'the verifier reached {reached_name or "no stage"}, the node needs {stage}'
    return True, reached_name, 'verifier passed'


# ---- the independent reviewer -----------------------------------------------------------
REVIEW_INSTRUCTIONS = '''You are an independent reviewer in a software factory. Another agent made the change below
to complete one step of a task. You did not write it and you have not seen that agent's
reasoning. Judge the change only against the step, its criteria and the method given here.

Look for:
- whether the diff does what the step asks and meets each criterion;
- anything the method requires that is missing (for example: off by default, a switch,
  log markers, a fallback, limits on scope);
- real bugs: wrong logic, missing bounds checks, memory or lifetime errors, races,
  unhandled errors, changed behaviour when the feature is off;
- anything the automatic verifier below could not see (it reads source text only).

Judge only the output this step owes. Later steps build the engine, run it and measure it,
and a lab tests it; do not fail this step because their evidence is not here yet. If the
method asks for such evidence, say which later step must supply it, as "minor".

Do not ask for style changes. A "blocker" means this output is wrong or unsafe as it
stands (it breaks a criterion, can crash, corrupt data or change behaviour when the feature
is off); "major" means it should be fixed but the step can stand; "minor" is advice.
Everything you need is in this message; do not run commands or look for other files.

Reply with JSON only, matching this schema:
{schema}
'''


def review_prompt(packet):
    parts = [REVIEW_INSTRUCTIONS.format(schema=json.dumps(REVIEW_SCHEMA))]
    parts.append('## Task objective\n' + packet['objective'])
    parts.append('## Step to check\n' + json.dumps(packet['step'], indent=1))
    if packet.get('criteria'):
        parts.append('## Criteria for this output\n' + '\n'.join(f'- {c}' for c in packet['criteria']))
    for name, text in packet['materials'].items():
        parts.append(f'## Method material: {name}\n{text}')
    if packet.get('verifier') is not None:
        parts.append('## Automatic verifier result\n' + json.dumps(packet['verifier'], indent=1))
    note = ' (truncated by the host; judge what is shown and say so)' if packet['diff_truncated'] else ''
    if packet.get('subject') == 'records':
        parts.append(f'## Records the output consists of{note}\n```json\n{packet["diff"]}\n```')
    else:
        parts.append(f'## Diff{note}\n```diff\n{packet["diff"]}\n```')
    return '\n\n'.join(parts)


def parse_review(text):
    text = text.strip()
    fenced = re.search(r'```(?:json)?\s*(\{.*\})\s*```', text, re.S)
    if fenced:
        text = fenced.group(1)
    elif not text.startswith('{') and '{' in text:
        text = text[text.index('{'):text.rindex('}') + 1]
    try:
        reply = json.loads(text)
    except ValueError:
        raise CheckError('the reviewer reply is not JSON') from None
    if (not isinstance(reply, dict) or reply.get('verdict') not in ('pass', 'fail')
            or not isinstance(reply.get('findings'), list) or not isinstance(reply.get('summary', ''), str)):
        raise CheckError('the reviewer reply does not match the review schema')
    findings = []
    for finding in reply['findings']:
        if not isinstance(finding, dict) or finding.get('severity') not in SEVERITIES or not isinstance(finding.get('problem'), str):
            raise CheckError('a reviewer finding does not match the review schema')
        findings.append({k: finding.get(k) for k in ('severity', 'file', 'line', 'problem')})
    return dict(verdict=reply['verdict'], summary=reply.get('summary', ''), findings=findings)


def review_passes(review):
    blockers = [f for f in review['findings'] if f['severity'] == 'blocker']
    if review['verdict'] == 'pass' and not blockers:
        return True, 'reviewer passed'
    if blockers:
        return False, f'reviewer found {len(blockers)} blocker(s): ' + '; '.join(f['problem'][:160] for f in blockers[:3])
    return False, 'reviewer verdict fail: ' + review['summary'][:300]


def _clean_env():
    """The reviewer gets no handle on the factory: no store, task, workspace or agent wiring."""
    return {k: v for k, v in os.environ.items() if not k.startswith(('FACTORY_', 'JIUWENSWARM_', 'CCV2_', 'JOBQ_'))}


class CommandReviewer:
    """Any command that reads the prompt on stdin and prints the reply."""
    def __init__(self, command, timeout=600):
        self.argv = shlex.split(command) if isinstance(command, str) else list(command)
        self.timeout, self.identity = timeout, 'cmd:' + ' '.join(self.argv)

    def __call__(self, prompt):
        with tempfile.TemporaryDirectory(prefix='factory-review-') as empty:
            done = subprocess.run(self.argv, input=prompt, capture_output=True, text=True, encoding='utf-8',
                                  timeout=self.timeout, cwd=empty, env=_clean_env())
        if done.returncode:
            raise CheckError(f'reviewer command exited {done.returncode}: {done.stderr.strip()[-300:]}')
        return done.stdout


class CodexReviewer:
    """A fresh, ephemeral Codex session in a read-only sandbox and an empty directory."""
    def __init__(self, model=None, timeout=600, codex='codex'):
        self.model, self.timeout, self.codex = model, timeout, codex
        self.identity = 'codex-exec' + (f':{model}' if model else '')

    def __call__(self, prompt):
        with tempfile.TemporaryDirectory(prefix='factory-review-') as empty:
            schema, reply = Path(empty) / '.schema.json', Path(empty) / '.reply.json'
            schema.write_text(json.dumps(REVIEW_SCHEMA))
            argv = [self.codex, 'exec', '--ephemeral', '--skip-git-repo-check', '-s', 'read-only', '-C', empty,
                    '--output-schema', str(schema), '-o', str(reply)]
            if self.model:
                argv += ['-m', self.model]
            done = subprocess.run(argv + ['-'], input=prompt, capture_output=True, text=True, encoding='utf-8',
                                  timeout=self.timeout, cwd=empty, env=_clean_env())
            if done.returncode:
                raise CheckError(f'codex exec exited {done.returncode}: {done.stderr.strip()[-300:]}')
            return reply.read_text(encoding='utf-8') if reply.exists() else done.stdout


class OpenAIReviewer:
    """Any OpenAI-compatible /chat/completions endpoint, standard library only."""
    def __init__(self, base_url, model, timeout=600, api_key_env='FACTORY_REVIEW_API_KEY'):
        self.url, self.model, self.timeout, self.api_key_env = base_url.rstrip('/') + '/chat/completions', model, timeout, api_key_env
        self.identity = f'openai:{base_url.rstrip("/")}|{model}'

    def __call__(self, prompt):
        body = json.dumps({'model': self.model, 'temperature': 0, 'messages': [{'role': 'user', 'content': prompt}]}).encode()
        headers = {'Content-Type': 'application/json'}
        if os.environ.get(self.api_key_env):
            headers['Authorization'] = 'Bearer ' + os.environ[self.api_key_env]
        with urllib.request.urlopen(urllib.request.Request(self.url, body, headers), timeout=self.timeout) as reply:
            return json.loads(reply.read().decode())['choices'][0]['message']['content']


def default_reviewer():
    """FACTORY_REVIEW_CMD, then an OpenAI-compatible endpoint, then the codex CLI; else None."""
    timeout = float(os.environ.get('FACTORY_REVIEW_TIMEOUT', 600))
    if os.environ.get('FACTORY_REVIEW_CMD'):
        return CommandReviewer(os.environ['FACTORY_REVIEW_CMD'], timeout)
    if os.environ.get('FACTORY_REVIEW_OPENAI_BASE_URL'):
        if not os.environ.get('FACTORY_REVIEW_MODEL'):
            raise CheckError('FACTORY_REVIEW_OPENAI_BASE_URL needs FACTORY_REVIEW_MODEL')
        return OpenAIReviewer(os.environ['FACTORY_REVIEW_OPENAI_BASE_URL'], os.environ['FACTORY_REVIEW_MODEL'], timeout)
    if shutil.which('codex'):
        return CodexReviewer(os.environ.get('FACTORY_REVIEW_MODEL'), timeout)
    return None


# ---- running a check --------------------------------------------------------------------
class NodeChecks:
    def __init__(self, store, reviewer=None, ccs_roots=None):
        self.store, self.ccs_roots = store, ccs_roots
        self._reviewer = reviewer

    @property
    def reviewer(self):
        if self._reviewer is None:
            self._reviewer = default_reviewer()
        return self._reviewer

    def _root(self):
        return self.store.home / 'node-checks'

    def _node(self, task_id, node_id):
        from .taskgraph import plan_get
        nodes = {n['node_id']: n for n in plan_get(self.store, task_id)['nodes']}
        if node_id not in nodes:
            raise CheckError(f'No node {node_id}')
        node = nodes[node_id]
        if node['state'] in {'done', 'cancelled', 'superseded'}:
            raise CheckError(f'Node {node_id} is {node["state"]}')
        return node

    def _entry(self, task, node, output):
        spec = effective_spec(task, node)
        if not spec:
            raise CheckError(f'Node {node["node_id"]} has no check; plan it from a node contract or add one')
        entries = outputs_of(spec)
        if output is None:
            if len(entries) != 1:
                raise CheckError(f'Node {node["node_id"]} checks several outputs; name one of: ' + ', '.join(e['name'] for e in entries))
            return entries[0]
        for entry in entries:
            if entry['name'] == output:
                return entry
        raise CheckError(f'Node {node["node_id"]} has no checked output {output}')

    def start(self, task_id, node_id, output=None, checkout=None, diff_path=None, verifier_inputs=None, refs=None,
              background=True):
        """Check one output of a node. Diffs run in the background; host checks run at once."""
        task = self.store.get_task(task_id)
        node = self._node(task_id, node_id)
        entry = self._entry(task, node, output)
        if entry['kind'] != 'diff':
            if checkout or diff_path or verifier_inputs:
                raise CheckError(f'Output {entry["name"]} is a {entry["kind"]}; pass refs, not a checkout')
            if entry['kind'] == 'evidence' and entry.get('review'):
                return self._start_records(task, node, entry, refs, background)
            return self._result(self.host_check(task, node, entry, refs))
        if not checkout:
            raise CheckError(f'Output {entry["name"]} is a diff: pass the checkout')
        return self._start_diff(task, node, entry, checkout, diff_path, verifier_inputs, background)

    # -- diff outputs --------------------------------------------------------------------
    def _start_diff(self, task, node, entry, checkout, diff_path, verifier_inputs, background):
        task_id, node_id = task['task_id'], node['node_id']
        checkout = Path(checkout).expanduser().resolve()
        head = _git(checkout, 'rev-parse', 'HEAD')
        diff = Path(diff_path).expanduser().read_bytes() if diff_path else working_diff(checkout)
        if not diff.strip():
            raise CheckError('There is no change to check')
        verifier = None
        if entry.get('verifier'):
            from jiuwenswarm.ccv2.ccv2 import Host
            cc_id, capability = _split(entry['verifier'])
            host = Host(self.store.home / 'ccstore')
            release = host.prepare(capsule_folder(cc_id, self.ccs_roots))
            release = release['release'] if isinstance(release, dict) else release
            declaration, _ = host.release(release)
            if capability not in declaration['capabilities']:
                raise CheckError(f'{cc_id} has no capability {capability}')
            verifier = dict(cc=cc_id, capability=capability, release=release)
        reviewer = None
        if entry.get('review'):
            if self.reviewer is None:
                raise CheckError('No reviewer is configured (FACTORY_REVIEW_CMD, FACTORY_REVIEW_OPENAI_BASE_URL or codex on PATH)')
            reviewer = self.reviewer.identity
        diff_sha = _sha(diff)
        key = _sha(dict(task=task_id, node=node_id, entry=entry, head=head, diff=diff_sha, working=not diff_path,
                        verifier=verifier, inputs=verifier_inputs or {}, reviewer=reviewer))
        request = dict(format=FORMAT, key=key, task_id=task_id, node_id=node_id, output=entry['name'], entry=entry,
                       kind='diff', checkout=str(checkout), head=head, working=not diff_path, diff_sha256=diff_sha,
                       diff_bytes=len(diff), verifier=verifier, verifier_inputs=verifier_inputs or {}, reviewer=reviewer)
        return self._launch(request, diff, background)

    def _start_records(self, task, node, entry, refs, background):
        """An evidence output with review: the host checks the records exist, then a reviewer reads them."""
        try:
            self._evidence(task, node, refs)
        except (CheckError, ValueError) as exc:
            values = dict(format=FORMAT, node_id=node['node_id'], output=entry['name'], kind='evidence', entry=entry,
                          key=_sha(dict(node=node['node_id'], entry=entry, refs=refs)), state='finished', passed=False,
                          refs=refs, reason=str(exc), seconds={}, started=time.time())
            return self._result(self._close(task['task_id'], node['node_id'], values, []))
        if self.reviewer is None:
            raise CheckError('No reviewer is configured (FACTORY_REVIEW_CMD, FACTORY_REVIEW_OPENAI_BASE_URL or codex on PATH)')
        records = [self.store.read(task['task_id'], ref) for ref in refs['evidence_ids']]
        subject = json.dumps(records, indent=1, sort_keys=True, default=str).encode()
        key = _sha(dict(task=task['task_id'], node=node['node_id'], entry=entry, records=_sha(subject),
                        reviewer=self.reviewer.identity))
        request = dict(format=FORMAT, key=key, task_id=task['task_id'], node_id=node['node_id'], output=entry['name'],
                       entry=entry, kind='evidence', refs=refs, head=None, working=False, diff_sha256=_sha(subject),
                       diff_bytes=len(subject), verifier=None, verifier_inputs={}, reviewer=self.reviewer.identity)
        return self._launch(request, subject, background)

    def _launch(self, request, subject, background):
        task_id, node_id, entry, key = request['task_id'], request['node_id'], request['entry'], request['key']
        work = self._root() / key[:32]
        work.mkdir(parents=True, exist_ok=True)
        (work / 'patch.diff').write_bytes(subject)
        (work / 'request.json').write_text(json.dumps(request, indent=1))
        cached = self._finished(task_id, node_id, entry['name'], key)
        if cached:
            return self._result(cached, cached=True)
        claim = work / 'running'
        try:
            fd = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(time.time()).encode())
            os.close(fd)
        except FileExistsError:
            if time.time() - claim.stat().st_mtime < float(os.environ.get('FACTORY_REVIEW_TIMEOUT', 600)) + 900:
                return dict(check_id=key[:32], node_id=node_id, output=entry['name'], state='running')
            claim.write_text(str(time.time()))  # a stale claim from a worker that died
        if not background:
            return self._result(self.work(work))
        log = (work / 'worker.log').open('ab')
        subprocess.Popen([sys.executable, '-m', 'jiuwenswarm.factory.node_check', 'work', str(work)],
                         stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
                         env=dict(os.environ, FACTORY_HOME=str(self.store.home), PYTHONPATH=os.pathsep.join(
                             filter(None, [str(Path(__file__).resolve().parents[2]), os.environ.get('PYTHONPATH')]))))
        return dict(check_id=key[:32], node_id=node_id, output=entry['name'], state='running')

    def _finished(self, task_id, node_id, output, key):
        checks = checks_for(self.store, task_id, node_id, output)
        same = [c for c in checks if c.get('key') == key and c.get('state') == 'finished']
        if not same:
            return None
        if checks[-1]['obs_id'] == same[-1]['obs_id']:
            return same[-1]
        # The same work was checked before a different one; record it again so it is the latest.
        values = {k: v for k, v in same[-1].items() if k not in ('obs_id', 'source_artifacts')} | dict(reused_from=same[-1]['obs_id'])
        return self._record(task_id, node_id, values, same[-1]['source_artifacts'])

    def _record(self, task_id, node_id, values, artifacts):
        seq = len(checks_for(self.store, task_id, node_id)) + 1
        limits = ('Host-run checks of one node output: a capsule verifier and an independent reviewer with a separate '
                  'context for changes, host record checks for builds and lab requests. None runs the real model or measures speed.')
        row = self.store.append_observation(task_id, dict(
            obs_id=f'node-check:{node_id}:{values["output"]}:{seq}:{values["key"][:8]}', kind=KIND, values=values,
            source_artifacts=artifacts, limitations=limits))
        return dict(row['values'], obs_id=row['obs_id'], source_artifacts=artifacts)

    def work(self, work):
        """Run a prepared diff check; always records an observation, pass or fail."""
        work = Path(work)
        request = json.loads((work / 'request.json').read_text())
        task_id, node_id, entry = request['task_id'], request['node_id'], request['entry']
        diff = (work / 'patch.diff').read_bytes()
        values = dict(format=FORMAT, node_id=node_id, output=entry['name'], kind=request['kind'], entry=entry, key=request['key'],
                      state='finished', passed=False, head=request['head'], diff_sha256=request['diff_sha256'],
                      diff_bytes=request['diff_bytes'], verifier=None, review=None, seconds={}, started=time.time())
        artifacts = []
        try:
            if _sha(diff) != request['diff_sha256']:
                raise CheckError('the diff changed after the check was requested')
            if request['kind'] == 'diff':
                artifacts.append(self.store.put_artifact(task_id, f'node-check-{request["key"][:24]}-diff', diff,
                                                         'text/x-diff', None)['artifact_id'])
            else:
                values['refs'] = request['refs']
            if request['verifier']:
                t = time.time()
                values['verifier'] = self._verify(request, work)
                values['seconds']['verifier'] = round(time.time() - t, 3)
                if not values['verifier']['passed']:
                    values['reason'] = values['verifier']['reason']
                    return self._close(task_id, node_id, values, artifacts, work)
            if entry.get('review'):
                t = time.time()
                values['review'], reply_artifacts = self._review(request, diff, values['verifier'])
                artifacts += reply_artifacts
                values['seconds']['review'] = round(time.time() - t, 3)
                if not values['review']['passed']:
                    values['reason'] = values['review']['reason']
                    return self._close(task_id, node_id, values, artifacts, work)
            values.update(passed=True, reason='passed')
        except (CheckError, OSError, subprocess.TimeoutExpired) as exc:
            values['reason'] = f'check could not run: {exc}'
        return self._close(task_id, node_id, values, artifacts, work)

    def _close(self, task_id, node_id, values, artifacts, work=None):
        values['seconds']['total'] = round(time.time() - values['started'], 3)
        row = self._record(task_id, node_id, values, artifacts)
        if work is not None:
            try:
                (Path(work) / 'running').unlink()
            except FileNotFoundError:
                pass
        return row

    def _same_work(self, request):
        """The checkout still holds exactly the work the check was asked about."""
        if _git(request['checkout'], 'rev-parse', 'HEAD') != request['head']:
            raise CheckError('the checkout moved to another commit after the check was requested')
        if request['working'] and _sha(working_diff(request['checkout'])) != request['diff_sha256']:
            raise CheckError('the checkout changed after the check was requested')

    def _verify(self, request, work):
        from jiuwenswarm.ccv2.ccv2 import Host
        verifier = request['verifier']
        host = Host(self.store.home / 'ccstore')
        declaration, _ = host.release(verifier['release'])
        capability = declaration['capabilities'][verifier['capability']]
        takes = capability['takes']
        self._same_work(request)
        inputs = dict(request['verifier_inputs'])
        if 'checkout' in takes:
            inputs['checkout'] = request['checkout']
        # Uncommitted work is already in the checkout: the verifier reads it there. A patch
        # file is checked against the checkout it applies to.
        if 'diff_path' in takes and not request['working']:
            inputs['diff_path'] = str(Path(work) / 'patch.diff')
        receipt = host.call(verifier['release'], verifier['capability'], inputs, key='node-check-' + request['key'],
                            grants=sorted(set(VERIFIER_GRANTS) & set(capability['changes'])),
                            timeout=float(os.environ.get('FACTORY_VERIFY_TIMEOUT', 900)))
        self._same_work(request)
        passed, reached, reason = assess(receipt, request['entry'].get('stage'))
        outputs = receipt.get('outputs') or {}
        return dict(cc=verifier['cc'], capability=verifier['capability'], release=verifier['release'],
                    call=receipt.get('call'), state=receipt.get('state'), passed=passed, stage_reached=reached,
                    reason=reason, checks=[{k: c.get(k) for k in ('name', 'status', 'stage', 'detail')}
                                           for c in outputs.get('checks') or [] if isinstance(c, dict)])

    def _review(self, request, diff, verifier):
        task = self.store.get_task(request['task_id'])
        from .taskgraph import plan_get
        node = next(n for n in plan_get(self.store, request['task_id'])['nodes'] if n['node_id'] == request['node_id'])
        entry = request['entry']
        step = {k: node.get(k) for k in ('node_id', 'kind', 'title', 'capability', 'engine_slice', 'node_contract') if node.get(k)}
        step['output'] = entry['name']
        contract_node = None
        if node.get('node_contract'):
            from .node_contract import for_task, node as contract_node_of
            try:
                contract_node = contract_node_of(for_task(task), node['node_contract'])
            except (ValueError, OSError):
                contract_node = None
        if contract_node:
            step['objective'] = contract_node['objective']
            step['requirement_ids'] = contract_node.get('requirement_ids', [])
        ccs = [_split(entry['verifier'])[0]] if entry.get('verifier') else []
        ccs += (contract_node or {}).get('work', {}).get('helpful_ccs', [])
        if not ccs and node.get('capability'):
            ccs = [_split(node['capability'])[0]]
        materials = {}
        for cc_id in dict.fromkeys(ccs):
            try:
                folder = capsule_folder(cc_id, self.ccs_roots)
            except CheckError:
                continue
            found = _materials(folder, yaml.safe_load((folder / 'cc.yaml').read_text(encoding='utf-8')), REVIEW_MATERIALS)
            if found:  # the first capsule with a method is the one the change follows
                materials = {f'{cc_id} {k}': v for k, v in found.items()}
                break
        text = diff.decode('utf-8', errors='replace')
        packet = dict(objective=task['objective'], step=step, criteria=entry.get('criteria', []),
                      subject='records' if request['kind'] == 'evidence' else 'diff',
                      materials=materials, diff=text[:MAX_DIFF], diff_truncated=len(text) > MAX_DIFF,
                      verifier=None if verifier is None else {k: verifier[k] for k in ('cc', 'passed', 'stage_reached', 'checks')})
        prompt = review_prompt(packet)
        reviewer = self.reviewer
        if reviewer is None or reviewer.identity != request['reviewer']:
            raise CheckError('the configured reviewer changed after the check was requested')
        key = request['key'][:24]
        packet_artifact = self.store.put_artifact(request['task_id'], f'node-check-{key}-review-packet', prompt.encode(),
                                                  'text/markdown', None)['artifact_id']
        reply = reviewer(prompt)
        reply_artifact = self.store.put_artifact(request['task_id'], f'node-check-{key}-review-reply-{_sha(reply.encode())[:12]}',
                                                 reply.encode(), 'text/plain', None)['artifact_id']
        try:
            review = parse_review(reply)
            passed, reason = review_passes(review)
        except CheckError as exc:
            review, passed, reason = dict(verdict=None, summary='', findings=[]), False, str(exc)
        return dict(review, reviewer=reviewer.identity, passed=passed, reason=reason, packet_sha256=_sha(prompt.encode()),
                    packet_artifact=packet_artifact, reply_artifact=reply_artifact, diff_truncated=packet['diff_truncated'],
                    materials=sorted(materials),
                    context=('objective, step, criteria, capsule method materials, verifier checks and '
                             + ('the cited records' if request['kind'] == 'evidence' else 'diff') + ' only')), \
            [packet_artifact, reply_artifact]

    # -- host-checked outputs ------------------------------------------------------------
    def host_check(self, task, node, entry, refs):
        task_id, node_id = task['task_id'], node['node_id']
        values = dict(format=FORMAT, node_id=node_id, output=entry['name'], kind=entry['kind'], entry=entry,
                      key=_sha(dict(node=node_id, entry=entry, refs=refs)), state='finished', passed=False,
                      refs=refs, found={}, seconds={}, started=time.time())
        try:
            check = {'source_bundle': self._source_bundles, 'image': self._image,
                     'lab_request': self._lab_request, 'evidence': self._evidence}[entry['kind']]
            values['found'] = check(task, node, refs)
            values.update(passed=True, reason='passed')
        except (CheckError, ValueError, OSError) as exc:
            values['reason'] = str(exc)
        artifacts = [a for a in values['found'].get('artifacts', [])] if isinstance(values['found'], dict) else []
        return self._close(task_id, node_id, values, artifacts)

    def _source_bundles(self, task, node, refs):
        from .lab_build import MEDIA_TYPE, read_bundle
        from .store import NotFound
        ids = refs.get('artifact_ids') if isinstance(refs, dict) else None
        if not isinstance(ids, list) or not ids:
            raise CheckError('refs.artifact_ids must list the stored source bundles (from lab_manager.source_bundle)')
        bundles = []
        for artifact_id in ids:
            try:
                record = self.store._get('artifacts', task['task_id'], artifact_id)
            except NotFound:
                raise CheckError(f'no artifact {artifact_id} in this task') from None
            if record['media_type'] != MEDIA_TYPE:
                raise CheckError(f'{artifact_id} is not a lab source bundle')
            self.store.read_artifact(task['task_id'], artifact_id)  # digest recomputed against the record
            source = read_bundle(self.store.home / record['location'])
            bundles.append(dict(artifact_id=artifact_id, sha256=record['sha256'], recipe=source['recipe'],
                                base_commit=source['source']['base_commit'], head_tree=source['source']['head_tree']))
        return dict(bundles=bundles, artifacts=list(ids))

    def _image(self, task, node, refs):
        from .store import NotFound
        attempt_id = refs.get('build_attempt_id') if isinstance(refs, dict) else None
        image = refs.get('image_id') if isinstance(refs, dict) else None
        if not attempt_id or not image:
            raise CheckError('refs needs build_attempt_id and image_id')
        try:
            build = self.store._get('attempts', task['task_id'], attempt_id)
        except NotFound:
            raise CheckError(f'no attempt {attempt_id} in this task') from None
        if build['kind'] != 'build' or build['state'] != 'succeeded':
            raise CheckError(f'{attempt_id} is not a successful build (kind {build["kind"]}, state {build["state"]})')
        receipt = json.loads(self.store.artifact_bytes(task['task_id'], attempt_id + ':receipt'))
        if receipt.get('image_id') != image:
            raise CheckError(f'the build receipt names image {receipt.get("image_id")}, not {image}')
        return dict(build_attempt_id=attempt_id, image_id=image, artifacts=[attempt_id + ':receipt'])

    def _lab_request(self, task, node, refs):
        from .store import NotFound
        request_id = refs.get('request_id') if isinstance(refs, dict) else None
        if not request_id:
            raise CheckError('refs.request_id must name the lab request sent from this node')
        try:
            sent = self.store._get('observations', task['task_id'], request_id + ':request')
        except NotFound:
            raise CheckError(f'no lab request {request_id} in this task') from None
        package = json.loads(self.store.artifact_bytes(task['task_id'], 'lab-package:' + sent['values']['package_id']))
        if package['origin'].get('node_id') != node['node_id']:
            raise CheckError(f'lab request {request_id} was composed for node {package["origin"].get("node_id")}, not {node["node_id"]}')
        lab_task = package['lab_task']
        covered = set(lab_task.get('arms', {})) | set(lab_task.get('subjects', {}))
        for test in lab_task['tests']:
            covered |= set(test['arms']) | {test.get('check')} | set(test.get('measure', []))
            for arm in test['arms']:
                covered.add(arm)
        missing = []
        if node.get('node_contract'):
            from .node_contract import for_task, node as contract_node_of
            contract_node = contract_node_of(for_task(task), node['node_contract']) or {}
            missing = sorted(set(contract_node.get('requirement_ids', [])) - covered)
        if missing:
            raise CheckError('the lab task does not cover ' + ', '.join(missing))
        return dict(request_id=request_id, package_id=sent['values']['package_id'], tests=[t['id'] for t in lab_task['tests']],
                    artifacts=['lab-package:' + sent['values']['package_id']])

    def _evidence(self, task, node, refs):
        ids = refs.get('evidence_ids') if isinstance(refs, dict) else None
        if not isinstance(ids, list) or not ids:
            raise CheckError('refs.evidence_ids must list the records this output consists of')
        self.store.validate_evidence(task['task_id'], ids)
        return dict(evidence_ids=ids)

    def status(self, task_id, node_id):
        task = self.store.get_task(task_id)
        from .taskgraph import plan_get
        node = next((n for n in plan_get(self.store, task_id)['nodes'] if n['node_id'] == node_id), None)
        if node is None:
            raise CheckError(f'No node {node_id}')
        spec = effective_spec(task, node)
        running = [json.loads((p / 'request.json').read_text()) for p in self._root().glob('*')
                   if (p / 'running').exists() and (p / 'request.json').exists()]
        running = [r for r in running if r['task_id'] == task_id and r['node_id'] == node_id]
        outputs = {}
        for entry in outputs_of(spec) if spec else []:
            checks = checks_for(self.store, task_id, node_id, entry['name'])
            outputs[entry['name']] = dict(kind=entry['kind'], required=entry.get('required', True),
                                          latest=self._result(checks[-1]) if checks else None, count=len(checks),
                                          running=[r['key'][:32] for r in running if r.get('output') == entry['name']])
        return dict(node_id=node_id, state=node['state'], outputs=outputs, done_blocked_by=pending(self.store, task, node))

    @staticmethod
    def _result(row, cached=False):
        keep = ('obs_id', 'node_id', 'output', 'kind', 'state', 'passed', 'reason', 'verifier', 'review', 'found',
                'seconds', 'diff_sha256')
        return {k: row[k] for k in keep if k in row} | ({'cached': True} if cached else {}) | {'check_id': row.get('key', '')[:32]}


def dispatch(store, task_id, operation, inputs):
    from .api import fields
    from .store import ScopeDenied
    host = store
    if hasattr(store, '_check'):
        store._check(task_id, write=True)
        host = store._store
    checks = NodeChecks(host)
    if operation == 'start':
        fields(inputs, {'node_id', 'output', 'checkout', 'diff_path', 'verifier_inputs', 'refs'}, {'node_id'})
        from .taskgraph import dispatch_precondition
        dispatch_precondition(host, task_id, inputs['node_id'])
        if host is not store:  # an agent: what it asks to check must be in its workspace
            roots = [Path(v).expanduser().resolve() for v in (os.environ.get('FACTORY_WORKSPACE'),) if v]
            for path in filter(None, [inputs.get('checkout'), inputs.get('diff_path')]):
                if not roots or not any(Path(path).expanduser().resolve().is_relative_to(r) for r in roots):
                    raise ScopeDenied('A checkout or diff to check must be inside the agent workspace')
        return checks.start(task_id, **inputs)
    if operation == 'status':
        fields(inputs, {'node_id'}, {'node_id'})
        return checks.status(task_id, inputs['node_id'])
    raise ValueError('Unknown node_check capability')


def main(argv=None):
    import argparse
    from .store import Store
    parser = argparse.ArgumentParser(description='Run a prepared node check (started by node_check.start).')
    sub = parser.add_subparsers(dest='command', required=True)
    work = sub.add_parser('work')
    work.add_argument('directory')
    args = parser.parse_args(argv)
    from .controller import factory_home
    row = NodeChecks(Store(factory_home())).work(args.directory)
    print(json.dumps(NodeChecks._result(row)))


if __name__ == '__main__':
    main()
