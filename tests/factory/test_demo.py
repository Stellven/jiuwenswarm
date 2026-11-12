"""Disposable fixture plumbing, never live-agent or engine evidence."""
import hashlib
import json
from io import BytesIO

from jiuwenswarm.factory.demo import build, make_handler, DemoState, ROOT
from jiuwenswarm.factory.store import Store


def test_build_and_control_api(tmp_path):
    home, out = tmp_path / 'store', tmp_path / 'pack'
    contract = json.loads((ROOT / 'jiuwenswarm/factory/contracts/qwen36-bare-greedy-v1.json').read_text())
    stdout = b'explicit synthetic fixture stdout\n'
    fixture_root = tmp_path / 'root'
    fixture_contract = fixture_root / 'jiuwenswarm/factory/contracts/qwen36-bare-greedy-v1.json'
    fixture_contract.parent.mkdir(parents=True)
    contract['reference']['stdout_sha256'] = hashlib.sha256(stdout).hexdigest()
    fixture_contract.write_text(json.dumps(contract))
    with Store(home) as store:
        for task in ('fixture-run4', 'fixture-run5'):
            store.create_task(dict(task_id=task, objective='Synthetic presentation fixture'))
        store.put_artifact('fixture-run4', 'stdout', stdout, 'text/plain', None)
        for rev in range(1, 14):
            patch = {'add': [dict(node_id='inspect', kind='inspect', title='Fixture inspection')]} if rev == 1 else {
                'update': [dict(node_id='inspect', reason=f'Fixture revision {rev}')]}
            store.advance_decision('fixture-run5', rev-1, dict(action={'type': 'inspect'},
                                   plan_patch=patch, expected_graph_rev=rev-1))
    before = {p.name: p.stat().st_mtime_ns for p in home.iterdir() if p.is_file()}
    pack = build(out, home, root=fixture_root, siminfeng=tmp_path/'lab',
                 run4='fixture-run4', run5='fixture-run5')
    assert (out/'index.html').is_file()
    assert sum(s['duration'] for s in pack['sections']) == 600
    assert stdout.decode() in pack['sections'][2]['text']
    assert json.loads((out/'assets/run5-plan-12.json').read_text())['rev'] == 12
    assert json.loads((out/'assets/run5-plan-13.json').read_text())['rev'] == 13
    assert pack['gaps']  # Fixture deliberately has no lab run, slides or integration builds.
    assert before == {p.name: p.stat().st_mtime_ns for p in home.iterdir() if p.is_file()}
    # Exercise the actual HTTP handler without opening a listening socket. This
    # also runs where the worker sandbox disallows socket creation.
    now = [0.0]
    state = DemoState(pack, clock=lambda: now[0])
    handler = make_handler(out, state)
    class Connection:
        def __init__(self, request):
            self.request, self.response = BytesIO(request), bytearray()
        def makefile(self, *args):
            return self.request
        def sendall(self, data):
            self.response.extend(data)
    def request(path, value=None):
        body = json.dumps(value).encode() if value is not None else b''
        method = 'POST' if value is not None else 'GET'
        wire = (f'{method} {path} HTTP/1.0\r\nHost: 127.0.0.1\r\n'
                f'Content-Length: {len(body)}\r\nContent-Type: application/json\r\n\r\n').encode()+body
        connection = Connection(wire)
        handler(connection, ('127.0.0.1', 1234), None)
        header, response = bytes(connection.response).split(b'\r\n\r\n', 1)
        return header, json.loads(response)
    def post(action, section=None):
        header, value = request('/api/control', dict(action=action, section=section))
        assert b'200 OK' in header
        return value
    assert post('pause')['paused']
    assert post('next')['section'] == 2
    assert post('prev')['section'] == 1
    assert post('goto', 6)['section'] == 6
    assert not post('resume')['paused']
    now[0] += 140
    assert request('/api/state')[1]['section'] == 8
    assert request('/api/state')[1]['elapsed'] == 140
    # Force the real read-only subprocess to fail, then exercise captured fallback.
    state.pack['home'] = str(tmp_path/'missing-store')
    assert post('live')['label'] == 'RECORDED FALLBACK'
    assert request('/assets/run5-plan-13.json')[1]['rev'] == 13
    assert b'400' in request('/api/control', dict(action='goto', section=99))[0]
