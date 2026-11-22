"""An agent-facing methodology workbench; advice does not grant execution."""
from __future__ import annotations

LAYERS = ('storage', 'placement', 'expert_prediction', 'expert_transfer', 'cpu_scheduling',
          'kernels', 'prefill', 'decode', 'cache', 'drafting', 'runtime', 'telemetry')
SCOPES = {
    'configuration_invariant': ('component', ['schema and applicability', 'exact changed fields', 'negative and boundary cases'],
        ['configuration verification does not establish engine correctness or speed']),
    'prediction_quality': ('offline_replay', ['request-separated temporal holdout', 'causal availability at decision time',
        'frequency and last-token baselines', 'coverage, wasted bytes and readiness/stall counters'],
        ['replay coverage does not establish an inference speedup', 'synthetic traces are test fixtures only']),
    'subsystem_performance': ('subsystem', ['fixed model/image/workload', 'one changed variable', 'warmup positions retained',
        'fresh-process counterbalanced confirmation', 'outputs and engagement compared', 'raw counters and failure receipts'],
        ['subsystem gains do not establish end-to-end speed or full-generation quality']),
    'end_to_end_performance': ('integration', ['fixed public correctness sample and decoding', 'untraced paired control/candidate',
        'TTFT, prefill, decode and combined rates reported separately', 'resource and cache state', 'uncertainty and regressions'],
        ['component ratios cannot be multiplied into a system speedup']),
    'recovery_reliability': ('fault_recovery', ['bounded injected failure', 'durable partial evidence', 'lease and process cleanup',
        'idempotent reconciliation', 'resume without duplicate submissions'],
        ['a single successful recovery does not establish weeks of unattended reliability']),
}


def test_scope(claim, layer):
    if claim not in SCOPES or layer not in LAYERS:
        raise ValueError('Choose a supported claim and engine layer from the package scope material')
    scope, checks, limits = SCOPES[claim]
    return dict(claim=claim, layer=layer, smallest_useful_scope=scope, verification_obligations=checks,
        limitations=limits, execution_authorized=False, promotion_authorized=False,
        next_step='Agent chooses a justified hypothesis and an admitted test; this is advice, not a scheduled run.')


def dispatch(store, task_id, operation, inputs):
    if operation == 'test_scope':
        from .api import fields
        fields(inputs, {'claim', 'layer'}, {'claim', 'layer'})
        return {'analysis': test_scope(**inputs)}
    if operation in {'diagnose', 'cache_protocol', 'ablation', 'followup'}:
        from .methodology import dispatch as route
        return route(store, task_id, operation, inputs)
    if operation == 'propose':
        from .hypotheses import dispatch as route
        return route(store, task_id, operation, inputs)
    if operation in {'profile_plan', 'analyze_profile'}:
        from .deep_profile import dispatch as route
        return route(store, task_id, {'profile_plan': 'plan', 'analyze_profile': 'analyze'}[operation], inputs)
    if operation == 'evaluate_prediction':
        from .expert_prediction import dispatch as route
        return route(store, task_id, 'evaluate', inputs)
    raise ValueError('Unknown inference methodology capability')
