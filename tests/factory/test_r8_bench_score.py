"""Exercise the final paired-scoring contract without a model or network."""
import csv
import hashlib
import json
import tarfile
from types import SimpleNamespace

import pytest

from jiuwenswarm.factory import capped_run
from jiuwenswarm.factory.ccs.paired_accuracy import paired
from scripts.factory import lab_v4_quiet, r8_bench_score


@pytest.fixture
def proposal(tmp_path):
    dataset = tmp_path / 'data' / 'test'
    dataset.mkdir(parents=True)
    with (dataset / 'subject_test.csv').open('w', newline='') as handle:
        csv.writer(handle).writerows((f'Question {i}?', 'One', 'Two', 'Three', 'Four', 'ABCD'[i % 4])
                                     for i in range(270))
    archive = tmp_path / 'data.tar'
    with tarfile.open(archive, 'w') as tar:
        tar.add(dataset, arcname='data/test')
    questions = paired.mmlu_order(dataset)
    ids = [q['id'] for q in questions[:250]]
    history = tmp_path / 'history.json'
    rows = {q['id']: dict(answer=q['answer'], prompt_sha256=paired.sha(paired.prompt(q))) for q in questions}
    history.write_text(json.dumps(dict(rows=dict(A=rows, B=rows))))
    binary = tmp_path / 'llama-server'
    binary.write_text('fixture server')
    packs = {}
    for pack in ('NVFP4', 'MIXED_2BIT'):
        manifest = tmp_path / f'{pack}.manifest.json'
        manifest.write_text(pack)
        packs[pack] = dict(first_shard=str(tmp_path / f'{pack}.gguf'), manifest=str(manifest),
                           manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())
    return dict(
        mmlu=dict(dataset_path=str(dataset), archive_path=str(archive),
                  archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                  order_seed=paired.SEED, historical_full_order_sha256=paired.sha(json.dumps([q['id'] for q in questions])),
                  historical_case_source=dict(path=str(history), sha256=hashlib.sha256(history.read_bytes()).hexdigest(),
                                              records=['/rows/A', '/rows/B']),
                  question_ids_in_order=ids, question_ids_sha256=paired.sha(json.dumps(ids, separators=(',', ':'))),
                  planned_looks=[50, 100, 160, 250], z=2.65, margin_points=5, role_reference='7', role_candidate='8',
                  verifier='eval.paired_accuracy'),
        engine=dict(required_verified_image_id='sha256:fixture',
                    required_image_executable_sha256=hashlib.sha256(binary.read_bytes()).hexdigest()),
        pack_pins=packs, settings_args=dict(ctx='-c', np='-np', batch='-b', ubatch='-ub', moe_cache_mib='--moe-cache-mib'),
        required_loads=[dict(id=leg, recipe='paired_mmlu_score', request_plan='mmlu250', pack=pack, ctx=32768, np=32,
                             batch=4096, ubatch=4096, moe_cache_mib=49152, extra_args=['-kvu'])
                        for leg, pack in r8_bench_score.PACKS.items()],
        request_plans=dict(mmlu250=dict(question_scores=250, request_batches=[32] * 7 + [26], path='/completion',
                                        **r8_bench_score.REQUEST)),
    )


class FakeServer:
    def __init__(self, proposal, leg_id, directory, request_error=None, duplicate=False):
        leg = next(record for record in proposal['required_loads'] if record['id'] == leg_id)
        self.proc = SimpleNamespace(pid=-1, poll=lambda: None, returncode=None)
        self.watches = []
        self.requests = []
        self.run = SimpleNamespace(watch=self.watches.append, log=lambda _: None, peak=4096, low=8192, cap='96G',
                                   home=directory, task=dict(resources=dict(floor_gib=8)))
        self.argv = ['systemd-run', '--scope', str(directory / 'llama-server'), '-m',
                     proposal['pack_pins'][leg['pack']]['first_shard']]
        for field, flag in proposal['settings_args'].items():
            self.argv.extend([flag, str(leg[field])])
        self.argv.extend(leg['extra_args'])
        self.log = directory / f'{leg_id}.server.log'
        self.request_error = request_error
        self.duplicate = duplicate

    def post(self, body):
        self.requests.append(body)
        if self.request_error and len(self.requests) == 1:
            raise self.request_error
        reply = []
        for index, prompt in enumerate(body['prompt']):
            q = int(prompt.split('Question ')[1].split('?')[0])
            top = [dict(token=f' {"ABCD"[q % 4]}', logprob=-0.01)]
            top.extend(dict(token=f'word{i}', logprob=-10.0) for i in range(19))
            reply.append(dict(index=0 if self.duplicate and len(self.requests) == 1 else index,
                              stop=True, truncated=False, tokens_predicted=1,
                              tokens_evaluated=42, completion_probabilities=[dict(top_logprobs=top)]))
        return list(reversed(reply))


