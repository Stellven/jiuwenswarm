"""Bounded offline numerical replay analysis. No engine, filesystem or GPU access."""
import hashlib
import json
import math

IDENTITY = {'model', 'tokenizer', 'source', 'precision', 'routing', 'profile'}
TREATABLE = {'source', 'precision', 'routing', 'profile'}
MAX_VOCAB = 262144
MAX_HISTORY = 16384
MAX_STEPS = 4096


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, minimum, maximum):
    require(type(value) is int and minimum <= value <= maximum, 'integer outside declared bounds')
    return value


def ids(value, maximum=MAX_HISTORY):
    require(type(value) is list and len(value) <= maximum, 'token sequence exceeds bound')
    for item in value:
        integer(item, 0, MAX_VOCAB - 1)
    return value


def finite(value):
    require(type(value) in (int, float) and math.isfinite(value), 'expected finite numeric value')
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def identity(value):
    require(type(value) is dict and set(value) == IDENTITY, 'identity must bind model/tokenizer/source/precision/routing/profile')
    require(all(type(v) is str and 0 < len(v) <= 256 for v in value.values()), 'identity values must be immutable nonempty references <=256 characters')
    return value


def policy(value):
    require(type(value) is dict and set(value) == {'declaration_id', 'absolute_tolerance', 'relative_tolerance', 'top_k'}, 'predeclared policy fields required')
    require(type(value['declaration_id']) is str and 0 < len(value['declaration_id']) <= 256, 'predeclared external declaration identity required')
    for name in ('absolute_tolerance', 'relative_tolerance'):
        require(0 <= finite(value[name]) <= 1, 'tolerance must be predeclared in [0,1]')
    integer(value['top_k'], 1, 32)
    return value


def replay_spec(baseline_identity, candidate_identity, prompt_ids, teacher_ids, step, vocabulary_size, treatment_fields, comparison_policy):
    """Freeze next-token history at zero-based output step; never generate tokens."""
    left, right = identity(baseline_identity), identity(candidate_identity)
    require(type(treatment_fields) is list and len(treatment_fields) == len(set(treatment_fields)), 'unique treatment field names required')
    require(set(treatment_fields) <= TREATABLE, 'model/tokenizer changes require a separate study')
    changed = {key for key in IDENTITY if left[key] != right[key]}
    require(changed == set(treatment_fields), 'identity mismatch must exactly equal explicitly declared treatment')
    ids(prompt_ids)
    ids(teacher_ids, MAX_STEPS)
    integer(step, 0, len(teacher_ids))
    integer(vocabulary_size, 2, MAX_VOCAB)
    history = prompt_ids + teacher_ids[:step]
    ids(history)
    require(bool(prompt_ids), 'nonempty tokenized prompt required')
    require(all(x < vocabulary_size for x in prompt_ids + teacher_ids), 'token outside vocabulary')
    spec = dict(schema='common-history-replay/1', baseline_identity=left, candidate_identity=right,
                prompt_ids=prompt_ids, teacher_ids=teacher_ids, step=step, history_ids=history,
                vocabulary_size=vocabulary_size, treatment_fields=treatment_fields,
                comparison_policy=policy(comparison_policy))
    return dict(spec=spec, spec_sha256=digest(spec), execution='not_executed',
                missing=['general engine teacher-force adapter (conditional no-draft capture available)', 'observer-on/off paired evidence'])


def validate_spec(spec):
    require(type(spec) is dict, 'spec object required')
    names = ('baseline_identity', 'candidate_identity', 'prompt_ids', 'teacher_ids', 'step', 'vocabulary_size', 'treatment_fields', 'comparison_policy')
    rebuilt = replay_spec(**{k: spec[k] for k in names})['spec']
    require(spec == rebuilt, 'replay spec is inconsistent or contains unknown fields')
    return rebuilt


