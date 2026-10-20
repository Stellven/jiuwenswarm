import json
import tempfile
import unittest
from pathlib import Path
import httpx
import pytest
from jiuwenswarm.channels.cli import main as cli_entry
from jiuwenswarm.channels.cli import research
from jiuwenswarm.channels.cli.research import ResearchClient, completion_exit_code


class CliTests(unittest.TestCase):
    def test_lost_post_reconciles_single_status_once_and_never_resends(self):
        calls = []
        def transport(request):
            calls.append(request.method)
            if request.url.path.endswith('/readiness'):
                return httpx.Response(200, json={'client_contract_version': '1.0.0', 'ready': True, 'instance_id': 'one'})
            if request.method == 'POST':
                return httpx.Response(500, json={'category': 'internal'})
            self.assertEqual(request.url.params['client_request_id'], 'request:one')
            return httpx.Response(200, json={'run_id': 'run:one', 'client_request_id': 'request:one'})
        client = ResearchClient('http://private:5173', 'opaque', transport=httpx.MockTransport(transport))
        try:
            result = client.submit({'client_request_id': 'request:one'})
            self.assertEqual(result['run_id'], 'run:one')
            self.assertEqual(calls, ['GET', 'POST', 'GET'])
            with self.assertRaises(ValueError): client.request('GET', '/api/v1/../../foreign')
        finally: client.close()

    def test_scientific_fail_is_not_process_failure(self):
        self.assertEqual(completion_exit_code({'status': 'completed', 'scientific_verdict': 'FAIL'}), 0)
        for status in ['halted', 'partial', 'paused']:
            self.assertEqual(completion_exit_code({'status': status}), 1)
        self.assertEqual(completion_exit_code({'status': 'in_progress'}), 0)

    def test_auth_header_and_source_requests(self):
        received = []
        def transport(request):
            received.append(request)
            return httpx.Response(200, json={'schema_version': '1.0.0', 'client_contract_version': '1.0.0', 'ready': True, 'instance_id': 'expected'})
        client = ResearchClient('http://private:5173', 'opaque', transport=httpx.MockTransport(transport), expected_instance='expected')
        client.readiness()
        self.assertEqual(received[0].headers['authorization'], 'Bearer opaque')
        self.assertNotIn('opaque', str(received[0].url))
        with self.assertRaises(ValueError):
            client.request('GET', 'http://foreign.invalid/api/v1/runs')
        client.close()


@pytest.mark.parametrize('configuration', ['none', 'origin-option', 'origin-env', 'token-option', 'token-env'])
def test_native_doctor_identifies_missing_client_configuration(configuration, monkeypatch, capsys):
    origin = 'https://private-origin-sentinel.invalid'
    token_path = '/private/token-file-path-sentinel'
    for key in ('JIUWENSWARM_M1_ORIGIN', 'JIUWENSWARM_M1_TOKEN_FILE'):
        monkeypatch.delenv(key, raising=False)
    options = []
    if configuration == 'origin-option':
        options = ['--origin', origin]
    elif configuration == 'origin-env':
        monkeypatch.setenv('JIUWENSWARM_M1_ORIGIN', origin)
    elif configuration == 'token-option':
        options = ['--token-file', token_path]
    elif configuration == 'token-env':
        monkeypatch.setenv('JIUWENSWARM_M1_TOKEN_FILE', token_path)

    def forbidden(*args, **kwargs):
        raise AssertionError('Missing client configuration must refuse before token access or client creation')

    monkeypatch.setattr(research, 'ResearchClient', forbidden)
    monkeypatch.setattr('sys.argv', ['jiuwenswarm', 'research', *options, 'doctor'])
    with monkeypatch.context() as local:
        local.setattr(Path, 'stat', forbidden)
        with pytest.raises(SystemExit) as stopped:
            cli_entry.main()
    assert stopped.value.code == 3
    output = capsys.readouterr()
    assert output.out == ''
    error = json.loads(output.err)
    assert error['status'] == 'unavailable' and error['request_id'] is None
    for required in ('origin', 'token', '--origin', '--token-file', 'JIUWENSWARM_M1_ORIGIN', 'JIUWENSWARM_M1_TOKEN_FILE'):
        assert required in error['message']
    assert 'required' in error['message']
    assert origin not in output.err and token_path not in output.err


@pytest.mark.parametrize('failure', ['value', 'os', 'timeout', 'transport', 'http'])
def test_native_doctor_keeps_arbitrary_failure_details_private(failure, tmp_path, monkeypatch, capsys):
    secret = 'provider-and-token-secret-sentinel'
    token_path = tmp_path / 'protected-token'
    token_path.write_text(secret, encoding='ascii')
    token_path.chmod(0o600)
    request = httpx.Request('GET', 'https://private.invalid/api/v1/readiness')
    failures = {
        'value': ValueError(secret),
        'os': OSError(secret),
        'timeout': TimeoutError(secret),
        'transport': httpx.ConnectError(secret, request=request),
        'http': httpx.HTTPStatusError(secret, request=request, response=httpx.Response(401, request=request)),
    }

    def unavailable(*args, **kwargs):
        raise failures[failure]

    monkeypatch.setattr(research, 'ResearchClient', unavailable)
    monkeypatch.setattr('sys.argv', ['jiuwenswarm', 'research', '--origin', 'https://private.invalid', '--token-file', str(token_path), 'doctor'])
    with pytest.raises(SystemExit) as stopped:
        cli_entry.main()
    assert stopped.value.code == 3
    output = capsys.readouterr()
    assert output.out == '' and secret not in output.err and str(token_path) not in output.err
    assert json.loads(output.err) == {
        'status': 'unavailable', 'request_id': None,
        'message': 'Research operation failed; inspect request, scope and readiness.',
    }


@pytest.mark.parametrize('configuration', ['options', 'environment', 'mixed'])
def test_native_doctor_uses_configured_authenticated_client(configuration, tmp_path, monkeypatch, capsys):
    origin, token = 'https://private.invalid', 'disposable-auth-sentinel'
    token_path = tmp_path / 'protected-token'
    token_path.write_text(token, encoding='ascii')
    token_path.chmod(0o600)
    for key in ('JIUWENSWARM_M1_ORIGIN', 'JIUWENSWARM_M1_TOKEN_FILE'):
        monkeypatch.delenv(key, raising=False)
    options = []
    if configuration in {'options', 'mixed'}:
        options.extend(['--origin', origin])
    else:
        monkeypatch.setenv('JIUWENSWARM_M1_ORIGIN', origin)
    if configuration == 'options':
        options.extend(['--token-file', str(token_path)])
    else:
        monkeypatch.setenv('JIUWENSWARM_M1_TOKEN_FILE', str(token_path))
    calls = []
    ready = {'client_contract_version': '1.0.0', 'ready': True, 'instance_id': 'controlled'}

    def respond(request):
        calls.append(request)
        assert request.method == 'GET' and str(request.url) == origin + '/api/v1/readiness'
        assert request.headers['authorization'] == 'Bearer ' + token
        return httpx.Response(200, json=ready)

    def controlled_client(*args, **kwargs):
        return ResearchClient(*args, **kwargs, transport=httpx.MockTransport(respond))

    monkeypatch.setattr(research, 'ResearchClient', controlled_client)
    monkeypatch.setattr('sys.argv', ['jiuwenswarm', 'research', *options, 'doctor'])
    with pytest.raises(SystemExit) as stopped:
        cli_entry.main()
    assert stopped.value.code == 0 and len(calls) == 1
    output = capsys.readouterr()
    assert json.loads(output.out) == ready
    assert token not in output.out + output.err and str(token_path) not in output.out + output.err
