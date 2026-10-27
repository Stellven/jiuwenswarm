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


async def prepare_intent_m1_8_release(store, *, base=None, verify_catalog=True):
    """Additive Intent m1-8: the m1-7 wall limit plus two general clarification rules in a new pinned prompt."""
    if base is None:
        from .compiler import prepare_compiler_assets
        base = (await prepare_compiler_assets(store))['intent']
    declaration = copy.deepcopy(store.read_record(base['declaration_ref']))
    if declaration['identity']['version_label'] != 'm1-6':
        raise ResearchError('asset_integrity', 'Intent m1-8 needs exact packaged m1-6 base')
    package = files('jiuwenswarm')
    new_paths = ['research/capsules/intent_m1_8.py', 'research_assets/compiler/intent_m1_8.txt']
    old_body_paths = {row['path'] for row in declaration['identity']['body']}
    body_refs = {**{path: ref for path, ref in base['body_refs'].items() if path not in old_body_paths},
                 **{path: store.put_blob(package.joinpath(path).read_bytes()) for path in new_paths}}
    declaration['identity']['version_label'] = 'm1-8'
    declaration['identity']['carrier'] = {'ref': new_paths[0], 'sha256': body_refs[new_paths[0]]['sha256']}
    declaration['identity']['body'] = [{'path': path, 'sha256': body_refs[path]['sha256']} for path in new_paths]
    declaration['budget']['per_call']['wall_s'] = 420
    bundle = copy.deepcopy(store.read_record(base['bundle_ref']))
    bundle.update(id='intent.compiler.checks.m1-8', target_cc_version_range='m1-8')
    profile = copy.deepcopy(store.read_record(base['profile_ref']))
    profile.update(id='intent.compiler.profile.m1-8.schema_context_2', target_cc_version_range='m1-8')
    from .checks.schema_context import frozen_output_instructions
    instructions = package.joinpath('research_assets/compiler/verifier.txt').read_bytes()
    profile['instruction_ref'] = store.put_blob(frozen_output_instructions(instructions, declaration), media_type='text/plain')
    result = dict(base, declaration=declaration, declaration_ref=store.put_record('capsule-declaration', declaration),
                  body_refs=body_refs, bundle=bundle, bundle_ref=store.put_record('check-bundle', bundle),
                  profile_ref=store.put_record('checking-profile', profile))
    if verify_catalog:
        expected = json.loads(package.joinpath('research_assets/compiler/intent_m1_8_catalog.json').read_text('utf-8'))
        if json.loads(json_bytes(result)) != expected:
            raise ResearchError('asset_integrity', 'Intent m1-8 differs from explicit release pins')
    return result
