"""Actual native Host inspection over synthetic raw logs; no jobs or GPU execution."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory import lab_evidence as evidence
from jiuwenswarm.factory.store import ScopeDenied, Store

ROOT = Path(__file__).resolve().parents[2]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture
def collected(tmp_path, monkeypatch, request):
    home = tmp_path / 'factory'
    parameter = getattr(request, 'param', 'succeeded')
    adapter = parameter.get('adapter', 'strata-benchmark-v3') if isinstance(parameter, dict) else 'strata-benchmark-v3'
    contract = dict(adapter=adapter, order=['A'])
    template = tmp_path / 'template.json'
    write(template, contract)
    digest = hashlib.sha256(template.read_bytes()).hexdigest()
    with Store(home) as store:
        store.create_task(dict(task_id='parent', objective='Inspect retained evidence', constraints={'factory_loop': {
            'templates': [dict(id='t', path=str(template), sha256=digest)]}}))
        store.create_task(dict(task_id='foreign', objective='Outside parent scope'))
        store.create_task(dict(task_id='child', objective='Owned measurement', contract_id=str(template),
                               constraints={'factory_loop_parent': 'parent'}))
        attempt = store.create_attempt('child', dict(kind='lab', idem_key='test', fingerprint='f',
            request=dict(adapter=contract['adapter'], contract=contract, contract_path=str(template), contract_sha256=digest)))
        aid = attempt['attempt_id']
        store.transition_attempt('child', aid, 'running')
        terminal = parameter.get('state', 'succeeded') if isinstance(parameter, dict) else parameter
        if terminal == 'cancelled':
            store.transition_attempt('child', aid, 'cancel_requested')
        store.transition_attempt('child', aid, terminal)
        cycle = dict(cycle_id='cycle', state='collected', child_task_id='child', attempt_id=aid,
            contract=contract, contract_sha256=digest, template_sha256=digest, request={'template_id': 't'})
        store._db.execute('CREATE TABLE factory_loop_cycles (task_id TEXT, cycle_id TEXT, record TEXT)')
        store._db.execute('INSERT INTO factory_loop_cycles VALUES (?,?,?)', ('parent', 'cycle', json.dumps(cycle)))
        store._db.commit()
        spool = home / 'benchmark-spool' / aid
        write(spool / 'config.json', dict(task_id='child', attempt_id=aid, contract=contract))
        write(spool / 'campaign.json', dict(task_id='child', attempt_id=aid, contract_sha256=digest,
            execution_outcome='ok' if terminal == 'succeeded' else 'measurement_failed',
            evidence_completeness='complete' if terminal == 'succeeded' else 'partial'))
        for phase in ('quality', 'speed'):
            folder = spool / 'cell-001-A' / phase
            folder.mkdir(parents=True)
            output = 'INFO expert_slots=100 cpu_experts=6\nREADY 8192 stop\nT 42\nDONE 1 1 10.0 5.0 length 0 0 0 0 0\n'
            (folder / 'stdout.log').write_text(output)
            (folder / 'stderr.log').write_text('safe retained native diagnostics\n')
            write(folder / 'report.json', dict(reason='completed' if terminal == 'succeeded' else 'command_failed', quiescent=True, container_removed=True,
                container_exit_code=0, cpus=8, container_oom_killed=False))
            events = [dict(stream='stdin', offset=0, retained_bytes=13, monotonic_ns=1_000_000_000),
                      dict(stream='stdout', offset=0, retained_bytes=len(output.encode()), monotonic_ns=2_000_000_000)]
            (folder / 'pipe-events.jsonl').write_text('\n'.join(map(json.dumps, events)) + '\n')
            samples = [dict(monotonic_ns=n * 1_000_000_000, available_bytes=1000 - n, cgroup_current=100*n,
                cpu_stat=dict(usage_usec=100*n, nr_throttled=0, throttled_usec=0),
                process_io=dict(read_bytes=10*n), io_stat=f'1:0 rbytes={20*n} wbytes=0\n') for n in (1, 2)]
            (folder / 'samples.jsonl').write_text('\n'.join(map(json.dumps, samples)) + '\n')
        files = {p.relative_to(spool).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in spool.rglob('*') if p.is_file()}
        write(spool / 'manifest.json', dict(state='complete' if terminal == 'succeeded' else 'partial', task_id='child', attempt_id=aid, files=files))
        store.put_artifact('child', aid + ':manifest.json', spool / 'manifest.json', 'application/json', aid)
        for name in files:
            if Path(name).name in evidence.ALLOWED_RAW:
                store.put_artifact('child', aid + ':' + name, spool / name, 'text/plain', aid)
    monkeypatch.setenv('FACTORY_HOME', str(home))
    monkeypatch.setenv('FACTORY_TASK_ID', 'parent')
    monkeypatch.setenv('PYTHONPATH', str(ROOT))
    monkeypatch.delenv('FACTORY_BRIDGE_DIR', raising=False)
    monkeypatch.delenv('FACTORY_PYTHON', raising=False)
    return home, spool, aid


def host_call(home, package='strata_throughput_workbench', cycle_id='cycle'):
    host = Host(home / 'ccstore', session_grants=['process.exec'], python=sys.executable)
    return host.call(host.prepare(ROOT / 'jiuwenswarm/factory/ccs' / package), 'inspect_evidence', {'cycle_id': cycle_id})


@pytest.mark.parametrize('package', ['strata_throughput_workbench', 'inference_lab'])
def test_actual_host_imports_parent_artifacts_and_rechecks(collected, package):
    home, spool, aid = collected
    result = host_call(home, package)
    assert result['state'] == 'succeeded', result
    report = result['outputs']['result']
    assert report['child_task_id'] == 'child' and len(report['artifacts']) == 10
    assert report['phases'][0]['engine_info'] == [{'expert_slots': 100, 'cpu_experts': 6}]
    assert report['phases'][0]['lifecycle_cgroup_io']['read_bytes'] == 20
    assert report['phases'][0]['memory']['kernel_cgroup_peak_bytes'] is None
    with Store(home) as store:
        scoped = store.scoped('parent')
        raw = report['artifacts'][0]
        assert scoped.read('parent', raw['artifact_id'])['sha256'] == raw['sha256']
        with pytest.raises(ScopeDenied):
            scoped.read('child', aid + ':manifest.json')
        again = evidence.inspect_evidence(scoped, 'parent', 'cycle')
        assert again == report
        assert len([o for o in store.dump('parent')['observations'] if o['kind'] == 'lab_evidence_inspection']) == 1


def test_actual_host_rejects_foreign_cycle_and_changed_raw(collected, monkeypatch):
    home, spool, aid = collected
    monkeypatch.setenv('FACTORY_TASK_ID', 'foreign')
    denied = host_call(home)
    assert denied['state'] == 'failed' and denied['reason'] == 'SCOPE_DENIED', denied
    monkeypatch.setenv('FACTORY_TASK_ID', 'parent')
    (spool / 'cell-001-A/quality/stdout.log').write_text('changed')
    bad = host_call(home)
    assert bad['state'] == 'failed' and bad['reason'] == 'INVALID_INPUT', bad
    with Store(home) as store:
        assert store.dump('parent')['artifacts'] == []


def test_rehashed_manifest_cannot_replace_collected_original(collected):
    home, spool, aid = collected
    manifest = json.loads((spool / 'manifest.json').read_text())
    manifest['extra'] = 'rewritten'
    write(spool / 'manifest.json', manifest)
    with Store(home) as store, pytest.raises(ValueError, match='collected child artifact'):
        evidence.inspect_evidence(store.scoped('parent'), 'parent', 'cycle')


def test_existing_parent_copy_mismatch_fails_without_overwrite(collected):
    home, spool, aid = collected
    name = 'cell-001-A/quality/stdout.log'
    artifact_id = 'lab-evidence:' + aid + ':' + hashlib.sha256(name.encode()).hexdigest()[:24]
    with Store(home) as store:
        store.put_artifact('parent', artifact_id, b'occupied', 'text/plain', None)
        with pytest.raises(ValueError, match='Existing parent artifact differs'):
            evidence.inspect_evidence(store.scoped('parent'), 'parent', 'cycle')
        assert store.artifact_bytes('parent', artifact_id) == b'occupied'


def test_finite_bridge_operation_uses_same_parent_checks(collected, monkeypatch, tmp_path):
    from jiuwenswarm.factory.bridge import handle
    home, spool, aid = collected
    monkeypatch.setenv('FACTORY_BRIDGE_HOME', str(home))
    result = handle(dict(operation='lab_evidence_inspect', task_id='parent', cycle_id='cycle'), tmp_path, tmp_path, tmp_path)
    assert json.loads(result['stdout'])['parent_task_id'] == 'parent'
    with pytest.raises(ScopeDenied):
        handle(dict(operation='lab_evidence_inspect', task_id='foreign', cycle_id='cycle'), tmp_path, tmp_path, tmp_path)


@pytest.mark.parametrize('collected', ['failed', 'cancelled'], indirect=True)
def test_partial_terminal_evidence_is_diagnostic_not_scoring(collected):
    home, spool, aid = collected
    result = host_call(home)
    assert result['state'] == 'succeeded', result
    report = result['outputs']['result']
    assert report['execution_complete'] is False and report['diagnostic_only'] is True
    assert report['evidence_status'] == 'partial_manifest_verified' and len(report['artifacts']) == 10
    assert all(p['native_rates'] is None for p in report['phases'])


def test_missing_raw_manifest_exposes_only_verified_collected_archives(collected):
    home, spool, aid = collected
    (spool / 'manifest.json').unlink()
    with Store(home) as store:
        report = evidence.inspect_evidence(store.scoped('parent'), 'parent', 'cycle')
    assert report['evidence_status'] == 'retained_archive_only'
    assert not report['execution_complete'] and not report['raw_source_verified']
    assert len(report['artifacts']) == 10


@pytest.mark.parametrize('collected', [{'adapter':'strata-benchmark-v4'},{'adapter':'strata-benchmark-v5'}], indirect=True)
def test_actual_host_fixed_adapter_import_remains_parent_ledger_scoped(collected,monkeypatch):
    home,spool,aid=collected
    result=host_call(home)
    assert result['state']=='succeeded',result
    report=result['outputs']['result']
    assert report['execution_complete'] and report['evidence_status']=='complete_verified'
    assert len(report['artifacts'])==10 and report['promotion_authorized'] is False
    monkeypatch.setenv('FACTORY_TASK_ID','foreign')
    denied=host_call(home)
    assert denied['state']=='failed' and denied['reason']=='SCOPE_DENIED'
    with Store(home) as store:
        assert store.dump('foreign')['artifacts']==[]
        with pytest.raises(ScopeDenied):store.scoped('parent').read('child',aid+':manifest.json')

@pytest.mark.parametrize('collected',[{'adapter':'strata-benchmark-v5'}],indirect=True)
@pytest.mark.parametrize('mutation',['request_adapter','foreign_parent','template_hash'])
def test_v5_cannot_use_labels_to_bypass_existing_ownership_checks(collected,mutation):
    home,spool,aid=collected
    with Store(home) as store:
        if mutation=='request_adapter':
            row=store._db.execute('SELECT request FROM attempts WHERE attempt_id=?',(aid,)).fetchone()
            request=json.loads(row['request']);request['adapter']='strata-benchmark-v4'
            store._db.execute('UPDATE attempts SET request=? WHERE attempt_id=?',(json.dumps(request),aid))
        if mutation=='foreign_parent':store._db.execute('UPDATE tasks SET constraints=? WHERE task_id=?',(json.dumps({'factory_loop_parent':'foreign'}),'child'))
        if mutation=='template_hash':
            row=store._db.execute('SELECT record FROM factory_loop_cycles WHERE task_id=?',('parent',)).fetchone()
            cycle=json.loads(row['record']);cycle['template_sha256']='b'*64
            store._db.execute('UPDATE factory_loop_cycles SET record=? WHERE task_id=?',(json.dumps(cycle),'parent'))
        store._db.commit()
    result=host_call(home)
    assert result['state']=='failed' and result['reason']=='SCOPE_DENIED',result
    with Store(home) as store:assert store.dump('parent')['artifacts']==[]
