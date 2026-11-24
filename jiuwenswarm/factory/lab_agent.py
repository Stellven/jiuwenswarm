"""Lab agent side of the lab mailbox, with stand-ins until a real lab agent exists.

Any lab agent works the same way: read a request's package (``factory.lab-package/1``),
accept or reject it, set up the lab, answer questions and post one report
(``factory.lab-report/1``). ``LabAgent`` does those steps and checks a report against
the package before posting it, so a lab learns about a bad report before the factory does.

Stand-ins, chosen with ``serve --adapter``:

* ``operator`` (no adapter): a person or a coding agent at the lab machine drives the
  steps by hand through this command line. This is what the lead engineer did on
  2026-11-20 for the DGX Spark contract, now through a recorded protocol.
* ``queue``: the factory's own lab queue (``Manager``) runs format-1 contracts for
  container images it built, as ``factory.lab_client`` did before.
* ``command``: a lab command is run for each request with the package path and an
  output directory, and must write ``report.json`` and ``files/``. Shipped subjects
  (``transfer: attach``) are fetched and checked first; ``{payloads}`` names a JSON file
  mapping each subject to its local file (and ``--load-images`` loads image archives).

The mailbox is a directory or an HTTP address (``--mailbox http://host:8790`` with
``$FACTORY_LAB_TOKEN``), so the lab agent can run on another machine.

Every stand-in also answers questions that ask for files, metrics or tests already
in its report. Other questions wait for the operator.

    python -m jiuwenswarm.factory.lab_agent inbox
    python -m jiuwenswarm.factory.lab_agent show <request>
    python -m jiuwenswarm.factory.lab_agent fetch <request> --load
    python -m jiuwenswarm.factory.lab_agent accept <request> --note "..."
    python -m jiuwenswarm.factory.lab_agent report <request> report.json --file ttft=samples.json
    python -m jiuwenswarm.factory.lab_agent serve --adapter queue --once
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time

from .lab_mailbox import MailboxError, TERMINAL, canonical, default_root, now, open_mailbox

VERSION = '1'


def _contract_doc(package):
    return package['contract']['document']


def lab_profile(package):
    from .lab_manager import contract_view
    return (package['lab_task'].get('constraints', {}).get('lab_profile')
            or contract_view(_contract_doc(package))['target'])


def accepted_by(thread):
    """Name of the lab agent that accepted the request, or None."""
    message = next((m for m in thread['messages'] if m['type'] == 'accepted'), None)
    return ((message or {}).get('body', {}).get('lab') or {}).get('name')


def owned(agent, thread):
    """A stand-in acts on an accepted request only when it accepted it itself."""
    owner = accepted_by(thread)
    return owner is None or owner == agent.name


class LabAgent:
    def __init__(self, mailbox, name='operator', kind='operator', profile=None):
        self.mailbox, self.name, self.kind, self.profile = mailbox, name, kind, profile

    @property
    def identity(self):
        return dict(name=self.name, kind=self.kind, version=VERSION)

    def matches(self, package):
        return self.profile is None or lab_profile(package) in {None, self.profile}

    def inbox(self, everything=False):
        rows = []
        for request_id in self.mailbox.requests():
            package = self.mailbox.package(request_id)
            if not self.matches(package):
                continue
            thread = self.mailbox.thread(request_id)
            if everything or thread['state'] not in TERMINAL or thread['open_questions']:
                rows.append(dict(request_id=request_id, state=thread['state'], lab_task_id=package['lab_task']['lab_task_id'],
                                 contract=package['contract']['id'], profile=lab_profile(package),
                                 open_questions=thread['open_questions'], origin_task=package['origin']['task_id']))
        return rows

    def show(self, request_id):
        package = self.mailbox.package(request_id)
        return dict(package=package, thread=self.mailbox.thread(request_id))

    def fetch(self, request_id, load=False, build=False, build_cache=None):
        """Download and check every shipped subject.

        ``load`` runs ``docker load`` on image archives; ``build`` assembles source bundles
        into images on this machine (``lab_build``).
        """
        package = self.mailbox.package(request_id)
        request = self.mailbox.latest(request_id, 'request')
        sent = {f['sha256']: f for f in (request or {}).get('files', [])}
        fetched = {}
        for name, subject in package['subjects'].items():
            payload = subject.get('payload')
            if not payload:
                continue
            if payload['sha256'] not in sent:
                raise MailboxError(f'subject {name}: its payload was not sent with the request')
            path = self.mailbox.file_path(request_id, dict(name=payload['name'], sha256=payload['sha256'], size=payload['size']))
            row = dict(path=str(path), sha256=payload['sha256'], size=payload['size'], format=payload['format'])
            if payload['format'] == 'docker-archive':
                from .lab_payload import archive_image_ids, load_image
                expected = subject['identity'].get('id') or payload.get('image_id')
                found = archive_image_ids(path)
                if not found or (expected and expected not in found):
                    raise MailboxError(f'subject {name}: the archive holds {found[:1] or "no image"}, not {expected}')
                row['image_id'] = expected or found[0]
                if load:
                    row['loaded'] = load_image(path, expected)
            elif payload['format'] == 'source-bundle':
                from .lab_build import assemble, read_bundle
                if read_bundle(path)['source']['head_tree'] != payload['head_tree']:
                    raise MailboxError(f'subject {name}: the source bundle is not the sealed tree')
                row.update(head_tree=payload['head_tree'], recipe=payload['recipe'])
                if build:
                    record = assemble(path, build_cache or os.environ.get('FACTORY_LAB_BUILD_CACHE', '~/.jiuwenswarm-factory/lab-build'))
                    row['build'] = record
                    if record.get('image_id'):
                        row['image_id'] = record['image_id']
            fetched[name] = row
        return fetched

    def accept(self, request_id, note=None):
        return self.mailbox.post(request_id, 'lab', 'accepted', dict(lab=self.identity, **({'note': note} if note else {})))

    def reject(self, request_id, reason):
        return self.mailbox.post(request_id, 'lab', 'rejected', dict(lab=self.identity, reason=reason))

    def progress(self, request_id, note, data=None):
        return self.mailbox.post(request_id, 'lab', 'progress', dict(note=note, **({'data': data} if data else {})))

    def fail(self, request_id, reason, problems=None):
        return self.mailbox.post(request_id, 'lab', 'failed', dict(reason=reason, **({'problems': problems} if problems else {})))

    def cancelled(self, request_id, note='cancelled as the factory asked'):
        return self.mailbox.post(request_id, 'lab', 'cancelled', dict(note=note))

    def _attach(self, request_id, files):
        refs = []
        for name, path in (files or {}).items():
            media = 'application/json' if str(path).endswith('.json') else 'text/plain' if str(path).endswith(('.txt', '.md', '.log', '.csv')) else 'application/octet-stream'
            refs.append(self.mailbox.attach(request_id, path, name, media))
        return refs

    def answer(self, request_id, question, text, data=None, files=None, refs=()):
        attached = self._attach(request_id, files) + list(refs)
        return self.mailbox.post(request_id, 'lab', 'answer',
                                 dict(question=question, text=text, **({'data': data} if data is not None else {})), attached)

    def complete_report(self, request_id, report, attached):
        package = self.mailbox.package(request_id)
        filled = dict(report)
        filled.setdefault('schema', 'factory.lab-report/1')
        filled.update(request_id=request_id, package_id=package['package_id'],
                      lab_task_id=package['lab_task']['lab_task_id'],
                      contract=dict(id=package['contract']['id'], sha256=package['contract']['sha256']))
        filled.setdefault('lab', self.identity)
        for key in ('results', 'checks', 'not_run', 'limits'):
            filled.setdefault(key, [])
        listed = {f['name']: f for f in filled.get('files', [])}
        filled['files'] = [dict(ref, **{k: v for k, v in listed.get(ref['name'], {}).items() if k == 'media_type'})
                           for ref in attached]
        return filled

    def check_report(self, request_id, report, files=None):
        """Problems a report would have, without posting it."""
        from .lab_manager import report_problems
        package = self.mailbox.package(request_id)
        attached = [dict(name=name, sha256='0' * 64, size=0) for name in (files or {})]
        return report_problems(self.complete_report(request_id, report, attached), package)

    def report(self, request_id, report, files=None):
        from .lab_manager import report_problems
        package = self.mailbox.package(request_id)
        problems = self.check_report(request_id, report, files)
        if problems:
            raise MailboxError('Report does not answer the package: ' + '; '.join(problems[:20]))
        attached = self._attach(request_id, files)
        filled = self.complete_report(request_id, report, attached)
        problems = report_problems(filled, package)
        if problems:
            raise MailboxError('Report does not answer the package: ' + '; '.join(problems[:20]))
        return self.mailbox.post(request_id, 'lab', 'report', filled, attached)

    def auto_answer(self, request_id):
        """Answer open questions that ask only for files, metrics or tests already reported."""
        thread = self.mailbox.thread(request_id)
        report = next((m for m in thread['messages'] if m['type'] == 'report'), None)
        answered = []
        if report is None:
            return answered
        body = report['body']
        files = {f['name']: f for f in report['files']}
        for question in [m for m in thread['messages'] if m['id'] in thread['open_questions']]:
            wants = question['body'].get('wants')
            if not wants:
                continue
            missing = [f for f in wants.get('files', []) if f not in files]
            metrics = set(wants.get('metrics', []))
            tests = set(wants.get('tests', []))
            reported_metrics = {row['metric'] for row in body['results']}
            reported_tests = {row['test_id'] for row in body['results'] + body['checks'] + body['not_run']}
            missing += sorted(metrics - reported_metrics) + sorted(tests - reported_tests)
            if missing:
                continue
            rows = [row for row in body['results'] if row['metric'] in metrics or row['test_id'] in tests]
            checks = [row for row in body['checks'] if row['test_id'] in tests]
            self.answer(request_id, question['id'], 'From the posted report.',
                        data=dict(results=rows, checks=checks), refs=[files[f] for f in wants.get('files', [])])
            answered.append(question['id'])
        return answered


def build_summary(row):
    """The report entry for a subject this lab assembled from source."""
    record = row['build']
    return {k: record[k] for k in ('head_tree', 'base_commit', 'recipe', 'machine', 'warm', 'seconds', 'executable_sha256',
                                   'image_id', 'jobs', 'generator', 'ccache') if k in record}


# ---- stand-in adapters -----------------------------------------------------------------
class QueueAdapter:
    """Runs format-1 contracts on the factory's own lab queue for images the factory built."""
    kind = 'queue'

    def __init__(self, home, state_root):
        self.home = Path(home).expanduser()
        self.state_root = Path(state_root)

    def _state(self, request_id):
        path = self.state_root / (request_id + '.json')
        return path, (json.loads(path.read_text()) if path.is_file() else {})

    def _save(self, path, state):
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.pending-')
        with os.fdopen(fd, 'w') as stream:
            json.dump(state, stream, sort_keys=True)
        os.replace(temporary, path)

    def unsupported(self, package):
        document = _contract_doc(package)
        if package['contract']['format'] != 1:
            return 'the factory lab queue runs format-1 contracts only'
        if document.get('external_execution_only'):
            return 'the contract requires execution outside the factory lab queue'
        lab_task = package['lab_task']
        for arm, spec in lab_task['arms'].items():
            subject = package['subjects'][spec['subject']]
            if subject['kind'] != 'container_image' or not subject.get('build_attempt_id'):
                return f'arm {arm}: the queue runs container images built by the factory (with build_attempt_id)'
            if spec.get('args'):
                return f'arm {arm}: the queue cannot change the scored argv'
        for test in lab_task['tests']:
            unknown = [m for m in test.get('measure', []) if m not in {'decode_ms_per_token', 'ab_ratio'}]
            if unknown:
                return f'test {test["id"]}: the queue cannot measure {", ".join(unknown)}'
            if test.get('compare') and set(test['arms']) != {test['compare']['base'], test['compare']['candidate']}:
                return f'test {test["id"]}: an A/B test names exactly its base and candidate arms'
        return None

    def _manager(self):
        from .manager import Manager
        from .store import Store
        store = Store(self.home)
        return store, Manager(store, store.home / 'lab-spool')

    def submit(self, request_id, package):
        store, manager = self._manager()
        try:
            task_id = package['origin']['task_id']
            lab_task = package['lab_task']
            contract_id = package['contract']['id']
            submitted = []

            def image(arm):
                subject = package['subjects'][lab_task['arms'][arm]['subject']]
                return dict(tag=subject['identity']['tag'], id=subject['identity']['id']), subject['build_attempt_id']

            for test in lab_task['tests']:
                compare = test.get('compare')
                if compare:
                    (base, _), (candidate, _) = image(compare['base']), image(compare['candidate'])
                    component = compare.get('component') or store.get_task(task_id).get('component_cc')
                    attempt = manager.ab_submit(task_id, base, candidate, lab_task['arms'][compare['base']].get('env', {}),
                                                lab_task['arms'][compare['candidate']].get('env', {}), compare.get('rounds', 2),
                                                f'{request_id}:{test["id"]}', component, contract_id)
                    submitted.append(dict(test=test['id'], arm=None, attempt_id=attempt['attempt_id'], mode='ab'))
                    continue
                for arm in test['arms']:
                    ref, build = image(arm)
                    admission = manager.admit(task_id, ref, build)
                    attempt = manager.submit_run(task_id, admission['admission_id'], contract_id,
                                                 dict(env=lab_task['arms'][arm].get('env', {})), f'{request_id}:{test["id"]}:{arm}')
                    submitted.append(dict(test=test['id'], arm=arm, attempt_id=attempt['attempt_id'], mode='run'))
            return submitted
        finally:
            store.close()

    def poll(self, submitted):
        store, manager = self._manager()
        try:
            rows = []
            for row in submitted:
                read = manager.ab_result if row['mode'] == 'ab' else manager.result
                rows.append(dict(row, result=read(row['attempt_id'])))
            return rows
        finally:
            store.close()

    def cancel(self, submitted):
        store, manager = self._manager()
        try:
            for row in submitted:
                try:
                    manager.cancel(row['attempt_id'])
                except Exception:  # an attempt that already ended cannot be cancelled
                    pass
        finally:
            store.close()

    @staticmethod
    def build_report(package, polled, directory):
        lab_task = package['lab_task']
        tests = {t['id']: t for t in lab_task['tests']}
        results, checks, not_run, files = [], [], [], {}
        for row in polled:
            test, result = tests[row['test']], row['result']
            name = f'attempt-{row["test"]}-{row["arm"] or "ab"}.json'
            path = Path(directory) / name
            path.write_text(canonical(result))
            files[name] = path
            outcome = result.get('execution_outcome')
            evaluation = result.get('evaluation') or {}
            if row['mode'] == 'ab':
                values = result.get('ab_result') or {}
                gate = values.get('gate')
                if 'check' in test:
                    verdict = 'pass' if gate in {'accept', 'pass'} else 'fail' if gate in {'reject', 'fail'} else 'not_run'
                    checks.append(dict(test_id=test['id'], check=test['check'], verdict=verdict,
                                       detail=f'A/B gate {gate}; outcome {outcome}'))
                if 'ab_ratio' in test.get('measure', []):
                    if isinstance(values.get('ratio'), (int, float)):
                        results.append(dict(test_id=test['id'], arm=test['compare']['candidate'], metric='ab_ratio',
                                            unit='ratio', value=values['ratio'], statistic='ratio'))
                    else:
                        not_run.append(dict(test_id=test['id'], reason=f'no A/B ratio; outcome {outcome}'))
                continue
            if 'check' in test:
                correctness = evaluation.get('correctness')
                verdict = {'pass': 'pass', 'fail': 'fail'}.get(correctness, 'not_run')
                checks.append(dict(test_id=test['id'], check=test['check'], arm=row['arm'], verdict=verdict,
                                   detail=f'correctness {correctness}; outcome {outcome}'))
            if 'decode_ms_per_token' in test.get('measure', []):
                value = ((evaluation.get('inputs') or {}).get('details') or {}).get('eval_ms_per_token')
                if isinstance(value, (int, float)):
                    results.append(dict(test_id=test['id'], arm=row['arm'], metric='decode_ms_per_token',
                                        unit='ms/token', value=value, statistic='single'))
                elif not any(r['test_id'] == test['id'] for r in not_run):
                    not_run.append(dict(test_id=test['id'], reason=f'no decode timing in the lab result; outcome {outcome}'))
        verdicts = [c['verdict'] for c in checks]
        incomplete = bool(not_run) or 'not_run' in verdicts
        return dict(outcome='partial' if incomplete else 'completed',
                    summary=f'{len(polled)} lab attempt(s) on the factory lab queue; '
                            f'{verdicts.count("pass")} check(s) passed, {verdicts.count("fail")} failed.',
                    setup=dict(runner='factory lab queue (jobq)', deviations=[]),
                    results=results, checks=checks, not_run=not_run,
                    limits=['Run by the factory lab queue stand-in, not an independent lab agent.']), files

    def step(self, agent, request_id, package, thread):
        path, state = self._state(request_id)
        status = thread['state']
        if not owned(agent, thread):
            return None
        if status == 'requested':
            reason = self.unsupported(package)
            return agent.reject(request_id, reason) if reason else agent.accept(request_id, 'factory lab queue')
        if status == 'cancel_requested':
            self.cancel(state.get('submitted', []))
            return agent.cancelled(request_id)
        if status not in {'accepted', 'running'}:
            return None
        if 'submitted' not in state:
            try:
                state['submitted'] = self.submit(request_id, package)
            except Exception as exc:
                return agent.fail(request_id, f'submission failed: {type(exc).__name__}: {str(exc)[:300]}')
            self._save(path, state)
            return agent.progress(request_id, 'submitted to the factory lab queue',
                                  dict(attempts=[r['attempt_id'] for r in state['submitted']]))
        polled = self.poll(state['submitted'])
        if not all(row['result'].get('state') in {'succeeded', 'failed', 'cancelled'} for row in polled):
            return None
        with tempfile.TemporaryDirectory() as scratch:
            report, files = self.build_report(package, polled, scratch)
            return agent.report(request_id, report, files)


