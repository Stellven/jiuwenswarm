"""Methods and execution locations for the two recorded Muse replays.

Native stage strings rank verifier evidence. A CPU fixture can reach the
"runtime acceptance" level while still belonging to the Factory stage.
"""
from difflib import unified_diff
import hashlib
import json


FACTORY = 'factory'
RUNTIME = 'runtime'
MIXED = 'mixed'
PREFIX_METHOD = "Turns on the engine's built-in prompt cache for document follow-up workloads."


def check(stage, method, role='Node verifier', verifier_role=None):
    result = dict(stage=stage, method=method, role=role)
    if verifier_role:
        result['verifier_role'] = verifier_role
    return result


def node(title, method, **checks):
    return dict(title=title, method=method, checks=checks)


RUN1_NODES = {
    'pin_inputs': node('Pin build inputs', 'Record source, workload and artifact identities before building.',
                       pins=check(FACTORY, 'Verify input identities and record the build resource budget.')),
    'ingest_nvfp4': node('Convert checkpoint weights',
                         'Map checkpoint tensors to the engine weight format and verify the conversion on a fixture.',
                         converter=check(FACTORY, 'Check format conversion and weight values against a small fixture.',
                                         verifier_role='CC verifier'),
                         nvfp4_pack=check(FACTORY, 'Check the pack manifest, tensor layout and weight types.',
                                          verifier_role='CC verifier')),
    'wire_expert_scales': node('Wire quantization scales',
                              'Apply stored weight scales at the engine operation that consumes them.',
                              change=check(FACTORY, 'Compile and verify numerical agreement on small fixtures.',
                                           verifier_role='CC verifier')),
    'build_base_engine': node('Build the baseline engine', 'Build the pinned engine source and check that it starts on the target.',
                              base_engine=check(FACTORY, 'Check the build receipt and produced executable identity.'),
                              smoke=check(RUNTIME, 'Check a real-model response on the target.')),
    'requant_2bit': node('Build a mixed-precision pack', 'Select formats by weight group from a sensitivity census and produce a pack.',
                         recipe=check(FACTORY, 'Check that the recipe pins compatible weight formats and inputs.',
                                      verifier_role='CC verifier'),
                         pack_2bit=check(FACTORY, 'Verify the resulting shard manifest, tensor types and preserved scales.',
                                         verifier_role='CC verifier')),
    'size_prefill_batch': node('Size the prefill batch', "Size prefill batches to the target's device budget from measured costs.",
                               batch_plan=check(MIXED, 'Check the plan structure and compare actual buffers and outputs on the target.',
                                                verifier_role='CC verifier')),
    'build_image': node('Package the engine image', 'Package the built executable and pin its launch configuration.',
                        image=check(FACTORY, 'Verify that the image identity matches the successful build receipt.'),
                        image_check=check(FACTORY, 'Check that the executable starts and reports its version without a model.'),
                        run_config=check(FACTORY, 'Verify the launch configuration and its pinned runtime inputs.')),
    'deliver_to_lab': node('Deliver a sealed lab request', 'Send the checked image, test requirements and acceptance criteria to the target lab.',
                           lab_request=check(FACTORY, 'Verify the sealed lab request refers to the checked artifacts.')),
}

RUN2_NODES = {
    'pin_inputs': node('Pin delivered engine inputs', 'Record the existing engine, weights and launch plan by identity.',
                       pinned_inputs=check(FACTORY, 'Verify the delivered input digests and required measurement records.')),
    'plan_prefix_store': node('Configure prefix reuse', PREFIX_METHOD,
                              prefix_plan=check(FACTORY, 'Check launch arguments and projected buffer usage against the memory budget.',
                                                verifier_role='CC verifier')),
    'build_image': node('Package the configured image', 'Package the approved launch configuration around the pinned engine.',
                        image=check(FACTORY, 'Verify that the image identity matches the successful build receipt.'),
                        factory_stage=check(FACTORY, 'Compare launch arguments, engine and pack digests, and memory accounting.')),
    'deliver_to_lab': node('Deliver a sealed lab request', 'Send the checked image, test requirements and acceptance criteria to the target lab.',
                           lab_package=check(FACTORY, 'Match the sealed delivery to the accepted factory checks.')),
    'measure_engine': node('Measure target behavior', 'The lab agent runs the delivered tests on the target and decides whether the engine meets them.',
                           measurements=check(RUNTIME, 'Judge request timings, cache reuse and answer identity from the target run.',
                                              role='Lab acceptance')),
    'release_gate': node('Decide release', 'Release only when factory checks and runtime evidence agree for the same delivery.',
                         release=check(FACTORY, 'Verify that the accepted target verdict belongs to the sealed factory delivery.')),
}


def argument_diff(builder, path, before, after, sources, label):
    """Add a readable diff derived from the recorded argument projection."""
    def lines(value):
        return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n').splitlines(keepends=True)

    raw = ''.join(unified_diff(lines(before), lines(after),
                               fromfile='before.json', tofile='after.json')).encode()
    target = builder.stage / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    builder.files[path] = dict(source='record_projection', sources=sources, display_name=label,
                               sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))
    return dict(path=path, label=label)
