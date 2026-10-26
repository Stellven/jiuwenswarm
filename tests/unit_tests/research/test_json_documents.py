"""Strict JSON reference uploads preserve original evidence without publication on failure."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.intake import extract_document, qualify_intake
from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research.uploads import UploadManager


class JSONDocumentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = SQLiteRunStore(self.root / 'store')
        self.addCleanup(self.store.close)
        self.principal = Principal('alice', frozenset({'project'}), frozenset({'upload', 'list_uploads', 'ingest'}))
        self.manager = UploadManager(self.store, self.root / 'uploads', extract_document,
                                     extraction_timeout_s=1, max_upload_bytes=4096)

    async def test_original_and_qualified_json_keep_exact_utf8_bytes(self):
        raw = '{\r\n  "reference": "😀e\u0301", "value": 1.00, "escaped": "\\u00e9"\r\n}\r\n'.encode('utf-8')
        record = await self.manager.upload(self.principal, 'docs', 'project', 'protocol.JSON', raw)
        self.assertEqual(self.store.read_upload(record['id'], 'alice'), raw)
        self.assertEqual(self.store.read_upload(record['id'], 'alice', extracted=True), raw)
        self.assertEqual(record['content_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(record['text_sha256'], record['content_sha256'])
        ref = self.store.put_blob(b'protected')
        qualified = qualify_intake(self.store, self.principal, 'Review reference', [record['id']],
            workspace_id='project', profile_ref=ref, workspace_ref=ref, input_directory_ref=ref)
        intake = self.store.read_record(qualified)
        self.assertEqual(len(intake['source_refs']), 1)
        self.assertEqual(self.store.read_blob(intake['source_refs'][0]), raw)
        self.assertEqual(intake['resource_refs'], [])

    async def test_invalid_json_never_publishes_or_creates_upload_paths(self):
        invalid = [b'{', b'{"x":1} trailing', b'{"x":1,"x":2}',
                   b'{"nested":{"a":1,"\\u0061":2}}', b'{"x":NaN}',
                   b'{"x":Infinity}', b'{"x":-Infinity}', b'{"x":1e999}',
                   b'{"x":"\xff"}', b'\xff\xfe{\x00}\x00', b'\xef\xbb\xbf{}']
        with patch.object(self.store, 'publish_upload', wraps=self.store.publish_upload) as publish:
            for raw in invalid:
                with self.subTest(raw=raw), self.assertRaises(ResearchError):
                    await self.manager.upload(self.principal, 'docs', 'project', 'bad.json', raw)
            publish.assert_not_called()
        self.assertEqual(self.store.list_uploads('alice', 'project'), [])
        self.assertFalse((self.store.input_root / 'docs' / 'project').exists())
        self.assertFalse((self.store.input_root / '.extracted').exists())

    async def test_json_keeps_upload_size_guard_before_extraction(self):
        extractor = AsyncMock(wraps=extract_document)
        manager = UploadManager(self.store, self.root / 'uploads', extractor,
                                extraction_timeout_s=1, max_upload_bytes=2)
        with self.assertRaises(ResearchError):
            await manager.upload(self.principal, 'docs', 'project', 'large.json', b'{"x":1}')
        extractor.assert_not_awaited()
        self.assertEqual(self.store.list_uploads('alice', 'project'), [])

    async def test_json_support_does_not_accept_loose_repository_sources(self):
        for name, raw in [('repo.py', b'print(1)'), ('repo.json', b'{}'), ('repo.zip', b'{}')]:
            with self.subTest(name=name), self.assertRaises(ResearchError):
                await self.manager.upload(self.principal, 'repo', 'project', name, raw)
        self.assertEqual(self.store.list_uploads('alice', 'project'), [])

    async def test_existing_text_formats_and_json_scalars_preserve_bytes(self):
        for name, raw in [('text.txt', b'plain\r\n'), ('notes.md', b'# Title\r\n'),
                          ('notes.markdown', b'plain\n'), ('list.json', b' [1, true, null] \r\n'),
                          ('scalar.json', b' "reference" '), ('null.json', b'null')]:
            with self.subTest(name=name):
                self.assertEqual(await extract_document(name, raw, timeout_s=1), raw)


if __name__ == '__main__':
    unittest.main()