class FakeMonitor:
    def __init__(self, server, contaminate=None, gate_failure=False, missing_evidence=False):
        self.server = server
        self.limits = dict(protocol=lab_v4_quiet.REVISED, campaign=lab_v4_quiet.EMPTY, no_builds=True,
                           max_load_1m=1.0, max_foreign_cpu_percent=50.0, sample_interval_seconds=2,
                           min_cpu_window_s=0.5, exempt_runner_tree=True)
        self.samples = []
        self.contaminate = contaminate
        self.gate_failure = gate_failure
        self.missing_evidence = missing_evidence
        self.started = 0

    def wait(self, phase, following, log):
        assert (phase, following) == ('start', 'during')
        self.started += 1
        if self.gate_failure:
            sample = self._add('start_wait', ['resident-server machine gate closed'])
            self.samples[-1]['resident_machine_gate'] = dict(ok=False)
            raise lab_v4_quiet.Breach(self.samples[sample])
        return self._add(phase), False

    def mark(self, phase, following):
        assert (phase, following) == ('end', 'between_rows')
        if self.missing_evidence:
            return self._add(phase, ['process probe unavailable (OSError)'])
        return self._add(phase, ['foreign helper process present'] if self.started == self.contaminate else [])

    def _add(self, phase, reasons=()):
        during = phase == 'end'
        self.samples.append(dict(phase=phase, ok=not reasons, reasons=list(reasons),
                                 utc='fixture', monotonic_s=len(self.samples),
                                 load_averages=[12 if during else 0.1, 1, 1], process_count=1,
                                 processes=[dict(own_lab=True)], idle_slot=True, resident_machine_gate=dict(ok=True),
                                 cpu=dict(interval_s=1, measured_pids=[-1], active=[])))
        return len(self.samples) - 1


def read(path):
    return json.loads(path.read_text())


def test_scores_both_legs_and_reports_all_fixed_looks(tmp_path, proposal):
    prepared = r8_bench_score.prepare(proposal)
    for leg_id in ('7', '8'):
        server = FakeServer(proposal, leg_id, tmp_path)
        report = r8_bench_score.score(server, FakeMonitor(server), prepared, tmp_path, leg_id)
        assert report['status'] == 'complete'
        assert len(server.watches) == 8
        assert [len(req['prompt']) for req in server.requests] == [32] * 7 + [26]
        assert all({k: v for k, v in req.items() if k != 'prompt'} == r8_bench_score.REQUEST for req in server.requests)
        assert list(report['rows']) == proposal['mmlu']['question_ids_in_order']
        assert all(row['correct'] for row in report['rows'].values())
        assert all(batch['quiet']['status'] == 'accepted' for batch in report['batches'])
        assert all(batch['quiet']['samples'][-1]['load_averages'][0] == 12 for batch in report['batches'])
        assert read(tmp_path / f'mmlu-{leg_id}.json') == report
        with pytest.raises(FileExistsError):
            r8_bench_score.score(server, FakeMonitor(server), prepared, tmp_path, leg_id)
        assert len(server.requests) == 8
    result = read(tmp_path / 'mmlu-paired.json')
    assert result['source']['question_ids_sha256'] == proposal['mmlu']['question_ids_sha256']
    assert result['complete'] and result['eligible_paired_prefix'] == 250
    assert [look['n'] for look in result['looks']] == [50, 100, 160, 250]
    assert result['decision'] == 'pass'
    assert result['decision_n'] == 160


