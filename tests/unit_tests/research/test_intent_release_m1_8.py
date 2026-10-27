"""Intent m1-8: exact additive release carrying two general clarification rules; no model dispatch."""
import copy
import json
from contextlib import closing
from pathlib import Path

import pytest

from jiuwenswarm.research.checks import CheckRegistry
from jiuwenswarm.research.compiler import prepare_compiler_assets, register_compiler_capsules
from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.runner import Registry
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes
from tests.unit_tests.research.controlled_assets import ControlledLibraryService
from tests.unit_tests.research.test_intent_release import capture

COMPILER = Path('jiuwenswarm/research_assets/compiler')


@pytest.mark.asyncio
async def test_exact_additive_release_keeps_m1_6_and_m1_7_bytes(tmp_path):
    with closing(SQLiteRunStore(tmp_path)) as store:
        old = await prepare_compiler_assets(store)
        m17 = await prepare_compiler_assets(store, intent_version='m1-7')
        new = await prepare_compiler_assets(store, intent_version='m1-8')
        base, selected = old['intent'], new['intent']
        assert selected['declaration_ref'] != base['declaration_ref'] != m17['intent']['declaration_ref']
        assert selected['declaration']['identity']['version_label'] == 'm1-8'
        assert selected['declaration']['budget']['per_call']['wall_s'] == 420
        assert [row['path'] for row in selected['declaration']['identity']['body']] == [
            'research/capsules/intent_m1_8.py', 'research_assets/compiler/intent_m1_8.txt']
        # The m1-8 prompt is the historical prompt plus the appended rules, nothing removed.
        old_prompt = (COMPILER / 'intent.txt').read_bytes()
        new_prompt = (COMPILER / 'intent_m1_8.txt').read_bytes()
        assert new_prompt.startswith(old_prompt) and len(new_prompt) > len(old_prompt)
        text = new_prompt.decode()
        assert 'Essential-parameter rule' in text and 'Supplied-material rule' in text
        assert 'Contradictions between clauses stay explicit blocking uncertainties.' in text
        assert selected['bundle']['checks'] == base['bundle']['checks']
        for stage in ('requirements', 'planner', 'verifier'):
            assert new[stage] == old[stage]
        ControlledLibraryService(store)._validate_association(selected['declaration_ref'], selected['bundle_ref'], selected['profile_ref'])
        pinned = json.loads((COMPILER / 'intent_m1_8_catalog.json').read_text())
        assert json.loads(json_bytes(selected)) == pinned
        assert await prepare_compiler_assets(store) == old


@pytest.mark.asyncio
async def test_prepared_release_validation_rejects_drift_and_implicit_selection(tmp_path):
    with closing(SQLiteRunStore(tmp_path)) as store:
        selected = await prepare_compiler_assets(store, intent_version='m1-8')
        args = (None, None, None, store, None)
        checked = await register_compiler_capsules(*args, prepare_only=True, prepared_assets=selected, intent_version='m1-8')
        assert checked['intent'] == selected['intent']
        with pytest.raises(ResearchError):
            await register_compiler_capsules(*args, prepare_only=True, prepared_assets=selected)
        drift = copy.deepcopy(selected)
        drift['intent']['runner_ref'] = drift['intent']['declaration_ref']
        with pytest.raises(ResearchError, match='differs from exact explicit release'):
            await register_compiler_capsules(*args, prepare_only=True, prepared_assets=drift, intent_version='m1-8')


@pytest.mark.asyncio
async def test_registration_installs_the_m1_8_carrier_and_profile_freezes_selection(tmp_path):
    with closing(SQLiteRunStore(tmp_path / 'state')) as store:
        profile = capture(store, tmp_path, intent_version='m1-8')
        options = store.read_record(profile['binding_ref'])['protected_options']
        assert options['intent_version'] == 'm1-8'
        assert options['compiler_limits']['time_s'] == 900
        with pytest.raises(ResearchError, match='Frozen Intent release changed'):
            capture(store, tmp_path)
        registry, checks = Registry(), CheckRegistry()
        library = ControlledLibraryService(store)
        actor = Principal('operator', operations=frozenset({'verifier_assets', 'library_admit', 'library_standing'}))
        installed = await register_compiler_capsules(registry, checks, library, store, actor, activate=True, intent_version='m1-8')
        pin = installed['intent']['pin']
        assert pin['cc_version'] == 'm1-8'
        from jiuwenswarm.research.capsules.intent_m1_8 import execute
        handler, _ = registry.resolve(pin['cc_name'], pin['cc_version'], pin['declaration_sha256'])
        assert handler is execute
