"""Explicit synthetic public UI fixtures; never operational admission/model calls."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import json
import io
import stat
import struct
import sys
import types

import pytest

MODULE = Path(__file__).parents[3] / 'jiuwenswarm/server/rsi/cc_rsi_projection.py'
spec = importlib.util.spec_from_file_location('unit_cc_projection', MODULE)
projection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(projection)


def unit_publication():
    body = '# Synthetic UI test fixture\nreturn 1\n'
    digest = hashlib.sha256(body.encode()).hexdigest()
    gate = {'allowed': True, 'blocker': None}
    return {'snapshot': {'schema_version': '1', 'revision': 'synthetic-ui-test', 'generated_at': None,
        'availability': 'TEST_ONLY', 'blocker': None,
        'targets': [{'id': 'unit-target', 'name': 'Synthetic UI target', 'parent_hash': digest, 'active_hash': None, 'run': gate}],
        'runs': [], 'nodes': [{'id': 'unit-parent', 'target_id': 'unit-target', 'run_id': None, 'parent_id': None,
            'hash': digest, 'label': 'Synthetic parent', 'evaluation_status': 'failed', 'admission_status': 'unadmitted',
            'activation_status': 'inactive', 'correctness': None, 'speed': None, 'noise': None,
            'evidence_refs': [], 'operator_receipts': [], 'admit': gate, 'activate': gate}]},
        'candidates': [{'node_id': 'unit-parent', 'candidate_hash': digest, 'path': 'unit.py', 'parent_code': body,
                        'candidate_code': body, 'rationale': None, 'blocker': None}]}


def test_exact_captured_unadmitted_code_remains_reviewable():
    value = projection.validate_publication(unit_publication())
    service = projection.CcRsiProjection()
    service._read = lambda: copy.deepcopy(value)
    node = value['snapshot']['nodes'][0]
    assert service.candidate({'node_id': node['id'], 'candidate_hash': node['hash']})['candidate_code'].startswith('# Synthetic')
    assert service.snapshot({})['nodes'][0]['admission_status'] == 'unadmitted'


@pytest.mark.parametrize('location,field', [('root', 'model_packet'), ('snapshot', 'fixture_labels'), ('node', 'private_ref')])
def test_private_or_unknown_fields_are_rejected(location, field):
    value = unit_publication()
    target = value if location == 'root' else value['snapshot'] if location == 'snapshot' else value['snapshot']['nodes'][0]
    target[field] = 'must not be forwarded'
    with pytest.raises(projection.ProjectionError): projection.validate_publication(value)


def test_changed_captured_bytes_or_identity_fail_closed():
    value = unit_publication()
    value['candidates'][0]['candidate_code'] += '# changed'
    with pytest.raises(projection.ProjectionError): projection.validate_publication(value)
    service = projection.CcRsiProjection(); service._read = unit_publication
    with pytest.raises(projection.ProjectionError): service.candidate({'node_id': 'unit-parent', 'candidate_hash': 'a' * 64})


def test_publication_cannot_grant_root_or_run_authority():
    service = projection.CcRsiProjection(); service._read = unit_publication
    view = service.snapshot({})
    assert view['targets'][0]['run']['allowed'] is False
    assert view['nodes'][0]['admit']['allowed'] is False
    assert view['nodes'][0]['activate']['allowed'] is False
    with pytest.raises(projection.ProjectionError): service.operator_action({'action': 'admit', 'actor': 'root'})
    with pytest.raises(projection.ProjectionError): service.run_start({'target_id': 'unit-target'})


def test_missing_publication_is_explicitly_blocked_without_synthetic_records():
    view = projection.CcRsiProjection().snapshot({})
    assert view['availability'] == 'BLOCKED'
    assert view['nodes'] == view['runs'] == view['targets'] == []


def test_lineage_cycles_rejected():
    value = unit_publication()
    value['snapshot']['nodes'][0]['parent_id'] = 'unit-parent'
    with pytest.raises(projection.ProjectionError): projection.validate_publication(value)


def test_nonfinite_budget_never_becomes_a_measured_zero():
    value = unit_publication()
    value['snapshot']['runs'] = [{'id': 'unit-run', 'target_id': 'unit-target', 'stage': 'unit', 'status': 'TEST_ONLY',
        'blockers': [], 'activity': [], 'budget': {'elapsed_seconds': float('nan'), 'limit_seconds': None,
        'setup_calls': None, 'diagnosis_calls': None, 'proposal_calls': None, 'generation_call_limit': None, 'cost': None, 'currency': None}}]
    with pytest.raises(projection.ProjectionError): projection.validate_publication(value)


def scoped_publication():
    value = unit_publication(); value['workspace_id'] = 'unit-workspace'
    value['snapshot']['nodes'][0]['security_status'] = 'NOT_APPLICABLE'
    return value


def test_exact_workspace_and_deferred_security_preserve_real_visible_metrics():
    value = scoped_publication()
    child = copy.deepcopy(value['snapshot']['nodes'][0])
    child.update(id='unit-child', parent_id='unit-parent', security_status='SECURITY_DEFERRED',
                 evaluation_status='passed', correctness='12/12 visible checks',
                 admit={'allowed': False, 'blocker': 'Security deferred'},
                 activate={'allowed': False, 'blocker': 'Security deferred'})
    value['snapshot']['nodes'].append(child)
    assert projection.validate_publication(value, workspace_id='unit-workspace')['snapshot']['nodes'][1]['correctness'] == '12/12 visible checks'
    with pytest.raises(projection.ProjectionError): projection.validate_publication(value, workspace_id='foreign')
    with pytest.raises(projection.ProjectionError): projection.validate_publication(unit_publication(), workspace_id='unit-workspace')
    for key, claim in [('admission_status', 'admitted'), ('activation_status', 'active'),
                       ('operator_receipts', [{'action': 'admit'}]), ('security_status', 'NOT_APPLICABLE')]:
        changed = copy.deepcopy(value); changed['snapshot']['nodes'][1][key] = claim
        with pytest.raises(projection.ProjectionError): projection.validate_publication(changed, workspace_id='unit-workspace')


def test_explicit_most_specific_readonly_mount_required():
    text = '1 0 0:1 / / rw - overlay overlay rw\n2 1 0:2 / /run/public ro - tmpfs tmpfs rw\n'
    path = '/run/public/publication.json'
    assert projection._readonly_mount(path, text)
    assert not projection._readonly_mount(path, text.replace('/run/public ro', '/run/public rw'))
    assert not projection._readonly_mount(path, text + '3 2 0:3 / /run/public/publication.json rw - tmpfs tmpfs rw\n')
    assert not projection._readonly_mount(path, text + text.splitlines()[1] + '\n')
    assert not projection._readonly_mount(path, '1 0 0:1 / / ro - overlay overlay ro\n')


@pytest.mark.parametrize('mode,owner', [(stat.S_IFLNK | 0o777, 0), (stat.S_IFDIR | 0o777, 0), (stat.S_IFDIR | 0o755, 10001)])
def test_root_nonsymlink_nonwritable_publication_ancestry_required(mode, owner):
    parent = types.SimpleNamespace(lstat=lambda: types.SimpleNamespace(st_mode=mode, st_uid=owner))
    with pytest.raises(projection.ProjectionError):
        projection._root_ancestors(types.SimpleNamespace(parents=[parent]))


@pytest.mark.parametrize('fault', [None, 'workspace', 'mount', 'owner', 'hardlink'])
def test_reader_enforces_actual_workspace_mount_and_leaf_custody(monkeypatch, fault):
    raw = json.dumps(scoped_publication()).encode()
    mountinfo = '1 0 0:1 / / rw - overlay overlay rw\n2 1 0:2 / /run/public ro - tmpfs tmpfs rw\n'
    parent = types.SimpleNamespace(lstat=lambda: types.SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0))
    path = type('SyntheticPath', (), {'__str__': lambda self: '/run/public/publication.json',
                                     'is_absolute': lambda self: True})()
    path.parts = ('/', 'run', 'public', 'publication.json'); path.parents = [parent]
    def paths(name):
        if str(name) == '/proc/self/mountinfo':
            return types.SimpleNamespace(read_text=lambda **kw: mountinfo.replace('/run/public ro', '/run/public rw') if fault == 'mount' else mountinfo)
        return path
    fake_os = types.SimpleNamespace(name='posix', O_RDONLY=0, O_NOFOLLOW=1, O_NONBLOCK=2,
        open=lambda *args: 99, close=lambda fd: None, fdopen=lambda *args, **kw: io.BytesIO(raw),
        fstat=lambda fd: types.SimpleNamespace(st_mode=stat.S_IFREG | 0o440, st_uid=10001 if fault == 'owner' else 0,
                                              st_nlink=2 if fault == 'hardlink' else 1, st_size=len(raw)))
    monkeypatch.setattr(projection, 'Path', paths); monkeypatch.setattr(projection, 'os', fake_os)
    service = projection.CcRsiProjection('/run/public/publication.json', workspace_id='foreign' if fault == 'workspace' else 'unit-workspace')
    assert service.snapshot({})['availability'] == ('TEST_ONLY' if fault is None else 'BLOCKED')


def broker_module():
    package = types.ModuleType('unit_cc_rsi'); package.__path__ = []
    sys.modules['unit_cc_rsi'] = package
    sys.modules['unit_cc_rsi.cc_rsi_projection'] = projection
    spec = importlib.util.spec_from_file_location('unit_cc_rsi.cc_rsi_broker', MODULE.with_name('cc_rsi_broker.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('fault', ['none', 'browser-actor', 'wrong-receipt', 'wrong-peer'])
def test_broker_contract_uses_verified_human_and_exact_receipt_only(monkeypatch, fault):
    broker = broker_module()
    digest = 'a' * 64
    authorization = broker.HumanActionAuthorization('unit:human', 'unit-action', 'synthetic-signed-proof')
    if fault == 'browser-actor':
        with pytest.raises(projection.ProjectionError):
            broker.InstalledHumanOperatorClient().execute('admit', 'unit-node', digest, {'actor': 'root'})
        return
    monkeypatch.setattr(broker.os, 'name', 'posix')
    monkeypatch.setattr(broker.socket, 'SO_PEERCRED', 17, raising=False)
    monkeypatch.setattr(broker.socket, 'AF_UNIX', 1, raising=False)
    monkeypatch.setattr(broker.os, 'lstat', lambda path: types.SimpleNamespace(st_uid=0,
        st_mode=(stat.S_IFSOCK | 0o660) if path.endswith('.sock') else (stat.S_IFDIR | 0o755)))
    sent = []
    class SyntheticSocket:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def settimeout(self, value): assert value == 10
        def connect(self, endpoint): assert endpoint == '/run/ai4r-rsi-ui/operator.sock'
        def getsockopt(self, *args): return struct.pack('3i', 1, 10001 if fault == 'wrong-peer' else 0, 13000)
        def sendall(self, raw): sent.append(json.loads(raw))
        def recv(self, limit):
            return json.dumps({'action': 'admit', 'node_id': 'unit-node', 'candidate_hash': digest,
                'actor': 'unit:other' if fault == 'wrong-receipt' else 'unit:human',
                'receipt_ref': {'id': 'synthetic-receipt', 'sha256': digest}}).encode() + b'\n'
    monkeypatch.setattr(broker.socket, 'socket', lambda *args: SyntheticSocket())
    if fault != 'none':
        with pytest.raises(projection.ProjectionError): broker.InstalledHumanOperatorClient().execute('admit', 'unit-node', digest, authorization)
    else:
        assert broker.InstalledHumanOperatorClient().execute('admit', 'unit-node', digest, authorization)['actor'] == 'unit:human'
        assert set(sent[0]) == {'protocol', 'action', 'node_id', 'candidate_hash', 'authorization'}
