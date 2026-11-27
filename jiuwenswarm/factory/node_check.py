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
  only after the verifier passes. ``review: "advisory"`` runs the same reviewer and records its
  verdict and findings on the check (``review.advisory: true``), but only the capsule verifier
  and the host checks decide pass or fail; a reviewer that is missing or errors out does not
  block it either. A reviewer needs no capsule: the node's criteria are
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
OUTPUT_FIELDS = {'name', 'kind', 'required', 'verifier', 'stage', 'review', 'criteria', 'inputs', 'seal'}
OUTPUT_KINDS = ('diff', 'source_bundle', 'image', 'lab_request', 'evidence', 'release')
# Evidence ladder used by the capsule verifiers (see each VALIDATION.md), weakest first.
STAGES = ('fixture', 'native CC execution', 'compile', 'runtime acceptance', 'hardware measurement')
VERIFIER_GRANTS = ['workspace.read', 'process.exec']
MAX_DIFF = int(os.environ.get('FACTORY_REVIEW_MAX_DIFF', 120_000))
MAX_MATERIAL = 24_000
REVIEW_MATERIALS = ('method', 'validation', 'guide')
SEVERITIES = ('blocker', 'major', 'minor')
ADVISORY = 'advisory'  # review: "advisory": recorded and shown, never decides the check
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
    if 'required' in entry and type(entry['required']) is not bool:
        raise ValueError('Check required must be true or false')
    if 'review' in entry and type(entry['review']) is not bool and entry['review'] != ADVISORY:
        raise ValueError(f'Check review must be true, false or "{ADVISORY}"')
    if entry['kind'] == 'diff' and not entry.get('verifier') and entry.get('review') is not True:
        raise ValueError(f'Check output {entry["name"]}: a diff needs a capsule verifier, a blocking review or both '
                         '(an advisory review decides nothing)')
    if entry['kind'] not in ('diff', 'evidence') and entry.get('verifier'):
        raise ValueError(f'Check output {entry["name"]}: capsule verifiers check diff and evidence outputs')
    if entry.get('review') and entry['kind'] not in ('diff', 'evidence'):
        raise ValueError(f'Check output {entry["name"]}: reviews read diffs and evidence; '
                         f'{entry["kind"]} outputs are checked by the host')
    if 'seal' in entry and (entry['kind'] != 'evidence' or not entry.get('verifier') or
                            not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', str(entry['seal']))):
        raise ValueError('Sealing needs a named output of an evidence verifier')
    if 'inputs' in entry and (not isinstance(entry['inputs'], dict) or not entry['inputs'] or not entry.get('verifier')
                              or set(entry['inputs']) & {'checkout', 'diff_path'}):
        raise ValueError(f'Check output {entry["name"]}: pinned inputs are a nonempty object for its verifier '
                         '(checkout and diff_path are set by the host)')
    if 'criteria' in entry and (not isinstance(entry['criteria'], list) or not all(isinstance(c, str) and c for c in entry['criteria'])):
        raise ValueError('Check criteria are a list of sentences')


def pin_inputs(entry, given):
    """The verifier inputs used: the agent's, with the contract's pinned values (targets, tolerances,
    expected ranges) on top. An agent value that differs from a pinned one is refused, so the
    worker cannot loosen its own gate."""
    pinned = entry.get('inputs') or {}
    merged = dict(given or {})
    loosened = sorted(k for k in pinned if k in merged and merged[k] != pinned[k])
    if loosened:
        raise CheckError(f'Output {entry["name"]}: the contract pins verifier inputs {", ".join(loosened)}; '
                         'omit them or pass the pinned values')
    return merged | pinned or None


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
        raise ValueError('A node check needs a verifier, a review or both')  # an advisory-only one is refused below
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


def current_checks(host, task_id, node, output):
    """The node checks that count: after an operator reopen, only those recorded after it."""
    checks = checks_for(host, task_id, node['node_id'], output)
    if node.get('checks_after'):
        later = {r[0] for r in host._db.execute(
            'SELECT obs_id FROM observations WHERE task_id=? AND kind=? AND rowid > '
            '(SELECT rowid FROM observations WHERE obs_id=?)', (task_id, KIND, node['checks_after']))}
        checks = [c for c in checks if c['obs_id'] in later]
    return checks


def pending(host, task, node):
    """Why this node cannot be done yet, or None. Called inside the plan transaction."""
    spec = effective_spec(task, node)
    if not spec:
        return None
    reasons = []
    for entry in outputs_of(spec):
        if not entry.get('required', True):
            continue
        checks = current_checks(host, task['task_id'], node, entry['name'])
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


def _staged_document(task):
    if not task.get('contract_id'):
        return None, None
    from .node_contract import for_task
    try:
        document = for_task(task)
    except FileNotFoundError:
        return None, None
    return document, (document or {}).get('staged_release')


def accepted_output(host, task_id, node, output):
    """Return the current check that the completed node cites."""
    task = host.get_task(task_id)
    if node['state'] != 'done' or pending(host, task, node):
        raise CheckError(f'Node {node["node_id"]} lacks its current passing checks')
    checks = current_checks(host, task_id, node, output)
    if not checks or not checks[-1].get('passed') or checks[-1]['obs_id'] not in node['evidence_ids']:
        raise CheckError(f'Node {node["node_id"]} has no accepted output {output}')
    return checks[-1]


def _predecessor(host, task_id, node, contract_id):
    from .taskgraph import plan_get
    matches = [other for other in plan_get(host, task_id)['nodes']
               if other['node_id'] in node['depends_on'] and other.get('node_contract') == contract_id
               and other['state'] == 'done']
    if len(matches) != 1:
        raise CheckError(f'Node {node["node_id"]} needs exactly one completed {contract_id} predecessor')
    return matches[0]


def accepted_stage(host, task_id, node, stage):
    """Resolve a configured stage to the accepted check of this node's predecessor."""
    _, staged = _staged_document(host.get_task(task_id))
    if not staged:
        raise CheckError('This task does not declare staged release')
    stage_id, output = staged[stage].split('.')
    producer = _predecessor(host, task_id, node, stage_id)
    return producer, accepted_output(host, task_id, producer, output)


def accepted_delivery(host, task_id, runtime_node):
    """Resolve the sent lab request accepted by the measurement node's predecessor."""
    document, staged = _staged_document(host.get_task(task_id))
    if not staged:
        raise CheckError('This task does not declare staged release')
    delivery = next(node for node in document['nodes'] if node['kind'] == 'deliver')
    output = next(out['name'] for out in delivery['outputs']
                  if out['kind'] == 'lab_request' and out.get('required', True))
    producer = _predecessor(host, task_id, runtime_node, delivery['node_id'])
    return accepted_output(host, task_id, producer, output)


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
        # Carry the diagnostics (for example "Missing input ports: [...]") so the worker can repair the call.
        said = '; '.join(str(d.get('message')) for d in receipt.get('diagnostics') or [] if isinstance(d, dict) and d.get('message'))
        return False, None, f"verifier call {receipt.get('state')}: {receipt.get('reason')}" + (f' ({said[:600]})' if said else '')
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
def _spawn(argv, **options):
    """Start the background worker of a check (detached)."""
    return subprocess.Popen(argv, **options)


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
        document, staged = _staged_document(task)
        port = f'{node.get("node_contract")}.{entry["name"]}'
        if staged:
            from .scheduler import effective_contract
            from .taskgraph import dispatch_precondition
            host = getattr(self.store, '_store', self.store)
            if effective_contract(host, task_id, node, document)[1]:
                raise CheckError('The scheduler must finalize this node before its check')
            dispatch_precondition(self.store, task_id, node_id)
        if staged and port == staged['runtime_stage']:
            measured = self._runtime_measurement(task_id, node, refs)
            if verifier_inputs and verifier_inputs != {'measurements': measured}:
                raise CheckError('The runtime-stage verifier takes the measurement from the host attempt')
            verifier_inputs = {'measurements': measured}
        elif staged and entry.get('verifier'):
            verifier_inputs = self._stage_inputs(task, node, document, port, verifier_inputs)
        if verifier_inputs and not entry.get('verifier'):
            raise CheckError(f'Output {entry["name"]} has no capsule verifier to take verifier_inputs')
        verifier_inputs = pin_inputs(entry, verifier_inputs)
        if staged and verifier_inputs:
            from .config import expand_sources
            verifier_inputs = expand_sources(verifier_inputs)
        if entry['kind'] != 'diff':
            if checkout or diff_path:
                raise CheckError(f'Output {entry["name"]} is a {entry["kind"]}; pass refs, not a checkout')
            if verifier_inputs and not (entry['kind'] == 'evidence' and entry.get('verifier')):
                raise CheckError(f'Output {entry["name"]} has no capsule verifier to take verifier_inputs')
            if entry['kind'] == 'evidence' and (entry.get('review') or entry.get('verifier')):
                return self._start_records(task, node, entry, refs, background, verifier_inputs)
            return self._result(self.host_check(task, node, entry, refs))
        if not checkout:
            raise CheckError(f'Output {entry["name"]} is a diff: pass the checkout')
        return self._start_diff(task, node, entry, checkout, diff_path, verifier_inputs, background)

    def _stage_inputs(self, task, node, document, port, supplied):
        from .node_contract import node as contract_node
        host = getattr(self.store, '_store', self.store)
        task_id = task['task_id']
        contract = contract_node(document, node.get('node_contract')) or {}
        values = {}
        for edge in contract.get('inputs', []):
            predecessor, separator, output = edge['from'].partition('.')
            if not separator:
                continue
            source = contract_node(document, predecessor)
            if not any(v['output'] == output and v.get('seal') for v in source['verifiers']):
                continue
            producer = _predecessor(host, task_id, node, predecessor)
            accepted = accepted_output(host, task_id, producer, output)
            artifact_id = accepted['verifier']['sealed_artifact']
            values[edge['name']] = json.loads(self.store.artifact_bytes(task_id, artifact_id))
        if port == document['staged_release']['factory_stage']:
            images = [entry for entry in outputs_of(node['check']) if entry['kind'] == 'image' and entry.get('required', True)]
            if len(images) != 1:
                raise CheckError('The factory stage needs one checked image output from its build')
            checks = current_checks(host, task_id, node, images[0]['name'])
            if not checks or not checks[-1]['passed'] or checks[-1]['entry'] != images[0]:
                raise CheckError('Pass the image output check before verifying the factory stage')
            build_id = checks[-1]['found']['build_attempt_id']
            values['build_record'] = json.loads(self.store.artifact_bytes(task_id, build_id + ':build-record'))
        supplied = supplied or {}
        if any(key in supplied and supplied[key] != value for key, value in values.items()):
            raise CheckError('The stage verifier inputs disagree with accepted host evidence')
        return dict(supplied, **values) or None

    # -- diff outputs --------------------------------------------------------------------
    def _start_diff(self, task, node, entry, checkout, diff_path, verifier_inputs, background):
        task_id, node_id = task['task_id'], node['node_id']
        if set(verifier_inputs or {}) & {'checkout', 'diff_path'}:
            raise CheckError('checkout and diff_path are set by the host from the work being checked, not in verifier_inputs')
        checkout = Path(checkout).expanduser().resolve()
        head = _git(checkout, 'rev-parse', 'HEAD')
        diff = Path(diff_path).expanduser().read_bytes() if diff_path else working_diff(checkout)
        if not diff.strip():
            raise CheckError('There is no change to check')
        verifier = self._prepare_verifier(entry)
        reviewer = self._reviewer_identity(entry)
        diff_sha = _sha(diff)
        key = _sha(dict(task=task_id, node=node_id, entry=entry, head=head, diff=diff_sha, working=not diff_path,
                        verifier=verifier, inputs=verifier_inputs or {}, reviewer=reviewer))
        request = dict(format=FORMAT, key=key, task_id=task_id, node_id=node_id, output=entry['name'], entry=entry,
                       kind='diff', checkout=str(checkout), head=head, working=not diff_path, diff_sha256=diff_sha,
                       diff_bytes=len(diff), verifier=verifier, verifier_inputs=verifier_inputs or {}, reviewer=reviewer)
        return self._launch(request, diff, background)

    def _reviewer_identity(self, entry):
        """Who reviews this output: None without a review. A blocking review needs a configured reviewer; an
        advisory one runs without (the check records that no reviewer was there)."""
        if not entry.get('review'):
            return None
        try:
            reviewer = self.reviewer
        except CheckError:
            if entry['review'] == ADVISORY:
                return None
            raise
        if reviewer is None:
            if entry['review'] == ADVISORY:
                return None
            raise CheckError('No reviewer is configured (FACTORY_REVIEW_CMD, FACTORY_REVIEW_OPENAI_BASE_URL or codex on PATH)')
        return reviewer.identity

    def _prepare_verifier(self, entry):
        """The sealed capsule release that verifies this output, or None when the output names no verifier."""
        if not entry.get('verifier'):
            return None
        from jiuwenswarm.ccv2.ccv2 import Host
        cc_id, capability = _split(entry['verifier'])
        host = Host(self.store.home / 'ccstore')
        release = host.prepare(capsule_folder(cc_id, self.ccs_roots))
        release = release['release'] if isinstance(release, dict) else release
        declaration, _ = host.release(release)
        if capability not in declaration['capabilities']:
            raise CheckError(f'{cc_id} has no capability {capability}')
        return dict(cc=cc_id, capability=capability, release=release)

    def _start_records(self, task, node, entry, refs, background, verifier_inputs=None):
        """An evidence output with a capsule verifier, a review or both: the host checks the records exist,
        the capsule's verifier inspects the artifact they name (for example a model pack manifest), then a
        reviewer reads the records and the verifier's checks."""
        if set(verifier_inputs or {}) & {'checkout', 'diff_path'}:
            raise CheckError('checkout and diff_path are not verifier inputs of an evidence output')
        try:
            self._evidence(task, node, refs)
        except (CheckError, ValueError) as exc:
            values = dict(format=FORMAT, node_id=node['node_id'], output=entry['name'], kind='evidence', entry=entry,
                          key=_sha(dict(node=node['node_id'], entry=entry, refs=refs)), state='finished', passed=False,
                          refs=refs, reason=str(exc), seconds={}, started=time.time())
            return self._result(self._close(task['task_id'], node['node_id'], values, []))
        reviewer = self._reviewer_identity(entry)
        verifier = self._prepare_verifier(entry)
        records = [self.store.read(task['task_id'], ref) for ref in refs['evidence_ids']]
        subject = json.dumps(records, indent=1, sort_keys=True, default=str).encode()
        key = _sha(dict(task=task['task_id'], node=node['node_id'], entry=entry, records=_sha(subject),
                        verifier=verifier, inputs=verifier_inputs or {}, reviewer=reviewer))
        request = dict(format=FORMAT, key=key, task_id=task['task_id'], node_id=node['node_id'], output=entry['name'],
                       entry=entry, kind='evidence', refs=refs, head=None, working=False, diff_sha256=_sha(subject),
                       diff_bytes=len(subject), verifier=verifier, verifier_inputs=verifier_inputs or {}, reviewer=reviewer)
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
        # Recorded first, so the node cannot close on an older pass while this check runs.
        self._record(task_id, node_id, dict(format=FORMAT, node_id=node_id, output=entry['name'], kind=request['kind'],
                                            entry=entry, key=key, state='running', passed=False,
                                            reason='check running', seconds={}), [])
        log = (work / 'worker.log').open('ab')
        _spawn([sys.executable, '-m', 'jiuwenswarm.factory.node_check', 'work', str(work)],
                         stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
                         env=dict(os.environ, FACTORY_HOME=str(self.store.home), PYTHONPATH=os.pathsep.join(
                             filter(None, [str(Path(__file__).resolve().parents[2]), os.environ.get('PYTHONPATH')]))))
        return dict(check_id=key[:32], node_id=node_id, output=entry['name'], state='running')

    def _finished(self, task_id, node_id, output, key):
        checks = checks_for(self.store, task_id, node_id, output)
        same = [c for c in checks if c.get('key') == key and c.get('state') == 'finished']
        if not same:
            return None
        counted = current_checks(self.store, task_id, self._node(task_id, node_id), output)
        if checks[-1]['obs_id'] == same[-1]['obs_id'] and counted and counted[-1]['obs_id'] == same[-1]['obs_id']:
            return same[-1]
        # The same work was checked before a different one or before an operator reopen; record it
        # again so it is the latest check that counts.
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
                if values['verifier'].get('sealed_artifact'):
                    artifacts.append(values['verifier']['sealed_artifact'])
                values['seconds']['verifier'] = round(time.time() - t, 3)
                if not values['verifier']['passed']:
                    values['reason'] = values['verifier']['reason']
                    return self._close(task_id, node_id, values, artifacts, work)
            advisory = entry.get('review') == ADVISORY
            if entry.get('review'):
                t = time.time()
                if advisory:
                    values['review'], reply_artifacts = self._advisory_review(request, diff, values['verifier'])
                else:
                    values['review'], reply_artifacts = self._review(request, diff, values['verifier'])
                artifacts += reply_artifacts
                values['seconds']['review'] = round(time.time() - t, 3)
                if not values['review']['passed'] and not advisory:
                    values['reason'] = values['review']['reason']
                    return self._close(task_id, node_id, values, artifacts, work)
            if request['kind'] == 'diff':
                self._same_work(request)  # after the review too: the pass is for the work as it stands
            values.update(passed=True, reason='passed')
            if advisory:
                values['reason'] = 'passed; advisory review (does not decide): ' + values['review']['reason']
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
        if request['kind'] != 'diff':
            return
        if _git(request['checkout'], 'rev-parse', 'HEAD') != request['head']:
            raise CheckError('the checkout moved to another commit after the check was requested')
        if request['working'] and _sha(working_diff(request['checkout'])) != request['diff_sha256']:
            raise CheckError('the checkout changed after the check was requested')

    def _verify(self, request, work):
        from .wiring_fixture import is_demo_check, submit
        self._same_work(request)
        receipt = submit(self.store, request, work) if is_demo_check(request) else self._call_verifier(request, work)
        self._same_work(request)
        verifier = request['verifier']
        passed, reached, reason = assess(receipt, request['entry'].get('stage'))
        outputs = receipt.get('outputs') or {}
        result = dict(cc=verifier['cc'], capability=verifier['capability'], release=verifier['release'],
                      call=receipt.get('call'), state=receipt.get('state'), passed=passed, stage_reached=reached,
                      reason=reason, checks=[{k: c.get(k) for k in ('name', 'status', 'stage', 'detail')}
                                             for c in outputs.get('checks') or [] if isinstance(c, dict)])
        if 'capped_attempt_id' in receipt:
            result['capped_attempt_id'] = receipt['capped_attempt_id']
        if passed and request['entry'].get('seal'):
            port = request['entry']['seal']
            payload = outputs.get(port)
            if not isinstance(payload, dict):
                result.update(passed=False, reason=f'Verifier did not return a JSON object at {port}')
            else:
                data = json.dumps(payload, sort_keys=True, indent=2, allow_nan=False).encode() + b'\n'
                artifact_id = f'node-check-{request["key"][:24]}-{port}'
                self.store.put_artifact(request['task_id'], artifact_id, data, 'application/json', None)
                result['sealed_artifact'] = artifact_id
        return result

    def _call_verifier(self, request, work, approved_inputs=None):
        from jiuwenswarm.ccv2.ccv2 import Host
        verifier = request['verifier']
        host = Host(self.store.home / 'ccstore')
        declaration, _ = host.release(verifier['release'])
        capability = declaration['capabilities'][verifier['capability']]
        takes = capability['takes']
        inputs = dict(request['verifier_inputs'] if approved_inputs is None else approved_inputs)
        if 'checkout' in takes:
            inputs['checkout'] = request['checkout']
        # Uncommitted work is already in the checkout: the verifier reads it there. A patch
        # file is checked against the checkout it applies to.
        if 'diff_path' in takes and not request['working']:
            inputs['diff_path'] = str(Path(work) / 'patch.diff')
        key_prefix = 'node-check-capped-' if approved_inputs is not None else 'node-check-'
        return host.call(verifier['release'], verifier['capability'], inputs, key=key_prefix + request['key'],
                         grants=sorted(set(VERIFIER_GRANTS) & set(capability['changes'])),
                         timeout=float(os.environ.get('FACTORY_VERIFY_TIMEOUT', 900)))

    def _advisory_review(self, request, diff, verifier):
        """The review of an advisory output: run and recorded like any review, marked advisory, and never raised."""
        empty = dict(verdict=None, summary='', findings=[], reviewer=request['reviewer'], passed=False, advisory=True,
                     error=True)
        if request['reviewer'] is None:
            return dict(empty, reason='no reviewer is configured; the review did not run'), []
        try:
            review, artifacts = self._review(request, diff, verifier)
        except Exception as exc:  # noqa: BLE001 - an advisory review never blocks the check, whatever goes wrong
            return dict(empty, reason=f'the review could not run: {type(exc).__name__}: {str(exc)[:300]}'), []
        return dict(review, advisory=True), artifacts

    def _review(self, request, diff, verifier):
        task = self.store.get_task(request['task_id'])
        from .taskgraph import plan_get
        node = next(n for n in plan_get(self.store, request['task_id'])['nodes'] if n['node_id'] == request['node_id'])
        entry = request['entry']
        step = {k: node.get(k) for k in ('node_id', 'kind', 'title', 'capability', 'engine_slice', 'node_contract') if node.get(k)}
        step['output'] = entry['name']
        contract_node = None
        if node.get('node_contract'):
            from .node_contract import for_task
            from .scheduler import effective_contract
            try:  # the final node contract when the scheduler finalized a preliminary one
                contract_node = effective_contract(getattr(self.store, '_store', self.store), request['task_id'],
                                                   node, for_task(task))[0]
            except (ValueError, OSError):
                contract_node = None
        if contract_node:
            step['objective'] = contract_node['objective']
            step['requirement_ids'] = contract_node.get('requirement_ids', [])
        ccs = [_split(entry['verifier'])[0]] if entry.get('verifier') else []
        ccs += (contract_node or {}).get('work', {}).get('bound_ccs', [])
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
                     'lab_request': self._lab_request, 'evidence': self._evidence, 'release': self._release}[entry['kind']]
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
        tested = dict(arm={a for test in lab_task['tests'] for a in test['arms']},
                      check={test['check'] for test in lab_task['tests'] if test.get('check')},
                      metric={m for test in lab_task['tests'] for m in test.get('measure', [])})
        missing = []
        if node.get('node_contract'):
            from .contract import load
            from .contract_v2 import arm_ids, check_ids, metric_ids
            from .node_contract import for_task
            from .scheduler import effective_contract
            contract_node = effective_contract(getattr(self.store, '_store', self.store), task['task_id'],
                                               node, for_task(task))[0] or {}
            contract = load(task['contract_id'])
            kinds = {**{a: 'arm' for a in arm_ids(contract)}, **{c: 'check' for c in check_ids(contract)},
                     **{m: 'metric' for m in metric_ids(contract)}}
            # Each requirement counts only as what it is: an arm must be tested, a check run, a metric measured.
            missing = sorted(r for r in contract_node.get('requirement_ids', []) if r not in tested.get(kinds.get(r), set()))
        if missing:
            raise CheckError('the lab task does not test ' + ', '.join(missing))
        return dict(request_id=request_id, package_id=sent['values']['package_id'], tests=[t['id'] for t in lab_task['tests']],
                    artifacts=['lab-package:' + sent['values']['package_id']])

    def _evidence(self, task, node, refs):
        ids = refs.get('evidence_ids') if isinstance(refs, dict) else None
        if not isinstance(ids, list) or not ids:
            raise CheckError('refs.evidence_ids must list the records this output consists of')
        self.store.validate_evidence(task['task_id'], ids)
        return dict(evidence_ids=ids)

    def _runtime_measurement(self, task_id, node, refs):
        host = getattr(self.store, '_store', self.store)
        delivery = accepted_delivery(host, task_id, node)
        request_id = delivery['found']['request_id']
        ids = (refs or {}).get('evidence_ids') or []
        matched = []
        for evidence_id in ids:
            record = self.store.read(task_id, evidence_id)
            values = record.get('values') or {}
            request = values.get('request') or {}
            if (record.get('kind') == 'capped_run' and values.get('node_id') == node['node_id']
                    and values.get('outcome') == 'ok' and request.get('request_id') == request_id
                    and request.get('package_id') == delivery['found']['package_id']
                    and isinstance(values.get('result'), dict)):
                attempt = host._get('attempts', task_id, values['attempt_id'])
                if (attempt.get('kind') == 'model_run' and attempt.get('state') == 'succeeded'
                        and attempt.get('request', {}).get('node_id') == node['node_id']):
                    matched.append(values['result'])
        if len(matched) != 1:
            raise CheckError('Runtime verification needs one successful host measurement of the accepted lab request')
        return matched[0]

    def _release(self, task, node, refs):
        host = getattr(self.store, '_store', self.store)
        document, staged = _staged_document(task)
        if not staged or node.get('node_contract') != staged['release_gate']:
            raise CheckError('Only the contracted staged release gate can produce a release')
        task_id = task['task_id']
        runtime, measured = accepted_stage(host, task_id, node, 'runtime_stage')
        delivery = accepted_delivery(host, task_id, runtime)
        delivery_id = next(item['node_id'] for item in document['nodes'] if item['kind'] == 'deliver')
        delivery_node = _predecessor(host, task_id, runtime, delivery_id)
        _, factory = accepted_stage(host, task_id, delivery_node, 'factory_stage')
        if (refs or {}).get('runtime_check_id') != measured['obs_id']:
            raise CheckError('refs.runtime_check_id must name the accepted runtime-stage check')
        self._runtime_measurement(task_id, runtime, measured['refs'])
        return dict(factory_check_id=factory['obs_id'], delivery_check_id=delivery['obs_id'],
                    runtime_check_id=measured['obs_id'], request_id=delivery['found']['request_id'],
                    package_id=delivery['found']['package_id'],
                    artifacts=delivery['source_artifacts'] + factory['source_artifacts'])

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
                                          **({'review': entry['review']} if entry.get('review') else {}),
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
