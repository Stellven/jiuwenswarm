"""Host replay of retained baseline artifacts under separately admitted slice pins."""
import json
from pathlib import Path
from .ccs.performance_baseline.numerical_replay import verify
from .experiment_jobs import ExperimentJobs
from .store import NotFound


def verify_attempt(store, task_id, attempt_id):
    task = store.get_task(task_id)
    expected = task['constraints'].get('baseline_numerical_replay')
    unverified = dict(status='unverified', reference_recomputed=False, promotion_authorized=False)
    if expected is None:
        return dict(unverified, reason='No independently admitted replay identity; historical self-checks are unverified')
    result = ExperimentJobs(store).result(task_id, attempt_id)
    if not result['analysis'].get('verified_complete'):
        return dict(unverified, reason='Diagnostic evidence incomplete')
    attempt = store.read(task_id, attempt_id)
    if attempt['request'].get('adapter') != 'factory-experiment-v1':
        raise ValueError('Baseline replay requires a retained construction diagnostic')
    # The worker retained the executed contract; use its model mount, not a path
    # supplied by the producer output. Slice/input digests come from task admission.
    contract_path = Path(task['contract_id'])
    import hashlib
    raw = contract_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != task['constraints']['benchmark_contract_sha256']:
        raise ValueError('Admitted diagnostic contract changed')
    model_path = Path(json.loads(raw)['model']['path'])
    def read_artifact(name):
        try:
            return store.artifact_bytes(task_id, attempt_id+':artifacts/'+name)
        except NotFound as exc:
            raise FileNotFoundError(name) from exc
    def read_slice(offset, size):
        with model_path.open('rb') as stream:
            stream.seek(offset)
            return stream.read(size)
    try:
        report = verify(expected, read_artifact, read_slice)
    except (ValueError, KeyError, OSError, OverflowError) as exc:
        report = dict(unverified, reason='Replay validation failed: '+str(exc))
    return dict(report, admission_verified=True, task_id=task_id, attempt_id=attempt_id)
