"""Repeated cases may reuse exact owned inputs, never replace different bytes."""
import asyncio
import hashlib

import pytest

from jiuwenswarm.research_sidecar.client import ResearchClient, ClientError


@pytest.mark.parametrize('same_bytes', [True, False])
def test_retained_upload_reuse_requires_exact_identity(tmp_path, same_bytes):
    path = tmp_path / 'train.csv'
    path.write_bytes(b'x,label\n1,0\n')
    record = {'id': 'upload:existing', 'kind': 'datasets', 'scope_id': 'local',
              'filename': 'train.csv', 'status': 'uploaded', 'size_bytes': path.stat().st_size,
              'content_sha256': hashlib.sha256(path.read_bytes()).hexdigest() if same_bytes else '0' * 64}
    client = object.__new__(ResearchClient)

    async def listing(scope):
        assert scope == 'local'
        return [record]

    async def no_write(*args, **kwargs):
        raise AssertionError('Retained uploads must not be replaced')

    client.list_uploads = listing
    client._request = no_write
    if same_bytes:
        assert asyncio.run(client.upload('datasets', 'local', path)) == record
    else:
        with pytest.raises(ClientError, match='different retained input bytes'):
            asyncio.run(client.upload('datasets', 'local', path))
