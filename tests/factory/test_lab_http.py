"""The lab mailbox over HTTP, shipped payloads (engine images and artifacts) and lab routing."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import threading

import pytest

from jiuwenswarm.factory import lab_http, lab_payload
from jiuwenswarm.factory.lab_agent import CommandAdapter, LabAgent, serve
from jiuwenswarm.factory.lab_http import MailboxServer, RemoteError, RemoteMailbox
from jiuwenswarm.factory.lab_mailbox import Mailbox, MailboxError, open_mailbox
from jiuwenswarm.factory.lab_manager import LabManager

from test_lab_manager import build, good_report, lab_task

FACTORY, LAB = 'factory-token-0123', 'lab-token-4567'


@pytest.fixture
def server(tmp_path):
    root = tmp_path / 'served'
    httpd = MailboxServer(('127.0.0.1', 0), Mailbox(root), dict(factory=FACTORY, lab=LAB))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{httpd.server_port}', root
    httpd.shutdown()
    httpd.server_close()


def remote(url, token, tmp_path, name):
    return RemoteMailbox(url, token, cache=tmp_path / f'cache-{name}', retries=2)


def fake_image_archive(path, config=b'{"architecture":"arm64","os":"linux"}'):
    """A minimal docker save archive: manifest.json naming one config blob."""
    digest = hashlib.sha256(config).hexdigest()
    with tarfile.open(path, 'w') as archive:
        for name, data in ((f'blobs/sha256/{digest}', config),
                           ('manifest.json', json.dumps([dict(Config=f'blobs/sha256/{digest}', RepoTags=['engine:x'], Layers=[])]).encode())):
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return 'sha256:' + digest


@pytest.fixture
def task(store):
    store.create_task(dict(task_id='lt', objective='measure the cache build', contract_id='star-deepseek-v2'))
    stock, candidate = build(store, 'lt', 'a' * 64), build(store, 'lt', 'e' * 64)
    engine = store.put_artifact('lt', 'engine-build.tar', b'llama-server build tree' * 1000, 'application/x-tar', None)
    subjects = dict(stock=dict(kind='native_build', identity=dict(executable_sha256='a' * 64), build_attempt_id=stock),
                    cache=dict(kind='native_build', identity=dict(executable_sha256='e' * 64, artifact_id='engine-build.tar'),
                               build_attempt_id=candidate, transfer='attach'))
    return store, subjects, engine


def test_engine_and_lab_task_cross_http_and_the_report_comes_back(server, task, tmp_path):
    url, root = server
    store, subjects, engine = task
    manager = LabManager(store, remote(url, FACTORY, tmp_path, 'factory'))
    assert manager.route == 'mailbox'
    composed = manager.compose('lt', lab_task(subjects))
    assert composed['payloads']['cache']['sha256'] == engine['sha256']
    request = manager.send('lt', composed['package_id'], 'over-http')['request_id']
    assert (root / 'requests' / request / 'files' / engine['sha256']).is_file()

    agent = LabAgent(remote(url, LAB, tmp_path, 'lab'), 'spark-lab', 'operator', 'spark-gb10')
    assert [row['request_id'] for row in agent.inbox()] == [request]
    fetched = agent.fetch(request)
    assert Path(fetched['cache']['path']).read_bytes() == store.artifact_bytes('lt', 'engine-build.tar')
    agent.accept(request, 'on the Spark')
    question = manager.ask('lt', request, 'Send the raw samples.', dict(files=['samples']))['question']
    samples = tmp_path / 'samples.json'
    samples.write_text('[50, 49, 23, 24]')
    agent.report(request, good_report(), {'samples': samples})
    assert agent.auto_answer(request) == [question]

    recorded = manager.report('lt', request)
    assert recorded['valid'], recorded['problems']
    assert store.artifact_bytes('lt', recorded['report']['files'][0]['artifact_id']) == samples.read_bytes()
    assert manager.reply('lt', request, question)['state'] == 'answered'


def test_tokens_separate_the_factory_from_the_lab(server, task, tmp_path, monkeypatch):
    url, _ = server
    store, subjects, _ = task
    manager = LabManager(store, remote(url, FACTORY, tmp_path, 'factory'))
    request = manager.send('lt', manager.compose('lt', lab_task(subjects))['package_id'], 'k')['request_id']
    lab = remote(url, LAB, tmp_path, 'lab')
    with pytest.raises(RemoteError, match='403'):
        lab.open_request('labreq-' + 'f' * 24, {'schema': 'x'})
    with pytest.raises(RemoteError, match='403'):
        lab.post(request, 'factory', 'cancel', {})
    with pytest.raises(RemoteError, match='409'):
        remote(url, FACTORY, tmp_path, 'f2').post(request, 'factory', 'request', {})
    with pytest.raises(RemoteError, match='401'):
        remote(url, 'wrong', tmp_path, 'x').requests()


def test_an_http_mailbox_needs_a_token(monkeypatch):
    monkeypatch.delenv('FACTORY_LAB_TOKEN', raising=False)
    monkeypatch.delenv('FACTORY_LAB_TOKEN_FILE', raising=False)
    with pytest.raises(ValueError, match='token'):
        RemoteMailbox('http://127.0.0.1:9')


def test_uploads_resume_and_downloads_are_checked(server, tmp_path, monkeypatch):
    url, root = server
    factory = remote(url, FACTORY, tmp_path, 'factory')
    request = 'labreq-' + 'a' * 24
    factory.open_request(request, {'schema': 'factory.lab-package/1'})
    big = tmp_path / 'engine.tar'
    big.write_bytes(bytes(range(256)) * 4096 * 3)  # 3 MiB
    monkeypatch.setattr(lab_http, 'CHUNK', 1 << 20)
    sha = hashlib.sha256(big.read_bytes()).hexdigest()
    # A first upload that stops after one chunk, as a broken link would leave it.
    local = Mailbox(root)
    with big.open('rb') as stream:
        local.receive(request, sha, big.stat().st_size, 0, stream, 1 << 20)
    assert factory._head(request, sha) == (None, 1 << 20)
    seen = []
    reference = factory.attach(request, big, 'engine.tar', progress=lambda name, done, total: seen.append(done))
    assert seen[0] == 2 << 20 and seen[-1] == 3 << 20 and reference['sha256'] == sha
    assert factory.file_size(request, sha) == big.stat().st_size

    lab = remote(url, LAB, tmp_path, 'lab')
    assert lab.file_path(request, reference).read_bytes() == big.read_bytes()
    # A wrong digest is refused on upload, and a changed file is refused on download.
    with pytest.raises(MailboxError):
        local.receive(request, 'b' * 64, 3, 0, io.BytesIO(b'abc'), 3)
    stored = root / 'requests' / request / 'files' / sha
    stored.write_bytes(b'x' + stored.read_bytes()[1:])
    cached = tmp_path / 'cache-lab2'
    with pytest.raises(MailboxError, match='differs from its digest'):
        RemoteMailbox(url, LAB, cache=cached, retries=1).file_path(request, reference)


def test_a_message_cannot_name_a_file_that_was_not_uploaded(tmp_path):
    mailbox = Mailbox(tmp_path / 'm')
    request = 'labreq-' + 'c' * 24
    mailbox.open_request(request, {'schema': 'x'})
    with pytest.raises(MailboxError, match='not uploaded'):
        mailbox.post(request, 'factory', 'request', {}, [dict(name='engine.tar', sha256='d' * 64, size=10)])


def test_open_mailbox_picks_directory_or_http(tmp_path, monkeypatch):
    monkeypatch.setenv('FACTORY_LAB_TOKEN', LAB)
    assert isinstance(open_mailbox('http://127.0.0.1:9'), RemoteMailbox)
    assert isinstance(open_mailbox(tmp_path / 'm'), Mailbox)


def test_containerd_archive_answers_to_its_index_digest(tmp_path):
    config, manifest = b'{"os":"linux"}', None
    archive = tmp_path / 'oci.tar'
    config_digest = hashlib.sha256(config).hexdigest()
    manifest = json.dumps(dict(schemaVersion=2, config=dict(digest='sha256:' + config_digest))).encode()
    manifest_digest = hashlib.sha256(manifest).hexdigest()
    index = json.dumps(dict(schemaVersion=2, manifests=[dict(digest='sha256:' + manifest_digest, size=len(manifest))])).encode()
    with tarfile.open(archive, 'w') as tar:
        for name, data in ((f'blobs/sha256/{config_digest}', config), (f'blobs/sha256/{manifest_digest}', manifest),
                           ('index.json', index),
                           ('manifest.json', json.dumps([dict(Config=f'blobs/sha256/{config_digest}', Layers=[])]).encode())):
            member = tarfile.TarInfo(name)
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
    assert lab_payload.archive_image_ids(archive) == ['sha256:' + manifest_digest, 'sha256:' + config_digest]


def test_image_archive_is_checked_before_use(store, tmp_path, monkeypatch):
    archive = tmp_path / 'engine.tar'
    image_id = fake_image_archive(archive)
    assert lab_payload.archive_image_id(archive) == image_id

    def fake_docker(argv, timeout):
        if argv[1] == 'save':
            fake_image_archive(Path(argv[3]))
        return type('Done', (), dict(returncode=0, stdout=image_id, stderr=''))()

    monkeypatch.setattr(lab_payload, '_docker', fake_docker)
    monkeypatch.setenv('FACTORY_LAB_MAILBOX', str(tmp_path / 'mailbox'))
    store.create_task(dict(task_id='lt', objective='o', contract_id='star-deepseek-v2'))
    subjects = dict(stock=dict(kind='container_image', identity=dict(tag='engine:x', id=image_id), transfer='attach'),
                    cache=dict(kind='container_image', identity=dict(tag='engine:y', id='sha256:' + '0' * 64)))
    manager = LabManager(store, route='mailbox')
    composed = manager.compose('lt', lab_task(subjects))
    assert composed['payloads']['stock']['format'] == 'docker-archive'
    request = manager.send('lt', composed['package_id'], 'img')['request_id']
    agent = LabAgent(manager.mailbox, 'lab', 'operator')
    fetched = agent.fetch(request, load=True)
    assert fetched['stock']['image_id'] == image_id and fetched['stock']['loaded'] == image_id

    bad = dict(subjects, stock=dict(subjects['stock'], identity=dict(tag='engine:x', id='sha256:' + '1' * 64)))
    with pytest.raises(ValueError, match='not the subject image'):
        manager.compose('lt', lab_task(bad))


def test_command_lab_agent_gets_the_shipped_engine(task, tmp_path, monkeypatch):
    store, subjects, engine = task
    monkeypatch.setenv('FACTORY_LAB_MAILBOX', str(tmp_path / 'mailbox'))
    manager = LabManager(store, route='mailbox')
    request = manager.send('lt', manager.compose('lt', lab_task(subjects))['package_id'], 'cmd')['request_id']
    script = tmp_path / 'lab.py'
    script.write_text('''import json, os, sys, hashlib
from pathlib import Path
payloads = json.loads(Path(sys.argv[3]).read_text())
engine = Path(payloads["cache"]["path"]).read_bytes()
out = Path(sys.argv[2])
(out / "files" / "samples").write_text(hashlib.sha256(engine).hexdigest())
report = dict(outcome="completed", summary="ran on the shipped build",
  results=[dict(test_id="ttft", arm=a, request="p512", metric="client_ttft_ms", unit="ms", samples=[1.0]) for a in ("A", "C3")],
  checks=[dict(test_id="parity", check="gate_unset_parity", arm="C3", verdict="pass")], limits=["test"])
(out / "report.json").write_text(json.dumps(report))
''')
    import sys
    agent = LabAgent(manager.mailbox, 'cmd-lab', 'command')
    adapter = CommandAdapter(f'{sys.executable} {script} {{package}} {{output}} {{payloads}}', tmp_path / 'work')
    serve(agent, adapter, once=True, log=lambda line: None)
    serve(agent, adapter, once=True, log=lambda line: None)
    recorded = manager.report('lt', request)
    assert recorded['valid'], recorded['problems']
    sent = store.artifact_bytes('lt', recorded['report']['files'][0]['artifact_id']).decode()
    assert sent == engine['sha256']


def test_queue_route_leaves_what_it_cannot_run_for_a_lab_agent(task, tmp_path, monkeypatch):
    store, subjects, _ = task
    monkeypatch.setenv('FACTORY_LAB_MAILBOX', str(tmp_path / 'mailbox'))
    manager = LabManager(store)
    assert manager.route == 'queue'
    sent = manager.send('lt', manager.compose('lt', lab_task(subjects))['package_id'], 'q')
    assert sent['state'] == 'requested' and sent['route'].startswith('left for a lab agent: ')
    with pytest.raises(ValueError):
        LabManager(store, route='elsewhere')


def test_cli_passes_lab_server_options_through(monkeypatch):
    from jiuwenswarm.factory import cli
    seen = {}
    monkeypatch.setattr(lab_http, 'main', lambda argv: seen.setdefault('argv', argv) and 0)
    with pytest.raises(SystemExit):
        cli.main(['lab-server', '--host', '127.0.0.1', '--port', '0'])
    assert seen['argv'] == ['--host', '127.0.0.1', '--port', '0']