def test_contaminated_batch_keeps_raw_scores_but_breaks_eligible_prefix(tmp_path, proposal):
    prepared = r8_bench_score.prepare(proposal)
    for leg_id in ('7', '8'):
        server = FakeServer(proposal, leg_id, tmp_path)
        monitor = FakeMonitor(server, contaminate=3 if leg_id == '8' else None)
        report = r8_bench_score.score(server, monitor, prepared, tmp_path, leg_id)
    assert len(server.requests) == 8 and len(report['rows']) == 250
    assert report['batches'][2]['quiet']['status'] == 'excluded'
    assert report['batches'][2]['quiet']['reasons'] == ['foreign helper process present']
    result = read(tmp_path / 'mmlu-paired.json')
    assert not result['complete'] and not result['decision']
    assert result['eligible_paired_prefix'] == 64
    assert [look['n'] for look in result['looks']] == [50]


@pytest.mark.parametrize('failure', ['gate', 'memory', 'missing evidence'])
def test_failed_batch_stays_on_disk_and_is_not_retried(tmp_path, proposal, failure):
    prepared = r8_bench_score.prepare(proposal)
    memory_error = capped_run.RunError('MEMORY_LOW', 'below the memory floor') if failure == 'memory' else None
    server = FakeServer(proposal, '7', tmp_path, request_error=memory_error)
    monitor = FakeMonitor(server, gate_failure=failure == 'gate', missing_evidence=failure == 'missing evidence')
    with pytest.raises(capped_run.RunError):
        r8_bench_score.score(server, monitor, prepared, tmp_path, '7')
    report = read(tmp_path / 'mmlu-7.json')
    assert report['status'] == 'failed' and len(report['batches']) == 1
    assert len(report['rows']) == (32 if failure == 'missing evidence' else 0)
    assert report['batches'][0]['quiet']['status'] == 'excluded'
    assert report['error']['code'] == ('MEMORY_LOW' if failure == 'memory' else 'LAB_NOT_QUIET')
    assert len(server.requests) == (0 if failure == 'gate' else 1)
    with pytest.raises(FileExistsError):
        r8_bench_score.score(server, monitor, prepared, tmp_path, '7')
    assert len(server.requests) == (0 if failure == 'gate' else 1)


@pytest.mark.parametrize('request_failure', ['HTTP error', 'duplicate indices'])
def test_recoverable_request_failure_keeps_remaining_batches_and_candidate(tmp_path, proposal, monkeypatch, request_failure):
    prepared = r8_bench_score.prepare(proposal)
    gates = []

    def machine(task, home, own_pids):
        gates.append((task['resources']['need_available_gib'], home, own_pids))
        return dict(ok=True)

    monkeypatch.setattr(capped_run, 'machine', machine)
    http_error = capped_run.RunError('REQUEST', 'HTTP 500') if request_failure == 'HTTP error' else None
    ref = FakeServer(proposal, '7', tmp_path, request_error=http_error, duplicate=request_failure == 'duplicate indices')
    report = r8_bench_score.score(ref, FakeMonitor(ref), prepared, tmp_path, '7')
    assert len(ref.requests) == 8 and len(report['rows']) == 218
    assert report['batches'][0]['quiet']['status'] == 'excluded'
    assert report['batches'][0]['post_failure_machine_gate'] == {'ok': True}
    assert gates == [(8, tmp_path, [-1])]
    cand = FakeServer(proposal, '8', tmp_path)
    report = r8_bench_score.score(cand, FakeMonitor(cand), prepared, tmp_path, '8')
    assert len(report['rows']) == 250 and len(cand.requests) == 8
    assert not read(tmp_path / 'mmlu-paired.json')['complete']


def test_rejects_extracted_data_changed_without_a_question_id_change(tmp_path, proposal):
    path = tmp_path / 'data' / 'test' / 'subject_test.csv'
    path.write_text(path.read_text().replace('Question 0?', 'Altered 0?'))
    with pytest.raises(ValueError, match='differs from the pinned archive'):
        r8_bench_score.prepare(proposal)
