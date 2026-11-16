"""API/stream contract tests with isolated executable stages, not product traces."""
import io
import json
import zipfile
from pathlib import Path
import sys
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jiuwenswarm.software_factory.api import create_router
from jiuwenswarm.software_factory.contracts import Stage
from jiuwenswarm.software_factory.engine import FactoryService


def action(ctx, inputs):
    ctx.run_command([sys.executable, '-c', 'print("actual child output", flush=True)'])
    return {'data': ctx.write_json('output.json', {'value': 3})}


DIFF_SOURCE = '__global__ void project(float* out) { out[0] = 1; }\n// <script>not executable UI content</script>\n'
GENERATED_SOURCE = '#include <cstddef>\nvoid project(float* out) { out[0] = 1; }\n'


def generated_artifacts(ctx, inputs):
    # Isolated transport test data; production publishes its actual generated files.
    cpp = ctx.workspace / 'strata_core.cpp'
    cpp.write_text(GENERATED_SOURCE)
    diff = ctx.write_json('code-diff.json', {
        'schema': 'strata.code.diff.v1',
        'files': [{'source_path': 'src/kernels/expert.cu', 'generated_path': 'src/strata_core.cpp',
                   'source_code': DIFF_SOURCE, 'generated_code': GENERATED_SOURCE, 'language': 'cpp'}],
    })
    archive = ctx.workspace / 'huawei_native_strata.zip'
    with zipfile.ZipFile(archive, 'w') as stream:
        stream.write(cpp, 'src/strata_core.cpp')
        stream.writestr('CMakeLists.txt', 'cmake_minimum_required(VERSION 3.24)\n')
    return {'diff': diff, 'source': cpp, 'package': archive}


class APITests(unittest.TestCase):
    def test_owner_isolation_and_stream_replays_real_command_events(self):
        with tempfile.TemporaryDirectory() as directory:
            service = FactoryService(Path(directory), [Stage('actual', 'Actual process', 'test', 'stage', {}, {'data': 'test.data'}, action)])
            app = FastAPI()
            app.include_router(create_router(service, lambda request, scope: request.headers.get('x-user', 'operator')))
            client = TestClient(app)
            response = client.post('/api/v1/factory/runs', json={'goals': ['test.data']}, headers={'x-user': 'alice'})
            self.assertEqual(response.status_code, 202)
            run_id = response.json()['id']
            with client.stream('GET', f'/api/v1/factory/runs/{run_id}/stream', headers={'x-user': 'alice'}) as response:
                frames = ''.join(response.iter_text())
            self.assertIn('event: snapshot', frames)
            self.assertIn('command.output', frames)
            self.assertIn('actual child output', frames)
            self.assertIn('run.completed', frames)
            self.assertEqual(client.get(f'/api/v1/factory/runs/{run_id}', headers={'x-user': 'bob'}).status_code, 404)
            run = client.get(f'/api/v1/factory/runs/{run_id}', headers={'x-user': 'alice'}).json()
            data = next(a for a in run['artifacts'] if a['kind'] == 'test.data')
            response = client.get(f'/api/v1/factory/runs/{run_id}/artifacts/{data["id"]}', headers={'x-user': 'alice'})
            self.assertEqual(response.json(), {'value': 3})
            self.assertEqual(client.post('/api/v1/factory/runs', json={'goals': ['test.data'], 'command': 'arbitrary'}).status_code, 422)
            self.assertEqual(client.post('/api/v1/factory/runs', json={'goals': ['test.data'], 'repository_url': 'https://example.com/foreign'}).status_code, 422)


    def test_generated_source_diff_and_zip_are_exact_owner_checked_attachments(self):
        with tempfile.TemporaryDirectory() as directory:
            service = FactoryService(Path(directory), [
                Stage('generate', 'Generate transport test files', 'test', 'generation', {},
                      {'diff': 'construction.code_diff', 'source': 'construction.cpp',
                       'package': 'construction.package'}, generated_artifacts),
            ])
            app = FastAPI()
            app.include_router(create_router(service, lambda request, scope: request.headers.get('x-user', 'operator')))
            client = TestClient(app)
            run = service.create({'goals': ['construction.package'], 'owner_id': 'alice'}, background=False)
            self.assertEqual(run['status'], 'completed')
            artifacts = {artifact['kind']: artifact for artifact in run['artifacts']}
            def fetch(kind, user='alice'):
                return client.get(f'/api/v1/factory/runs/{run["id"]}/artifacts/{artifacts[kind]["id"]}',
                                  headers={'x-user': user})
            diff = fetch('construction.code_diff')
            self.assertEqual(diff.status_code, 200)
            self.assertEqual(diff.headers['content-type'], 'application/json')
            self.assertEqual(diff.headers['x-content-type-options'], 'nosniff')
            self.assertTrue(diff.headers['content-disposition'].startswith('attachment;'))
            self.assertEqual(diff.json()['files'][0]['source_code'], DIFF_SOURCE)
            self.assertEqual(diff.json()['files'][0]['generated_code'], GENERATED_SOURCE)
            self.assertEqual(diff.content, Path(artifacts['construction.code_diff']['path']).read_bytes())
            source = fetch('construction.cpp')
            self.assertEqual(source.status_code, 200)
            self.assertTrue(source.headers['content-type'].startswith('text/plain'))
            self.assertEqual(source.text, GENERATED_SOURCE)
            package = fetch('construction.package')
            self.assertEqual(package.status_code, 200)
            self.assertEqual(package.headers['content-type'], 'application/zip')
            self.assertIn('filename="huawei_native_strata.zip"', package.headers['content-disposition'])
            self.assertEqual(package.headers['x-content-type-options'], 'nosniff')
            self.assertEqual(package.content, Path(artifacts['construction.package']['path']).read_bytes())
            with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
                self.assertEqual(archive.read('src/strata_core.cpp').decode(), GENERATED_SOURCE)
            for kind in artifacts:
                self.assertEqual(fetch(kind, 'bob').status_code, 404)
            Path(artifacts['construction.code_diff']['path']).write_text('{"changed":true}')
            self.assertEqual(fetch('construction.code_diff').status_code, 409)


if __name__ == '__main__':
    unittest.main()