class CommandAdapter:
    """Runs one lab command per request: ``COMMAND {package} {output}``.

    The command reads the package, runs the lab and writes ``{output}/report.json`` (the
    report without the identity fields, which are filled in) and any files under
    ``{output}/files/``. Its exit status 0 means a report was written.
    """
    kind = 'command'

    def __init__(self, command, work_root, timeout_s=None, load_images=False, build_sources=False, build_cache=None):
        self.command, self.work_root, self.timeout_s = command, Path(work_root), timeout_s
        self.load_images, self.build_sources, self.build_cache = load_images, build_sources, build_cache

    def step(self, agent, request_id, package, thread):
        status = thread['state']
        if not owned(agent, thread):
            return None
        if status == 'requested':
            return agent.accept(request_id, 'lab command ' + shlex.split(self.command)[0])
        if status == 'cancel_requested':
            return agent.cancelled(request_id)
        if status == 'running':
            # The command runs inside one step, so a running request seen later was interrupted.
            return agent.fail(request_id, 'the lab command was interrupted before it reported; send the request again')
        if status != 'accepted':
            return None
        work = self.work_root / request_id
        output = work / 'out'
        (output / 'files').mkdir(parents=True, exist_ok=True)
        package_path = work / 'package.json'
        package_path.write_text(canonical(package))
        try:
            payloads = agent.fetch(request_id, self.load_images, self.build_sources, self.build_cache)
        except (MailboxError, ValueError, OSError) as exc:
            return agent.fail(request_id, f'could not fetch the shipped subjects: {str(exc)[:400]}')
        payloads_path = work / 'payloads.json'
        payloads_path.write_text(canonical(payloads))
        argv = [part.replace('{package}', str(package_path)).replace('{output}', str(output))
                .replace('{payloads}', str(payloads_path)) for part in shlex.split(self.command)]
        limit = self.timeout_s or package['lab_task'].get('constraints', {}).get('wall_clock_s') or 6 * 3600
        agent.progress(request_id, 'lab command started', dict(payloads={k: v['sha256'] for k, v in payloads.items()}) if payloads else None)
        try:
            process = subprocess.run(argv, capture_output=True, text=True, timeout=limit,
                                     env=dict(os.environ, FACTORY_LAB_PACKAGE=str(package_path), FACTORY_LAB_OUTPUT=str(output),
                                              FACTORY_LAB_PAYLOADS=str(payloads_path)))
        except subprocess.TimeoutExpired:
            return agent.fail(request_id, f'lab command exceeded {limit} s')
        (work / 'stdout.txt').write_text(process.stdout)
        (work / 'stderr.txt').write_text(process.stderr)
        report_path = output / 'report.json'
        if process.returncode != 0 or not report_path.is_file():
            tail = ' | '.join(process.stderr.strip().splitlines()[-3:])[-400:]
            return agent.fail(request_id, f'lab command exited {process.returncode} without a report: {tail}')
        try:
            report = json.loads(report_path.read_text())
            builds = {name: build_summary(row) for name, row in payloads.items() if row.get('build')}
            if builds and 'builds' not in report:
                report['builds'] = builds
            files = {p.name: p for p in sorted((output / 'files').iterdir()) if p.is_file()}
            return agent.report(request_id, report, files)
        except (ValueError, MailboxError) as exc:
            return agent.fail(request_id, 'lab command wrote an invalid report', [str(exc)[:1000]])


