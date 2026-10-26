"""Explicit evidence-review pilot installs coexist with unchanged old releases."""
import copy
from contextlib import closing

import pytest

from jiuwenswarm.research.compiler import prepare_compiler_assets, register_compiler_capsules
from jiuwenswarm.research.capsules.assets import build_research_assets, register_research_capsules
from jiuwenswarm.research.capsules.paper_assets import build_paper_assets, register_paper_capsules
from jiuwenswarm.research.contracts import Principal
from jiuwenswarm.research.checks import CheckRegistry
from jiuwenswarm.research.checks import CheckContext
from jiuwenswarm.research.pilot_catalog import (
    capture_evidence_aware_pilot_catalog,
    prepare_evidence_aware_pilot_assets,
)
from jiuwenswarm.research.runner import Registry
from jiuwenswarm.research.state import SQLiteRunStore
from tests.unit_tests.research.controlled_assets import ControlledLibraryService


@pytest.mark.asyncio
async def test_check_registry_dispatches_same_bundle_id_by_exact_profile_ref(tmp_path):
    with closing(SQLiteRunStore(tmp_path)) as store:
        registry = CheckRegistry()
        implementation = store.put_blob(b'controlled check implementation')
        profile_a = store.put_blob(b'profile-a')
        profile_b = store.put_blob(b'profile-b')
        registry.register_bundle('same.cc.checks', ['review'],
            lambda *_: [{'check_id': 'review', 'outcome': 'PASS', 'reason': 'profile A', 'evidence_refs': []}],
            implementation_ref=implementation, profile_ref=profile_a)
        registry.register_bundle('same.cc.checks', ['review'],
            lambda *_: [{'check_id': 'review', 'outcome': 'FAIL', 'reason': 'profile B', 'evidence_refs': []}],
            implementation_ref=implementation, profile_ref=profile_b)
        context = CheckContext({}, store, {}, {}, {}, {})
        for profile, expected in ((profile_a, 'PASS'), (profile_b, 'FAIL')):
            result = await registry.run({'runner_refs': [implementation], 'profile_ref': profile,
                'mandatory_deterministic': []}, context, bundle_id='same.cc.checks')
            assert result[0]['outcome'] == expected


async def _install(library, store, actor, asset):
    library.associate_checks(asset['declaration_ref'], asset['bundle_ref'], asset['profile_ref'], actor)
    admission_ref = await library.admit(asset['declaration_ref'], asset['body_refs'], actor, memory_mb=16384)
    admission = store.read_record(admission_ref)
    assert admission['status'] == 'admitted', admission.get('reasons')
    identity = store.read_record(asset['declaration_ref'])['identity']
    library.set_standing(identity['name'], identity['version_label'], 'active', actor,
        reason='Controlled evidence-pilot install test')


@pytest.mark.asyncio
async def test_evidence_pilot_installs_new_verifier_and_variants_without_rewriting_old_releases(tmp_path):
    with closing(SQLiteRunStore(tmp_path)) as store:
        library = ControlledLibraryService(store)
        actor = Principal('pilot-owner', operations=frozenset({'verifier_assets', 'library_admit', 'library_standing'}))
        compiler = await prepare_compiler_assets(store)
        research = build_research_assets(store)
        paper = build_paper_assets(store)
        old_refs = {stage: (asset['declaration_ref'], asset['bundle_ref'], asset['profile_ref'])
                    for stage, asset in {**research, **paper}.items()}
        pilot = prepare_evidence_aware_pilot_assets(store, compiler_assets=compiler,
            research_assets=research, paper_assets=paper)

        # The installer accepts an explicit original+new verifier release list;
        # the original verifier identity remains byte-for-byte pinned.
        compiler_for_install = copy.deepcopy(compiler)
        compiler_for_install['verifier'] = [compiler['verifier'], pilot['compiler_assets']['verifier']]
        registry, checks = Registry(), CheckRegistry()
        installed_compiler = await register_compiler_capsules(registry, checks, library, store, actor,
            activate=True, initialize=True, memory_mb=16384, prepared_assets=compiler_for_install)
        assert installed_compiler['verifier']['pin']['cc_version'] == 'm1-3'
        old_verifier_identity = store.read_record(compiler['verifier']['declaration_ref'])['identity']
        assert library.get(old_verifier_identity['name'], old_verifier_identity['version_label'])['declaration_ref'] == compiler['verifier']['declaration_ref']

        for asset in (*research.values(), *paper.values(),
                      *pilot['research_assets'].values(), *pilot['paper_assets'].values()):
            await _install(library, store, actor, asset)
        register_research_capsules(registry, checks, library, store, assets=research)
        register_paper_capsules(registry, checks, library, store, assets=paper)
        for stage, asset in pilot['research_assets'].items():
            register_research_capsules(registry, checks, library, store,
                assets={stage.removesuffix('_evidence'): asset})
        for stage, asset in pilot['paper_assets'].items():
            register_paper_capsules(registry, checks, library, store,
                assets={stage.removesuffix('_evidence'): asset})

        assert all((asset['declaration_ref'], asset['bundle_ref'], asset['profile_ref']) == old_refs[stage]
                   for stage, asset in {**research, **paper}.items())
        for stage in ('evaluation', 'delivery', 'paper_summary', 'paper_delivery'):
            old = research[stage] if stage in research else paper[stage]
            assert library.get(store.read_record(old['declaration_ref'])['identity']['name'],
                               store.read_record(old['declaration_ref'])['identity']['version_label'])['declaration_ref'] == old['declaration_ref']

        catalog_ref = capture_evidence_aware_pilot_catalog(store, library,
            evidence_assets=pilot, original_assets={**research, **paper})
        catalog = store.read_record(catalog_ref)
        assert catalog['schema'] == 'ai4r-evidence-aware-pilot-catalog:1'
        assert catalog['changes_global_graph_selection'] is False
        assert {row['pin']['cc_version'] for row in catalog['candidate_releases']} == {
            'm1-5-evidence-1', 'paper-m1-5-evidence-1'}
        assert {row['pin']['cc_version'] for row in catalog['historical_output_only_pins']} == {
            'm1-5', 'paper-m1-5'}
        assert catalog['verifier_pin']['cc_version'] == 'm1-3'
        assert all(row['qualification_status'] == 'admission_recorded' for row in catalog['candidate_releases'])
