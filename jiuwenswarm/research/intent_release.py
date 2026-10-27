"""Additive Intent wall-time release; historical declaration and bodies stay pinned."""
import copy
import json
from importlib.resources import files

from .contracts import ResearchError
from .state import json_bytes


async def prepare_intent_release(store, *, base=None, verify_catalog=True):
    if base is None:
        from .compiler import prepare_compiler_assets
        base = (await prepare_compiler_assets(store))['intent']
    declaration = copy.deepcopy(store.read_record(base['declaration_ref']))
    if declaration['identity']['version_label'] != 'm1-6':
        raise ResearchError('asset_integrity', 'Intent m1-7 needs exact packaged m1-6 base')
    declaration['identity']['version_label'] = 'm1-7'
    declaration['budget']['per_call']['wall_s'] = 420
    bundle = copy.deepcopy(store.read_record(base['bundle_ref']))
    bundle.update(id='intent.compiler.checks.m1-7', target_cc_version_range='m1-7')
    profile = copy.deepcopy(store.read_record(base['profile_ref']))
    profile.update(id='intent.compiler.profile.m1-7.schema_context_2', target_cc_version_range='m1-7')
    from .checks.schema_context import frozen_output_instructions
    instructions = files('jiuwenswarm').joinpath('research_assets/compiler/verifier.txt').read_bytes()
    profile['instruction_ref'] = store.put_blob(frozen_output_instructions(instructions, declaration), media_type='text/plain')
    result = dict(base, declaration=declaration, declaration_ref=store.put_record('capsule-declaration', declaration),
                  bundle=bundle, bundle_ref=store.put_record('check-bundle', bundle),
                  profile_ref=store.put_record('checking-profile', profile))
    if verify_catalog:
        expected = json.loads(files('jiuwenswarm').joinpath('research_assets/compiler/intent_m1_7_catalog.json').read_text('utf-8'))
        if json.loads(json_bytes(result)) != expected:
            raise ResearchError('asset_integrity', 'Intent m1-7 differs from explicit release pins')
    return result