def capture(value, spec, arm):
    require(type(value) is dict and set(value) == {'identity', 'spec_sha256', 'history_ids', 'step', 'vocabulary_ids', 'logits', 'complete', 'capture_id'}, 'capture schema mismatch')
    require(type(value['capture_id']) is str and 0 < len(value['capture_id']) <= 256, 'capture provenance identity required')
    require(value['identity'] == spec[arm + '_identity'], 'capture identity differs from frozen arm')
    require(value['spec_sha256'] == digest(spec), 'capture spec hash mismatch')
    require(type(value['step']) is int and value['step'] == spec['step'], 'capture step mismatch')
    ids(value['history_ids'])
    require(value['history_ids'] == spec['history_ids'], 'capture history mismatch')
    vocab = ids(value['vocabulary_ids'], MAX_VOCAB)
    require(len(vocab) >= 1 and len(set(vocab)) == len(vocab), 'vocabulary ids must be nonempty and unique')
    require(all(x < spec['vocabulary_size'] for x in vocab), 'vocabulary id outside frozen bounds')
    require(type(value['logits']) is list and len(value['logits']) == len(vocab), 'logit vector length mismatch')
    for x in value['logits']:
        finite(x)
    require(type(value['complete']) is bool, 'complete must be boolean')
    if value['complete']:
        require(len(vocab) == spec['vocabulary_size'], 'complete capture must include entire frozen vocabulary')
    return dict(zip(vocab, value['logits']))


def ranked(vector, k):
    rows = sorted(vector.items(), key=lambda pair: (-pair[1], pair[0]))
    # Finite inputs can still overflow subtraction, which must fail safely.
    margin = finite(rows[0][1] - rows[1][1])
    return dict(top=[dict(token_id=i, logit=x) for i, x in rows[:k]],
                margin=margin, tied_top=rows[0][1] == rows[1][1])


def compare_logits(spec, baseline, candidate):
    spec = validate_spec(spec)
    left = capture(baseline, spec, 'baseline')
    right = capture(candidate, spec, 'candidate')
    require(set(left) == set(right), 'captures must contain identical vocabulary id sets')
    p = spec['comparison_policy']
    differences = []
    violations = 0
    exact = True
    for token in sorted(left):
        delta = finite(abs(left[token] - right[token]))
        allowed = finite(p['absolute_tolerance'] + p['relative_tolerance'] * abs(left[token]))
        differences.append(delta)
        violations += delta > allowed
        exact = exact and left[token] == right[token]
    full = baseline['complete'] and candidate['complete']
    result = dict(schema='logit-comparison/1', spec_sha256=digest(spec), policy_sha256=digest(p),
                  capture_ids=[baseline['capture_id'], candidate['capture_id']],
                  coverage='full' if full else 'partial', compared_tokens=len(left),
                  maximum_absolute_difference=max(differences), observed_violations=violations,
                  exact_vectors=exact if full else 'unknown',
                  within_tolerance=(violations == 0) if full else 'unknown',
                  numerical_cause='unknown', engine_reproduction='not_established',
                  observer_effect='not_checked', quality='not_established')
    if full:
        a, b = ranked(left, p['top_k']), ranked(right, p['top_k'])
        result.update(baseline=a, candidate=b,
                      same_top_choice=a['top'][0]['token_id'] == b['top'][0]['token_id'],
                      margin_difference=finite(b['margin'] - a['margin']))
    else:
        result.update(baseline='unknown', candidate='unknown', same_top_choice='unknown', margin_difference='unknown')
    return result


def first_divergence(baseline_ids, candidate_ids, baseline_finish, candidate_finish):
    ids(baseline_ids, MAX_STEPS)
    ids(candidate_ids, MAX_STEPS)
    require(all(type(x) is str and 0 < len(x) <= 64 for x in (baseline_finish, candidate_finish)), 'explicit finish reasons required')
    common = 0
    while common < min(len(baseline_ids), len(candidate_ids)) and baseline_ids[common] == candidate_ids[common]:
        common += 1
    different_token = common < min(len(baseline_ids), len(candidate_ids))
    length_differs = len(baseline_ids) != len(candidate_ids)
    return dict(schema='first-output-divergence/1', common_prefix_tokens=common,
                first_different_index=common if different_token or length_differs else None,
                baseline_token=baseline_ids[common] if common < len(baseline_ids) else None,
                candidate_token=candidate_ids[common] if common < len(candidate_ids) else None,
                baseline_length=len(baseline_ids), candidate_length=len(candidate_ids),
                finish_equal=baseline_finish == candidate_finish,
                exact_output=baseline_ids == candidate_ids and baseline_finish == candidate_finish,
                token_ids_sha256=[digest(baseline_ids), digest(candidate_ids)],
                cause='unknown', claim='output identity only; does not establish matched engine or prompt provenance')


TOOLS = {'replay_spec': replay_spec, 'compare_logits': compare_logits, 'first_divergence': first_divergence}
