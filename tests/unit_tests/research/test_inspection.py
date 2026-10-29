import hashlib
import io
import json
import unittest
import zipfile
from unittest.mock import Mock
from jiuwenswarm.research.contracts.types import Principal, ResearchError
from jiuwenswarm.research.inspection import build_retrieval, encode_export_zip


class InspectionTests(unittest.TestCase):
    def test_authorized_exact_bytes_and_withholding(self):
        store = Mock(); store.read_blob.return_value = b'visible'
        ref = {'id': 'blob:visible', 'sha256': hashlib.sha256(b'visible').hexdigest()}
        principal = Principal('owner', operations=frozenset({'export'}))
        files = [{'path': 'report.md', 'artifact_ref': ref, 'media_type': 'text/markdown', 'audience': 'researcher'},
                 {'path': 'private.md', 'artifact_ref': ref, 'media_type': 'text/plain', 'audience': 'reviewer'}]
        result, contents = build_retrieval(store, principal, 'run:1', 'owner', 'researcher', files, allowed_refs=[ref])
        self.assertEqual(contents, {'report.md': b'visible'})
        self.assertEqual(result['artifact_refs'], [ref])
        self.assertEqual(len(result['redactions']), 1)
        encoded = encode_export_zip(result, contents)
        with zipfile.ZipFile(io.BytesIO(encoded)) as archive:
            self.assertEqual(set(archive.namelist()), {'client_retrieval.json', 'report.md'})
            self.assertEqual(archive.read('report.md'), b'visible')
            self.assertEqual(json.loads(archive.read('client_retrieval.json')), result)
        for bad in [{'report.md': b'swapped'}, {'report.md': b'visible', 'unexpected.txt': b'bad'}, {}]:
            with self.assertRaises(ResearchError):
                encode_export_zip(result, bad)

    def test_path_and_foreign_run_no_side_effects(self):
        store = Mock(); principal = Principal('owner', operations=frozenset({'export'}))
        with self.assertRaises(ResearchError):
            build_retrieval(store, principal, 'run:foreign', 'foreign', 'researcher', [], allowed_refs=[])
        with self.assertRaises(ResearchError):
            build_retrieval(store, principal, 'run:1', 'owner', 'researcher', [{'path': '../escape'}], allowed_refs=[])
        store.read_blob.assert_not_called()


@__import__('pytest').mark.asyncio
async def test_finite_inspection_exports_exact_owned_originals_without_private_policy_or_work(tmp_path):
    from tests.unit_tests.research.test_finite_e1 import finite_execution_fixture
    from jiuwenswarm.research.control import ResearchService
    from jiuwenswarm.research.run_evidence import RunEvidence
    store, owner, protected, inputs, scheduler, prompts = await finite_execution_fixture(tmp_path, 'valid')
    try:
        evidence = RunEvidence(store, owner.library)
        evidence.start('run:finite-visible', protected)
        scheduler.evidence = scheduler.runner.evidence = evidence
        result = await owner.execute('run:finite-visible', protected, scheduler=scheduler)
        assert result['status'] == 'completed', result
        evidence.finish('run:finite-visible')
        service = ResearchService(store, registry=scheduler.runner.registry, model=scheduler.runner.model, scheduler=scheduler, finite_e1=owner, evidence=evidence)
        actor = Principal('owner', workspace_ids=frozenset({'work'}), operations=frozenset({'export'}), audiences=frozenset({'researcher', 'reviewer'}))
        before = len(prompts)
        manifest, contents = await service.artifact_bytes(actor, 'run:finite-visible')
        qualification = next(store.iter_records(run_id='run:finite-visible', kinds=('finite-e1-fixture-qualification',)))
        binding = next(store.iter_records(run_id='run:finite-visible', kinds=('finite-e1-plan-binding',)))
        refs = [qualification['ref'], binding['ref'], owner.binding_ref, result['plan_ref'], *inputs.values(), *qualification['record']['visible_refs']]
        assert all(ref in manifest['artifact_refs'] for ref in refs)
        assert all(store.read_blob(ref) in contents.values() for ref in refs)
        assert owner._binding['qualification_policy_ref'] not in manifest['artifact_refs']
        policy_raw = store.read_blob(owner._binding['qualification_policy_ref'])
        assert policy_raw not in contents.values()
        assert len(prompts) == before
        package = encode_export_zip(manifest, contents)
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            assert all(archive.read(path) == raw for path, raw in contents.items())
        stranger = Principal('foreign', workspace_ids=frozenset({'work'}), operations=frozenset({'export'}))
        with __import__('pytest').raises(ResearchError):
            await service.artifact_bytes(stranger, 'run:finite-visible')
        assert len(prompts) == before
    finally:
        store.close()
