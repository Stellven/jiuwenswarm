import asyncio
import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from jiuwenswarm.research.contracts.types import Principal, ResearchError
from jiuwenswarm.research.uploads import UploadManager


class UploadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Mock()
        self.store.publish_upload.side_effect = lambda record, original, extracted: record
        self.extract = AsyncMock(return_value='café 😀\n'.encode())
        self.manager = UploadManager(self.store, Path(self.tmp.name), self.extract, extraction_timeout_s=1)
        self.principal = Principal('owner', frozenset({'w'}), frozenset({'upload', 'list_uploads', 'delete_upload'}))

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_extract_once_exact_bytes_and_no_dataset_reasoning(self):
        record = await self.manager.upload(self.principal, 'docs', 'project', 'paper.pdf', b'%PDF-test')
        self.assertEqual(record['text_sha256'], hashlib.sha256('café 😀\n'.encode()).hexdigest())
        self.extract.assert_awaited_once()
        await self.manager.upload(self.principal, 'datasets', 'project', 'data.bin', b'raw')
        self.assertEqual(self.extract.await_count, 1)
        self.assertEqual(self.store.publish_upload.call_args.args[2], None)

    async def test_unsafe_paths_archive_and_types_publish_nothing(self):
        for name in ['../escape.txt', '/absolute.txt', 'x/y.txt', 'x\\y.txt', 'bad.exe']:
            with self.assertRaises(ResearchError):
                await self.manager.upload(self.principal, 'docs', 'project', name, b'bad')
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            archive.writestr('../escape', 'bad')
        with self.assertRaises(ResearchError):
            await self.manager.upload(self.principal, 'repo', 'project', 'repo.zip', output.getvalue())
        self.store.publish_upload.assert_not_called()

    async def test_extract_timeout_publishes_nothing(self):
        self.extract.side_effect = TimeoutError('bounded')
        with self.assertRaises(ResearchError):
            await self.manager.upload(self.principal, 'docs', 'project', 'bad.pdf', b'%PDF')
        self.store.publish_upload.assert_not_called()
