"""The headline endpoint serves a linked, digest-verified native publication."""
import hashlib
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jiuwenswarm.factory.store import Store
from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService, attach_factory_routes


def test_headlines_selects_latest_published_artifact_and_rejects_tampering(tmp_path):
    task = 'spark-direct-benchmarks-20261120'
    old = {'schema': 'spark-final-headlines/1', 'title': 'Draft', 'summary': '', 'rows': []}
    final = {**old, 'title': 'Final'}
    with Store(tmp_path) as store:
        store.create_task(dict(task_id=task, objective='Synthetic headline publication'))

        def add(payload):
            raw = json.dumps(payload).encode()
            digest = hashlib.sha256(raw).hexdigest()
            artifact_id = f'source:OPS/final-headlines.json@sha256:{digest}'
            return store.put_artifact(task, artifact_id, raw, 'application/json', None)

        draft_artifact = add(old)
        store.append_observation(task, dict(kind='report_publication',
                                           source_artifacts=[draft_artifact['artifact_id']]))
        final_artifact = add(final)
        store.append_observation(task, dict(kind='report_publication',
                                           source_artifacts=[final_artifact['artifact_id']]))
        add({**old, 'title': 'Stored but unpublished'})

    app = FastAPI()
    attach_factory_routes(app, service=FactoryHttpService(roots=[tmp_path]))
    client = TestClient(app)
    response = client.get('/api/factory/headlines')
    assert response.status_code == 200
    assert response.json()['payload'] == final
    assert response.json()['sha256'] == final_artifact['sha256']
    assert response.json()['source_artifacts'] == [final_artifact['artifact_id']]

    (tmp_path / final_artifact['location']).write_text('tampered')
    assert client.get('/api/factory/headlines').status_code == 422
