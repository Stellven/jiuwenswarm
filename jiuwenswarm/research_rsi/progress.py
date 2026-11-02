"""Payload-free stage telemetry. Reporting never changes execution authority."""
import time

SCHEMA = 'ai4r-rsi-stage-event:1'
STAGES = {
    'starting': 'Starting worker', 'parent': 'Parent evaluation',
    'baseline': 'Benchmark baseline', 'diagnose': 'Diagnose',
    'propose': 'Propose edits', 'verify': 'Verify candidate',
    'benchmark': 'Benchmark candidate', 'select': 'Rank & select',
    'finalizing': 'Publishing results', 'failed': 'Worker stopped',
}


def emit(store, session, stage, *, iteration=0, completed_iterations=0, model_calls=None, executions=None):
    """Only fixed stage names and counters enter the progress channel."""
    if stage not in STAGES:
        raise ValueError('Unknown RSI stage')
    try:
        store.put({'schema': SCHEMA, 'run_id': session['id'], 'target_id': session['capsule_name'],
                   'stage': stage, 'at': time.time(), 'iteration': iteration,
                   'completed_iterations': completed_iterations,
                   'model_calls': model_calls, 'executions': executions})
    except Exception:
        # Telemetry is not a model/evaluator effect and must not fail the run.
        pass
