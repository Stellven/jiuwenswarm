"""Lab manager: the factory side of work done by a lab agent.

A software agent hands the lab manager what it built (a container image, a native build,
a source revision or a stored artifact) together with a lab task (``factory.lab-task/1``):
which contract arms those results fill, which checks and measurements to run and what to
deliver. The lab manager checks the lab task against the task's pinned contract, seals the
three into a lab package (``factory.lab-package/1``) and posts it to the lab mailbox
(``lab_mailbox``). Any lab agent that reads the mailbox can take it, set up the lab, answer
questions and deliver a report (``factory.lab-report/1``). The lab manager checks the
report against the package and records it as factory evidence.

A subject marked ``transfer: attach`` travels with the package: a container image as a
``docker save`` archive, a stored artifact as it is (``lab_payload``), or a source bundle:
the diff of a repository, branch or fork against a base commit plus its build recipe and
source dependencies, which the lab assembles into an image on its own hardware
(``lab_build``, made with ``source_bundle``). The mailbox may
be a directory or an HTTP address (``lab_http``), so the lab can be another machine.

Routing (``$FACTORY_LAB_ROUTE``): ``queue`` lets the factory's own lab queue, the system
behind ``factory.lab_client``, work every request it can run, in process, whenever the
lab manager is asked for the status or the report. ``mailbox`` leaves every request to an
external lab agent. ``auto`` (the default) is ``queue`` for a local mailbox and
``mailbox`` for an HTTP one. A request the queue cannot run stays open for a lab agent.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

import yaml

from .lab_mailbox import MailboxError, TERMINAL, canonical, open_mailbox, sha256_file
from .store import NotFound, ScopeDenied

PACKAGE = 'factory.lab-package/1'
QUEUE_LAB = 'factory-queue'


# ---- contracts as the lab manager sees them --------------------------------------------
def contract_view(contract):
    """Arms, checks, metrics and requests a lab task may name. None means not declared."""
    if contract.get('schema') == 'factory.contract/2':
        from . import contract_v2
        return dict(format=2, arms=contract_v2.arm_ids(contract),
                    roles={arm['id']: arm['role'] for arm in contract['arms']},
                    checks={check['id']: check for check in contract['correctness']['checks']},
                    metrics={name: spec['unit'] for name, spec in contract['measurement']['metrics'].items()},
                    requests=contract_v2.request_ids(contract), target=contract['target']['profile'])
    checks = {'reference_parity': dict(id='reference_parity', does='Output equals the frozen reference output.',
                                       applies_to=['candidate'])}
    for name in [*contract.get('engagement_checks', []), *contract.get('candidate_engagement_checks', [])]:
        checks[name] = dict(id=name, does='Engagement line or check named by the contract.', applies_to=['candidate'])
    return dict(format=1, arms=None, roles={}, checks=checks, metrics=None, requests=None,
                target=contract.get('target'))


def parse_lab_task(value):
    if isinstance(value, str):
        try:
            value = yaml.safe_load(value)
        except yaml.YAMLError as exc:
            raise ValueError('lab_task is not valid YAML: ' + str(exc)[:200]) from None
    if not isinstance(value, dict):
        raise ValueError('lab_task must be an object or YAML text')
    return value


def task_problems(lab_task, contract, contract_sha256):
    from .contract_v2 import schema_errors
    found = schema_errors(lab_task, 'lab-task-1.schema.json')
    if found:
        return found
    view = contract_view(contract)
    named = lab_task['contract']
    if named['id'] not in {contract['contract_id'], str(getattr(contract, 'path', '')), getattr(getattr(contract, 'path', None), 'stem', None)}:
        found.append(f'contract/id: {named["id"]!r} is not the task contract {contract["contract_id"]!r}')
    if named.get('sha256') and named['sha256'] != contract_sha256:
        found.append('contract/sha256: differs from the pinned contract file')
    subjects = lab_task['subjects']
    for arm, spec in lab_task['arms'].items():
        if view['arms'] is not None and arm not in view['arms']:
            found.append(f'arms/{arm}: not an arm of the contract ({", ".join(view["arms"])})')
        if spec['subject'] not in subjects:
            found.append(f'arms/{arm}/subject: unknown subject {spec["subject"]!r}')
    seen = set()
    for test in lab_task['tests']:
        where = f'tests/{test["id"]}'
        if test['id'] in seen:
            found.append(f'{where}: test id is declared twice')
        seen.add(test['id'])
        for arm in test['arms']:
            if arm not in lab_task['arms']:
                found.append(f'{where}/arms: {arm!r} is not an arm of this lab task')
        if 'check' in test:
            check = view['checks'].get(test['check'])
            if check is None:
                found.append(f'{where}/check: {test["check"]!r} is not a check of the contract ({", ".join(view["checks"])})')
            elif view['format'] == 2:
                from .contract_v2 import arms_for
                applies = set(arms_for(contract, check['applies_to']))
                for arm in test['arms']:
                    if arm in lab_task['arms'] and arm not in applies:
                        found.append(f'{where}/arms: check {test["check"]} does not apply to arm {arm}')
        for metric in test.get('measure', []):
            if view['metrics'] is not None and metric not in view['metrics']:
                found.append(f'{where}/measure: {metric!r} is not a metric of the contract')
        for request in test.get('requests', []):
            if view['requests'] is not None and request not in view['requests']:
                found.append(f'{where}/requests: {request!r} is not a request of the contract')
        compare = test.get('compare')
        if compare:
            for side in ('base', 'candidate'):
                if compare[side] not in test['arms']:
                    found.append(f'{where}/compare/{side}: {compare[side]!r} is not one of the test arms')
            if compare['base'] == compare['candidate']:
                found.append(f'{where}/compare: base and candidate must differ')
    names = [f['name'] for f in lab_task.get('deliverables', {}).get('files', [])]
    if len(names) != len(set(names)):
        found.append('deliverables/files: a file name is listed twice')
    profile = lab_task.get('constraints', {}).get('lab_profile')
    if profile and view['target'] and profile != view['target']:
        found.append(f'constraints/lab_profile: {profile!r} differs from the contract target {view["target"]!r}')
    from .contract_v2 import host_paths
    for path in host_paths(lab_task):
        found.append(f'{path.lstrip("/")}: absolute host path; a lab task names results by identity, not location')
    return found


def report_problems(report, package):
    """Every reason a report does not answer the package it claims to answer."""
    from .contract_v2 import schema_errors
    found = schema_errors(report, 'lab-report-1.schema.json')
    if found:
        return found
    lab_task, contract = package['lab_task'], package['contract']
    for key, expected in (('package_id', package['package_id']), ('lab_task_id', lab_task['lab_task_id'])):
        if report[key] != expected:
            found.append(f'{key}: {report[key]!r} is not {expected!r}')
    if report['contract'] != dict(id=contract['id'], sha256=contract['sha256']):
        found.append('contract: id or sha256 differs from the package')
    view = contract_view(contract['document'])
    tests = {test['id']: test for test in lab_task['tests']}
    covered = {}
    for row in report['results']:
        test = tests.get(row['test_id'])
        if test is None:
            found.append(f'results: unknown test {row["test_id"]!r}')
            continue
        covered.setdefault(row['test_id'], set()).add(('metric', row['metric']))
        if row['arm'] not in test['arms']:
            found.append(f'results/{row["test_id"]}: arm {row["arm"]!r} is not an arm of the test')
        if row['metric'] not in test.get('measure', []):
            found.append(f'results/{row["test_id"]}: metric {row["metric"]!r} is not measured by the test')
        elif view['metrics'] is not None and view['metrics'].get(row['metric']) != row['unit']:
            found.append(f'results/{row["test_id"]}/{row["metric"]}: unit {row["unit"]!r} is not the contract unit {view["metrics"].get(row["metric"])!r}')
        if 'request' in row and row['request'] not in test.get('requests', view['requests'] or [row['request']]):
            found.append(f'results/{row["test_id"]}: request {row["request"]!r} is not a request of the test')
        if lab_task.get('deliverables', {}).get('raw_samples') and 'samples' not in row:
            found.append(f'results/{row["test_id"]}/{row["metric"]}: raw samples were asked for')
    for row in report['checks']:
        test = tests.get(row['test_id'])
        if test is None:
            found.append(f'checks: unknown test {row["test_id"]!r}')
            continue
        covered.setdefault(row['test_id'], set()).add(('check', row['check']))
        if row['check'] != test.get('check'):
            found.append(f'checks/{row["test_id"]}: check {row["check"]!r} is not the check of the test')
        if 'arm' in row and row['arm'] not in test['arms']:
            found.append(f'checks/{row["test_id"]}: arm {row["arm"]!r} is not an arm of the test')
    skipped = {}
    for row in report['not_run']:
        if row['test_id'] not in tests:
            found.append(f'not_run: unknown test {row["test_id"]!r}')
        skipped[row['test_id']] = row['reason']
    for test_id, test in tests.items():
        if test_id in skipped:
            continue
        have = covered.get(test_id, set())
        if 'check' in test and ('check', test['check']) not in have:
            found.append(f'tests/{test_id}: no verdict for check {test["check"]} and not listed in not_run')
        for metric in test.get('measure', []):
            if ('metric', metric) not in have:
                found.append(f'tests/{test_id}: no result for {metric} and not listed in not_run')
    not_run_verdicts = [row for row in report['checks'] if row['verdict'] == 'not_run']
    if report['outcome'] == 'completed' and (skipped or not_run_verdicts):
        found.append('outcome: completed, but some tests or checks were not run; use partial')
    names = [f['name'] for f in report['files']]
    if len(names) != len(set(names)):
        found.append('files: a file name is listed twice')
    for wanted in lab_task.get('deliverables', {}).get('files', []):
        if wanted['name'] not in names and report['outcome'] != 'failed':
            found.append(f'files: deliverable {wanted["name"]!r} is missing')
    for name, build in (report.get('builds') or {}).items():
        payload = (package.get('subjects', {}).get(name) or {}).get('payload') or {}
        if payload.get('format') != 'source-bundle':
            found.append(f'builds/{name}: not a subject shipped as source')
        elif build.get('head_tree') != payload.get('head_tree'):
            found.append(f'builds/{name}/head_tree: the lab built another tree than the sealed one')
    for section in lab_task.get('deliverables', {}).get('sections', []):
        if section not in report.get('sections', {}) and report['outcome'] != 'failed':
            found.append(f'sections: deliverable section {section!r} is missing')
    return found


# ---- the factory side ------------------------------------------------------------------
class LabManager:
    def __init__(self, store, mailbox=None, route=None):
        self.store = store
        self.mailbox = mailbox or open_mailbox(None, store.home)
        route = route or os.environ.get('FACTORY_LAB_ROUTE', 'auto')
        if route not in {'auto', 'queue', 'mailbox'}:
            raise ValueError('FACTORY_LAB_ROUTE is auto, queue or mailbox')
        if route == 'auto':
            route = 'mailbox' if str(getattr(self.mailbox, 'root', '')).startswith(('http://', 'https://')) else 'queue'
        self.route = route

    def _advance(self, request_id, package):
        """With the queue route, let the factory lab queue take one step on this request."""
        if self.route != 'queue':
            return None
        from .lab_agent import LabAgent, QueueAdapter, accepted_by
        thread = self.mailbox.thread(request_id)
        if thread['state'] in TERMINAL:
            return None
        owner = accepted_by(thread)
        if owner not in (None, QUEUE_LAB):
            return None
        adapter = QueueAdapter(self.store.home, self.store.home / 'lab-state' / QUEUE_LAB)
        if thread['state'] == 'requested':
            reason = adapter.unsupported(package)
            if reason:
                return f'left for a lab agent: {reason}'
        agent = LabAgent(self.mailbox, QUEUE_LAB, 'queue')
        adapter.step(agent, request_id, package, thread)
        agent.auto_answer(request_id)
        return 'factory lab queue'

    def _payload(self, task_id, name, subject, scratch):
        """Store the bytes of a subject marked transfer: attach; return the payload reference."""
        identity = subject['identity']
        if identity.get('artifact_id'):
            try:
                record = self.store._get('artifacts', task_id, identity['artifact_id'])
            except NotFound:
                raise ValueError(f'subjects/{name}/identity/artifact_id: no such artifact in this task') from None
            from .lab_build import MEDIA_TYPE, read_bundle
            if record['media_type'] == MEDIA_TYPE:
                source = read_bundle(self.store.home / record['location'])
                if subject['kind'] != 'source':
                    raise ValueError(f'subjects/{name}: a source bundle ships a subject of kind source')
                if identity.get('head_tree') and identity['head_tree'] != source['source']['head_tree']:
                    raise ValueError(f'subjects/{name}/identity/head_tree: differs from the source bundle')
                return dict(name=f'{name}.src.tar', sha256=record['sha256'], size=record['size'], media_type=MEDIA_TYPE,
                            format='source-bundle', artifact_id=identity['artifact_id'], recipe=source['recipe'],
                            head_tree=source['source']['head_tree'], base_commit=source['source']['base_commit'])
            return dict(name=f'{name}.bin', sha256=record['sha256'], size=record['size'],
                        media_type=record['media_type'], format='file', artifact_id=identity['artifact_id'])
        if subject['kind'] != 'container_image':
            raise ValueError(f'subjects/{name}/transfer: attach needs identity.artifact_id, or a container image')
        from .lab_payload import DOCKER_ARCHIVE, save_image
        image = identity.get('id') or identity.get('tag')
        if not image:
            raise ValueError(f'subjects/{name}/identity: a container image needs id or tag')
        archive = Path(scratch) / f'{name}.tar'
        image_id = save_image(image, archive, identity.get('id'))
        sha, size = sha256_file(archive)
        artifact_id = f'lab-payload:{sha[:32]}'
        self.store.put_artifact(task_id, artifact_id, archive, DOCKER_ARCHIVE, None)
        return dict(name=f'{name}.tar', sha256=sha, size=size, media_type=DOCKER_ARCHIVE,
                    format='docker-archive', image_id=image_id, artifact_id=artifact_id)

    def _payload_path(self, task_id, payload):
        record = self.store._get('artifacts', task_id, payload['artifact_id'])
        if record['sha256'] != payload['sha256']:
            raise ValueError(f'Stored payload {payload["artifact_id"]} differs from the sealed package')
        return self.store.home / record['location']

    # helpers
    def _contract(self, task, contract_id):
        from .contract import load_for_task
        from .contract_v2 import file_sha256
        contract = load_for_task(task, contract_id or task.get('contract_id'))
        digest = file_sha256(contract.path)
        pinned = task.get('constraints', {}).get('contract_sha256')
        if pinned and pinned != digest:
            raise ValueError('The task contract file changed after it was pinned')
        return contract, digest

    def _verify_subject(self, task_id, name, subject):
        attempt_id = subject.get('build_attempt_id')
        if not attempt_id:
            return dict(verified=False, against=None, note='no build attempt named; identity is as stated')
        try:
            build = self.store._get('attempts', task_id, attempt_id)
        except NotFound:
            raise ValueError(f'subjects/{name}/build_attempt_id: no such attempt in this task') from None
        if build['kind'] != 'build' or build['state'] != 'succeeded':
            raise ValueError(f'subjects/{name}/build_attempt_id: not a succeeded build')
        try:
            receipt = json.loads(self.store.artifact_bytes(task_id, attempt_id + ':receipt'))
        except NotFound:
            raise ValueError(f'subjects/{name}: the build has no receipt') from None
        identity = subject['identity']
        if subject['kind'] == 'container_image':
            if identity.get('id') != receipt.get('image_id'):
                raise ValueError(f'subjects/{name}/identity/id: differs from the build receipt image id')
        elif subject['kind'] == 'native_build':
            executable = receipt.get('executable') or {}
            stated = identity.get('executable_sha256')
            recorded = executable.get('sha256') if isinstance(executable, dict) else None
            if stated and recorded and stated != recorded:
                raise ValueError(f'subjects/{name}/identity/executable_sha256: differs from the build receipt')
        return dict(verified=True, against=f'build receipt of {attempt_id}')

    def _package_for(self, task_id, request_id):
        try:
            package = self.mailbox.package(request_id)
        except MailboxError:
            raise ValueError('Unknown lab request') from None
        if package.get('origin', {}).get('task_id') != task_id:
            raise ScopeDenied('Lab request belongs to another task')
        # Judge the lab against the package the factory sealed, never a copy in the mailbox.
        try:
            sealed = json.loads(self.store.artifact_bytes(task_id, 'lab-package:' + str(package.get('package_id'))))
        except NotFound:
            raise ScopeDenied('Lab request names no package sealed by this task') from None
        if canonical(sealed) != canonical(package):
            raise ScopeDenied('The mailbox copy of the lab package differs from the sealed package')
        return sealed

    def _record(self, task_id, artifact_id, data, media_type='application/json'):
        return self.store.put_artifact(task_id, artifact_id, data, media_type, None)['artifact_id']

    def _observation(self, task_id, obs_id, record):
        try:
            return self.store._get('observations', task_id, obs_id)
        except NotFound:
            return self.store.append_observation(task_id, dict(record, obs_id=obs_id))

    # capabilities
    def source_bundle(self, task_id, checkout, base, recipe, repository=None, include_base=False,
                      worktree=True, deps=(), extra_flags=()):
        """Store a source bundle of ``checkout`` against ``base``; return a subject that ships it."""
        from .lab_build import MEDIA_TYPE, make_bundle
        self.store.get_task(task_id)
        with tempfile.TemporaryDirectory(dir=self.store.home) as scratch:
            made = make_bundle(checkout, base, Path(scratch) / 'source.tar', recipe, repository, include_base,
                               worktree, deps, extra_flags)
            artifact_id = f'lab-source:{made["sha256"][:32]}'
            self.store.put_artifact(task_id, artifact_id, Path(made['path']), MEDIA_TYPE, None)
        identity = dict(base_commit=made['base_commit'], head_tree=made['head_tree'], artifact_id=artifact_id)
        if made['repository']:
            identity['repository'] = made['repository']
        return dict(artifact_id=artifact_id, sha256=made['sha256'], size=made['size'], recipe=recipe, deps=made['deps'],
                    subject=dict(kind='source', identity=identity, transfer='attach'))

    def draft_task(self, task_id, arm_subjects, subjects, contract_id=None, lab_task_id=None, purpose=None):
        """A lab task that runs every check and metric of the contract on the given arms."""
        task = self.store.get_task(task_id)
        contract, digest = self._contract(task, contract_id)
        if contract.get('schema') != 'factory.contract/2':
            raise ValueError('draft_task needs a format-2 contract; write the lab task by hand for format 1')
        from .contract_v2 import arms_for, metric_ids, request_ids
        if not isinstance(arm_subjects, dict) or not arm_subjects:
            raise ValueError('arm_subjects maps contract arms to subject names')
        arms = [arm for arm in (a['id'] for a in contract['arms']) if arm in arm_subjects]
        tests = []
        for check in contract['correctness']['checks']:
            applies = [arm for arm in arms_for(contract, check['applies_to']) if arm in arms]
            if applies:
                tests.append(dict(id=check['id'], does=check['does'], check=check['id'], arms=applies))
        tests.append(dict(id='measure', does='Every contract metric on every arm and request.',
                          measure=metric_ids(contract), arms=arms, requests=request_ids(contract)))
        draft = dict(schema='factory.lab-task/1', lab_task_id=lab_task_id or f'{contract["contract_id"]}-lab',
                     purpose=purpose or contract['purpose'], contract=dict(id=contract['contract_id'], sha256=digest),
                     subjects=subjects, arms={arm: dict(subject=arm_subjects[arm]) for arm in arms}, tests=tests,
                     deliverables=dict(raw_samples=True, sections=['setup', 'results', 'deviations']),
                     constraints=dict(lab_profile=contract['target']['profile']), questions=dict(allowed=True))
        return dict(lab_task=draft, problems=task_problems(draft, contract, digest))

    def compose(self, task_id, lab_task, contract_id=None, node_id=None):
        task = self.store.get_task(task_id)
        lab_task = parse_lab_task(lab_task)
        contract, digest = self._contract(task, contract_id or (lab_task.get('contract') or {}).get('id'))
        found = task_problems(lab_task, contract, digest)
        if found:
            raise ValueError('Invalid lab task: ' + '; '.join(found[:20]))
        lab_task = json.loads(canonical(lab_task))
        from .node_contract import from_contract
        if (from_contract(contract) or {}).get('staged_release'):
            self._verify_factory_stage(task_id, node_id, lab_task)
        lab_task['contract'] = dict(id=contract['contract_id'], sha256=digest)
        subjects = {name: dict(subject, verification=self._verify_subject(task_id, name, subject))
                    for name, subject in lab_task['subjects'].items()}
        with tempfile.TemporaryDirectory(dir=self.store.home) as scratch:
            for name, subject in subjects.items():
                if subject.get('transfer') == 'attach':
                    subject['payload'] = self._payload(task_id, name, subject, scratch)
        package = dict(schema=PACKAGE, origin=dict(task_id=task_id, **({'node_id': node_id} if node_id else {})),
                       lab_task=lab_task, subjects=subjects,
                       contract=dict(id=contract['contract_id'], sha256=digest,
                                     format=contract_view(contract)['format'], document=dict(contract)))
        package['package_id'] = 'labpkg-' + hashlib.sha256(canonical(package).encode()).hexdigest()[:32]
        artifact = self._record(task_id, 'lab-package:' + package['package_id'], (canonical(package) + '\n').encode())
        return dict(package_id=package['package_id'], artifact_id=artifact, contract=package['contract']['id'],
                    contract_sha256=digest, tests=[t['id'] for t in lab_task['tests']],
                    subjects={name: s['verification'] for name, s in subjects.items()},
                    payloads={name: {k: s['payload'][k] for k in ('name', 'sha256', 'size', 'format')}
                              for name, s in subjects.items() if 'payload' in s})

    def _verify_factory_stage(self, task_id, node_id, lab_task):
        from .node_check import accepted_stage
        from .taskgraph import plan_get
        node = next((item for item in plan_get(self.store, task_id)['nodes'] if item['node_id'] == node_id), None)
        if not node or node['kind'] != 'deliver':
            raise ValueError('Staged lab composition requires the contracted delivery node')
        _, check = accepted_stage(self.store, task_id, node, 'factory_stage')
        sealed = (check.get('verifier') or {}).get('sealed_artifact')
        subjects = lab_task['subjects']
        evidence = subjects.get('factory_stage') or {}
        if (not sealed or evidence.get('kind') != 'artifact' or evidence.get('transfer') != 'attach'
                or evidence.get('identity', {}).get('artifact_id') != sealed):
            raise ValueError('Staged delivery must attach the accepted factory-stage verifier artifact as factory_stage')
        stage = json.loads(self.store.artifact_bytes(task_id, sealed))
        for arm in lab_task['arms'].values():
            image = subjects[arm['subject']]
            if (image['kind'] != 'container_image' or not image.get('build_attempt_id')
                    or image['identity'].get('id') != stage.get('image_id')):
                raise ValueError('The staged lab arms must use the checked container image and name its build attempt')

    def send(self, task_id, package_id, idem_key):
        if not isinstance(idem_key, str) or not idem_key:
            raise ValueError('idem_key is required')
        try:
            package = json.loads(self.store.artifact_bytes(task_id, 'lab-package:' + package_id))
        except NotFound:
            raise ValueError('Unknown lab package; compose it first') from None
        request_id = 'labreq-' + hashlib.sha256(f'{task_id}\0{package_id}\0{idem_key}'.encode()).hexdigest()[:24]
        self.mailbox.open_request(request_id, package)
        thread = self.mailbox.thread(request_id)
        if not any(m['type'] == 'request' for m in thread['messages']):
            files = []
            for name, subject in package['subjects'].items():
                payload = subject.get('payload')
                if payload:
                    files.append(self.mailbox.attach(request_id, self._payload_path(task_id, payload),
                                                     payload['name'], payload['media_type']))
                    if files[-1]['sha256'] != payload['sha256']:
                        raise ValueError(f'Payload of {name} changed after the package was sealed')
            lab_task = package['lab_task']
            self.mailbox.post(request_id, 'factory', 'request', dict(
                package_id=package_id, lab_task_id=lab_task['lab_task_id'], purpose=lab_task['purpose'],
                lab_profile=lab_task.get('constraints', {}).get('lab_profile') or contract_view(package['contract']['document'])['target']),
                files)
        self._observation(task_id, request_id + ':request', dict(
            kind='lab_request', values=dict(request_id=request_id, package_id=package_id, idem_key=idem_key,
                                            lab_task_id=package['lab_task']['lab_task_id'], contract=package['contract']['id']),
            source_artifacts=['lab-package:' + package_id],
            limitations='A request records what was asked of a lab, not that it was done.'))
        return self.status(task_id, request_id)

    def status(self, task_id, request_id):
        package = self._package_for(task_id, request_id)
        route = self._advance(request_id, package)
        thread = self.mailbox.thread(request_id)
        accepted = next((m for m in thread['messages'] if m['type'] == 'accepted'), None)
        return dict(request_id=request_id, state=thread['state'], route=route or self.route,
                    lab=(accepted or {}).get('body', {}).get('lab'),
                    messages=[dict(id=m['id'], type=m['type'], at=m['at'],
                                   note=str(m['body'].get('note') or m['body'].get('reason') or m['body'].get('text') or '')[:300])
                              for m in thread['messages']],
                    open_questions=thread['open_questions'], invalid=thread['invalid'], ignored=thread['ignored'])

    def cancel(self, task_id, request_id, reason=None):
        self._package_for(task_id, request_id)
        self.mailbox.post(request_id, 'factory', 'cancel', dict(reason=reason or 'cancelled by the factory'))
        return self.status(task_id, request_id)

    def ask(self, task_id, request_id, question, wants=None):
        package = self._package_for(task_id, request_id)
        if package['lab_task'].get('questions', {}).get('allowed') is False:
            raise ValueError('This lab task does not allow questions')
        if not isinstance(question, str) or not question.strip():
            raise ValueError('question must be text')
        if wants is not None and (not isinstance(wants, dict) or set(wants) - {'files', 'metrics', 'tests'}
                                  or any(not isinstance(v, list) or not all(isinstance(i, str) for i in v) for v in wants.values())):
            raise ValueError('wants may list files, metrics and tests by name')
        message = self.mailbox.post(request_id, 'factory', 'question', dict(text=question.strip(), **({'wants': wants} if wants else {})))
        return dict(request_id=request_id, question=message['id'])

    def _ingest_files(self, task_id, request_id, files):
        stored = []
        for reference in files:
            path = self.mailbox.file_path(request_id, reference)
            artifact = f'{request_id}:file:{reference["sha256"][:16]}:{reference["name"]}'
            self.store.put_artifact(task_id, artifact, path, reference.get('media_type') or 'application/octet-stream', None)
            stored.append(dict(reference, artifact_id=artifact))
        return stored

    def reply(self, task_id, request_id, question):
        self._package_for(task_id, request_id)
        thread = self.mailbox.thread(request_id)
        if question not in {m['id'] for m in thread['messages'] if m['type'] == 'question'}:
            raise ValueError('Unknown question id for this request')
        answer_id = thread['answered'].get(question)
        if answer_id is None:
            return dict(request_id=request_id, question=question, state='pending')
        answer = next(m for m in thread['messages'] if m['id'] == answer_id)
        files = self._ingest_files(task_id, request_id, answer['files'])
        record = self._record(task_id, f'{request_id}:answer:{question}.json',(canonical(answer) + '\n').encode())
        observation = self._observation(task_id, f'{request_id}:answer:{question}', dict(
            kind='lab_answer', values=dict(request_id=request_id, question=question, answer=answer['body'], files=files),
            source_artifacts=[record, *(f['artifact_id'] for f in files)],
            limitations='An answer is the lab agent\'s statement; it is checked only for file digests.'))
        return dict(request_id=request_id, question=question, state='answered', answer=answer['body'],
                    files=files, evidence_id=observation['obs_id'])

    def report(self, task_id, request_id):
        package = self._package_for(task_id, request_id)
        self._advance(request_id, package)
        thread = self.mailbox.thread(request_id)
        if thread['state'] != 'reported':
            return dict(request_id=request_id, state=thread['state'], report=None,
                        note='No report yet' if thread['state'] not in {'rejected', 'failed', 'cancelled'}
                        else 'The request ended without a report')
        ignored = {row['id'] for row in thread['ignored']}
        message = next(m for m in sorted(thread['messages'], key=lambda m: (m['sender'], m['seq']))
                       if m['type'] == 'report' and m['id'] not in ignored)
        body = message['body']
        found = report_problems(body, dict(package, package_id=package['package_id']))
        if not found and body.get('request_id') != request_id:
            found.append('request_id: names another request')
        listed = {f['name']: f for f in body.get('files', [])} if isinstance(body.get('files'), list) else {}
        attached = {f.get('name'): f for f in message['files']}
        for name, reference in listed.items():
            if attached.get(name, {}).get('sha256') != reference.get('sha256'):
                found.append(f'files/{name}: not attached to the report message with this digest')
        files = []
        if not found:
            try:
                files = self._ingest_files(task_id, request_id, message['files'])
            except MailboxError as exc:
                found.append(str(exc))
        record = self._record(task_id, f'{request_id}:report.json',(canonical(message) + '\n').encode())
        valid = not found
        values = dict(request_id=request_id, package_id=package['package_id'], valid=valid, problems=found,
                      lab_task_id=package['lab_task']['lab_task_id'], contract=package['contract']['id'],
                      contract_sha256=package['contract']['sha256'])
        if valid:
            values.update(outcome=body['outcome'], lab=body['lab'], summary=body['summary'], setup=body.get('setup', {}),
                          results=body['results'], checks=body['checks'], not_run=body['not_run'], files=files)
        limits = '; '.join(body.get('limits', [])) if valid else 'Report rejected by the lab manager: ' + '; '.join(found[:10])
        observation = self._observation(task_id, f'{request_id}:report', dict(
            kind='lab_report', values=values, source_artifacts=[record, *(f['artifact_id'] for f in files)],
            limitations=limits or 'none stated'))
        return dict(request_id=request_id, state='reported', valid=valid, problems=found,
                    evidence_id=observation['obs_id'], report=values)


def dispatch(store, task_id, operation, inputs):
    from .api import fields
    if hasattr(store, '_check'):
        store._check(task_id, write=True)
        host = store._store
    else:
        host = store
    manager = LabManager(host)
    if operation == 'source_bundle':
        fields(inputs, {'checkout', 'base', 'recipe', 'repository', 'include_base', 'worktree', 'deps', 'extra_flags'},
               {'checkout', 'base', 'recipe'})
        if host is not store:  # an agent: its checkouts must be in its workspace
            import os
            roots = [Path(v).expanduser().resolve() for v in (os.environ.get('FACTORY_WORKSPACE'),) if v]
            for path in [inputs['checkout'], *(d.get('checkout', '') for d in inputs.get('deps') or [])]:
                if not roots or not any(Path(path).expanduser().resolve().is_relative_to(root) for root in roots):
                    raise ScopeDenied('A checkout to bundle must be inside the agent workspace')
        return manager.source_bundle(task_id, **inputs)
    if operation == 'draft_task':
        fields(inputs, {'arm_subjects', 'subjects', 'contract_id', 'lab_task_id', 'purpose'}, {'arm_subjects', 'subjects'})
        return manager.draft_task(task_id, **inputs)
    if operation == 'compose':
        fields(inputs, {'lab_task', 'contract_id', 'node_id'}, {'lab_task'})
        return manager.compose(task_id, **inputs)
    if operation == 'send':
        fields(inputs, {'package_id', 'idem_key'}, {'package_id', 'idem_key'})
        return manager.send(task_id, **inputs)
    if operation in {'status', 'report'}:
        fields(inputs, {'request_id'}, {'request_id'})
        return getattr(manager, operation)(task_id, **inputs)
    if operation == 'cancel':
        fields(inputs, {'request_id', 'reason'}, {'request_id'})
        return manager.cancel(task_id, **inputs)
    if operation == 'ask':
        fields(inputs, {'request_id', 'question', 'wants'}, {'request_id', 'question'})
        return manager.ask(task_id, **inputs)
    if operation == 'reply':
        fields(inputs, {'request_id', 'question'}, {'request_id', 'question'})
        return manager.reply(task_id, **inputs)
    raise ValueError('Unknown lab manager capability')

