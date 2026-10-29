"""Initializer static capture uses the frozen release and real library allowances."""
import pytest

from jiuwenswarm.research.builder_mode import builder_mode
from jiuwenswarm.research.capsules.assets import (
    STAGE_VERSIONS, build_screening_asset, load_research_catalog,
)
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.local_profile import _screening_static_template
from jiuwenswarm.research.screening_static_capture import capture_static_template
from tests.unit_tests.research.test_budget_ceiling import installed_library


@pytest.mark.asyncio
@pytest.mark.parametrize('screening_version', ['m1-4', 'm1-5'])
@pytest.mark.parametrize('fault', [None, 'missing', 'insufficient', 'wrong_declaration'])
async def test_initializer_static_capture_requires_selected_builder_allowance(
        tmp_path, monkeypatch, screening_version, fault):
    # Use actual admissions and snapshot budget derivation, without model calls.
    store, _, _, library, installed, actor = await installed_library(
        tmp_path, scientific=True, scientific_memory=512 if fault == 'insufficient' else 32768)
    try:
        if screening_version == 'm1-5':
            asset = build_screening_asset(store)
            library.associate_checks(asset['declaration_ref'], asset['bundle_ref'], asset['profile_ref'], actor)
            admission = await library.admit(asset['declaration_ref'], asset['body_refs'], actor, memory_mb=32768)
            assert store.read_record(admission)['status'] == 'admitted'
            library.set_standing('research.screening', screening_version, 'active', actor, reason='Selected release fixture')

        # These are the same operator capture and validation used by compose_core
        # when initialize_profile calls it with initialize=True.
        expected_ref = _screening_static_template(store, screening_version)
        template = store.read_record(expected_ref, contract_id='static-template')
        node = next(n for n in template['nodes'] if n['node_id'] == 'builder')
        asset = load_research_catalog()['stages']['builder']
        assert node['cc'] == installed['builder']['pin']
        assert node['cc']['cc_version'] == STAGE_VERSIONS['builder']
        assert node['cc']['declaration_sha256'] == asset['declaration_ref']['sha256']
        declaration = store.read_record(asset['declaration_ref'])
        assert builder_mode(declaration) == 'agent'
        assert {'path': 'builder_mode.py', 'sha256': asset['body_refs']['builder_mode.py']['sha256']} in declaration['identity']['body']

        if fault == 'missing':
            library.set_standing(node['cc']['cc_name'], node['cc']['cc_version'], 'suspended', actor,
                                 reason='Genuinely unavailable selected Builder')
        snapshot = store.read_record(library.snapshot(), contract_id='library-snapshot')
        builder_entries = [e for e in snapshot['entries'] if e['cc_name'] == node['cc']['cc_name']]
        if fault == 'missing':
            assert builder_entries == []
        else:
            assert len(builder_entries) == 1
            assert builder_entries[0]['declaration_sha256'] == asset['declaration_ref']['sha256']
        if fault == 'wrong_declaration':
            # Same name/version and adequate budget must not substitute for the
            # declaration containing the selected Builder dependency closure.
            builder_entries[0]['declaration_sha256'] = '0' * 64
            snapshot_ref = store.put_record('library-snapshot', snapshot)
            monkeypatch.setattr(library, 'snapshot', lambda: snapshot_ref)
        if fault is not None:
            with pytest.raises(ResearchError, match='exact eligible aggregate library allowance') as error:
                capture_static_template(store, library, screening_version=screening_version, expected_ref=expected_ref)
            assert error.value.code == 'static_template_pin'
        else:
            assert capture_static_template(store, library, screening_version=screening_version,
                                           expected_ref=expected_ref) == expected_ref
    finally:
        store.close()