def serve(agent, adapter, once=False, interval_s=10.0, log=print):
    while True:
        for request_id in agent.mailbox.requests():
            try:
                package = agent.mailbox.package(request_id)
                if not agent.matches(package):
                    continue
                thread = agent.mailbox.thread(request_id)
                if adapter is not None and thread['state'] not in TERMINAL:
                    message = adapter.step(agent, request_id, package, thread)
                    if message:
                        log(f'{now()} {request_id} {message["type"]}')
                for question in agent.auto_answer(request_id):
                    log(f'{now()} {request_id} answered {question}')
            except Exception as exc:  # one bad request never stops the lab
                log(f'{now()} {request_id} error {type(exc).__name__}: {str(exc)[:300]}')
        if once:
            return
        time.sleep(interval_s)


# ---- command line ----------------------------------------------------------------------
def _files(values):
    result = {}
    for value in values or []:
        name, _, path = value.partition('=')
        if not path:
            raise SystemExit('--file takes NAME=PATH')
        result[name] = Path(path)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(prog='lab-agent', description='Work lab requests from the factory lab mailbox.')
    parser.add_argument('--mailbox', help='mailbox directory or http(s):// address (default: $FACTORY_LAB_MAILBOX or $FACTORY_HOME/lab-mailbox)')
    parser.add_argument('--token', help='token for an HTTP mailbox (default: $FACTORY_LAB_TOKEN or $FACTORY_LAB_TOKEN_FILE)')
    parser.add_argument('--state', help='where this lab agent keeps its own state and work (default: <mailbox>/lab-state, or ~/.jiuwenswarm-factory/lab-agent for an HTTP mailbox)')
    parser.add_argument('--lab', default=os.environ.get('FACTORY_LAB_NAME', 'operator'), help='this lab agent\'s name')
    parser.add_argument('--profile', help='only take requests for this lab profile, for example spark-gb10')
    sub = parser.add_subparsers(dest='command', required=True)
    inbox = sub.add_parser('inbox', help='list open requests and open questions')
    inbox.add_argument('--all', action='store_true')
    fetch = sub.add_parser('fetch', help='download and check the shipped subjects of a request')
    fetch.add_argument('request_id')
    fetch.add_argument('--load', action='store_true', help='docker load image archives after checking them')
    fetch.add_argument('--build', action='store_true', help='assemble source bundles into images on this machine')
    for name in ('show', 'accept', 'reject', 'progress', 'fail', 'cancelled'):
        command = sub.add_parser(name)
        command.add_argument('request_id')
        if name != 'show':
            command.add_argument('--note' if name in {'accept', 'progress', 'cancelled'} else '--reason',
                                 required=name in {'reject', 'fail', 'progress'})
    answer = sub.add_parser('answer', help='answer a question')
    answer.add_argument('request_id')
    answer.add_argument('question')
    answer.add_argument('--text', required=True)
    answer.add_argument('--data', help='JSON value to include')
    answer.add_argument('--file', action='append', help='NAME=PATH to attach')
    report = sub.add_parser('report', help='check and post the report')
    report.add_argument('request_id')
    report.add_argument('report', help='report JSON; identity fields are filled in')
    report.add_argument('--file', action='append', help='NAME=PATH to attach')
    report.add_argument('--check', action='store_true', help='only check, do not post')
    run = sub.add_parser('serve', help='run a stand-in lab agent')
    run.add_argument('--adapter', choices=['operator', 'queue', 'command'], default='operator')
    run.add_argument('--command', dest='lab_command', help='for --adapter command: COMMAND {package} {output}')
    run.add_argument('--home', help='for --adapter queue: the factory home (default $FACTORY_HOME)')
    run.add_argument('--load-images', action='store_true', help='for --adapter command: docker load shipped images first')
    run.add_argument('--build-sources', action='store_true', help='for --adapter command: assemble shipped source bundles first')
    run.add_argument('--once', action='store_true')
    run.add_argument('--interval', type=float, default=10.0)
    args = parser.parse_args(argv)
    spec = args.mailbox or os.environ.get('FACTORY_LAB_MAILBOX') or default_root(args.home if args.command == 'serve' else None)
    mailbox = open_mailbox(spec, token=args.token)
    remote = str(spec).startswith(('http://', 'https://'))
    state = Path(args.state).expanduser() if args.state else (
        Path('~/.jiuwenswarm-factory/lab-agent').expanduser() if remote else Path(spec).expanduser())
    kind = args.adapter if args.command == 'serve' and args.adapter != 'operator' else 'operator'
    agent = LabAgent(mailbox, args.lab, kind, args.profile)
    try:
        if args.command == 'inbox':
            result = agent.inbox(args.all)
        elif args.command == 'show':
            result = agent.show(args.request_id)
        elif args.command == 'fetch':
            result = agent.fetch(args.request_id, args.load, args.build)
        elif args.command == 'accept':
            result = agent.accept(args.request_id, args.note)
        elif args.command == 'reject':
            result = agent.reject(args.request_id, args.reason)
        elif args.command == 'progress':
            result = agent.progress(args.request_id, args.note)
        elif args.command == 'fail':
            result = agent.fail(args.request_id, args.reason)
        elif args.command == 'cancelled':
            result = agent.cancelled(args.request_id, args.note or 'cancelled as the factory asked')
        elif args.command == 'answer':
            result = agent.answer(args.request_id, args.question, args.text,
                                  json.loads(args.data) if args.data else None, _files(args.file))
        elif args.command == 'report':
            body = json.loads(Path(args.report).read_text())
            if args.check:
                problems = agent.check_report(args.request_id, body, _files(args.file))
                result = dict(valid=not problems, problems=problems)
            else:
                result = agent.report(args.request_id, body, _files(args.file))
        else:
            adapter = None
            if args.adapter == 'queue':
                from .telemetry import home_path
                home = home_path(args.home)
                adapter = QueueAdapter(home, state / 'lab-state' / args.lab)
            elif args.adapter == 'command':
                if not args.lab_command:
                    raise SystemExit('--adapter command needs --command')
                adapter = CommandAdapter(args.lab_command, state / 'lab-work' / args.lab, load_images=args.load_images,
                                         build_sources=args.build_sources)
            serve(agent, adapter, args.once, args.interval)
            return 0
    except (MailboxError, ValueError) as exc:
        print(json.dumps(dict(error=str(exc))), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
