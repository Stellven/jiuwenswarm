"""Pure, bounded prefill chunk treatment for the pinned native Strata engine."""
from __future__ import annotations
import copy
import re
from .strata_components import SOURCE_REVISION, _digest, _flag, apply as validate_profile

COMPONENT = 'strata.prefill_chunk'
CHUNKS = (256, 512, 1024)


def apply(base_profile, chunk_tokens):
    if type(chunk_tokens) is not int or chunk_tokens not in CHUNKS:
        raise ValueError('chunk_tokens must be an integer in 256, 512, 1024')
    # Reuse the fixed full-six/static-cache/no-prefix-reuse envelope without
    # changing drafting. That validator also excludes DS4_CHUNK/WINDOWS overrides.
    if not isinstance(base_profile, dict):
        raise ValueError('base_profile must be a JSON object')
    args = base_profile.get('args')
    if not isinstance(args, list):
        raise ValueError('base_profile.args must be a list')
    drafting, _ = _flag(args, '--dspark')
    if drafting not in {'none', 'on'}:
        raise ValueError('Explicit dspark none/on required')
    # The opt-in fixed-placement extension is orthogonal to chunk selection.
    # Validate it locally, then preserve it through the original profile guard;
    # this does not widen any historical benchmark contract or admit an image.
    guarded = copy.deepcopy(base_profile)
    env_key = 'environment' if 'environment' in guarded else 'env'
    environment = guarded.get(env_key)
    fixed_budget = None
    if isinstance(environment, dict) and 'DS4_EXPERT_BUDGET_BYTES' in environment:
        fixed_budget = environment.pop('DS4_EXPERT_BUDGET_BYTES')
        if (not isinstance(fixed_budget, str) or not re.fullmatch('[1-9][0-9]{0,11}', fixed_budget)
                or not 2**30 <= int(fixed_budget) <= 128*2**30):
            raise ValueError('Fixed expert budget must be decimal bytes between 1 and 128 GiB')
    result = validate_profile(guarded, drafting == 'on')['profile']
    if fixed_budget is not None:
        result[env_key]['DS4_EXPERT_BUDGET_BYTES'] = fixed_budget
    current, index = _flag(result['args'], '--prefill-chunk')
    if current not in {str(v) for v in CHUNKS}:
        raise ValueError('Explicit bounded prefill chunk required')
    requested = str(chunk_tokens)
    result['args'][index] = requested
    changed = current != requested
    return dict(profile=result, change=dict(component=COMPONENT,
        capsule='engine.strata_prefill_chunk', source_revision=SOURCE_REVISION,
        mechanism='Native layer-major prompt chunk size; positive explicit value',
        setting='--prefill-chunk', before=current, after=requested, changed=changed,
        changed_paths=[f'args[{index}]'] if changed else [], maximum_changed_variables=1,
        before_sha256=_digest(base_profile), after_sha256=_digest(result),
        status='candidate_profile_only', performance_benefit='unknown',
        required_evidence=['effective positive chunk in native startup',
            'full-six expert engagement', 'frozen public-task regression gate',
            'counterbalanced native prefill plus decode comparison',
            'placement and peak-memory accounting'],
        fixed_budget_engine_required=fixed_budget is not None,
        authority='No engine launch, jobs, source edits, contract mutation or promotion.'))


def coverage(prompt_lengths, baseline_chunk, candidate_chunk):
    """Predict chunk-count exposure before spending a correctness lab run."""
    if any(type(v) is not int or v not in CHUNKS for v in (baseline_chunk, candidate_chunk)):
        raise ValueError('Coverage requires bounded explicit chunk sizes')
    if (not isinstance(prompt_lengths, list) or not 1 <= len(prompt_lengths) <= 4096
            or any(type(v) is not int or not 1 <= v <= 8192 for v in prompt_lengths)):
        raise ValueError('Supply 1..4096 prompt lengths of 1..8192 tokens')
    rows = [dict(prompt_tokens=n, baseline_chunks=(n+baseline_chunk-1)//baseline_chunk,
                 candidate_chunks=(n+candidate_chunk-1)//candidate_chunk) for n in prompt_lengths]
    changed = sum(r['baseline_chunks'] != r['candidate_chunks'] for r in rows)
    return dict(cases=rows, predicted_changed_chunk_count_cases=changed,
                total_cases=len(rows), predicted_exposure_fraction=changed/len(rows),
                status='no_predicted_chunk_count_change' if not changed else 'predicted_chunk_count_change',
                runtime_engagement_verified=False, correctness_established=False,
                limitation='Static count prediction only; confirm native chunk engagement. Equal counts do not prove identical allocation, placement or kernels.')


def dispatch(inputs, capability='apply'):
    if capability == 'coverage':
        if not isinstance(inputs, dict) or set(inputs) != {'prompt_lengths', 'baseline_chunk', 'candidate_chunk'}:
            raise ValueError('coverage requires prompt_lengths, baseline_chunk and candidate_chunk')
        return {'analysis': coverage(**inputs)}
    if capability != 'apply':
        raise ValueError('Unknown prefill capability')
    if not isinstance(inputs, dict) or set(inputs) != {'base_profile', 'chunk_tokens'}:
        raise ValueError('apply requires exactly base_profile and chunk_tokens')
    return apply(inputs['base_profile'], inputs['chunk_tokens'])
