"""Closed prediction protocol and root-owned scoring after sandbox cessation.

Public parsers are pure. Only RootClassificationScorer opens the private
holdout, and neither its bytes nor its path are published to the product Store.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import stat
import uuid
from pathlib import Path

from .contracts import ResearchError, validate
from .state import json_bytes

PROTOCOL = 'ai4r-blind-classification:1'
PREDICTIONS = 'ai4r-predictions:1'
SCORE_SCHEMA = 'urn:ai4r:private:classification-scoring-receipt:1'
SCORE_KIND = 'classification-scoring-receipt'
BUILD_SCHEMA = 'urn:ai4r:prediction-build-receipt:2.0.0'
PRIVATE_PATH = '/run/ai4r-private-qa/holdout.json'
PROFILE_FIELDS = {'protocol', 'public_dataset_ref', 'public_file', 'public_data_sha256',
                  'holdout_path', 'holdout_sha256', 'scorer_sha256', 'max_stdout_bytes'}


def require(value, message):
    if not value:
        raise ResearchError('blind_scoring', message)


def _pairs(rows):
    value = {}
    for key, item in rows:
        require(key not in value, 'Duplicate JSON member')
        value[key] = item
    return value


def _json(raw):
    try:
        return json.loads(raw.decode('utf-8', errors='strict') if isinstance(raw, bytes) else raw,
            object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))
    except (UnicodeError, ValueError, TypeError) as error:
        raise ResearchError('blind_scoring', 'Expected one finite UTF-8 JSON document') from error


def _text(value, maximum=128):
    return type(value) is str and 0 < len(value) <= maximum and '\0' not in value


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def validate_public_dataset(value):
    require(type(value) is dict and set(value) == {'schema', 'dataset_id', 'feature_names', 'classes', 'train', 'test'}
            and value['schema'] == 'ai4r-classification-data:1' and _text(value['dataset_id']),
            'Public classification data has another closed schema')
    for key, maximum in (('feature_names', 64), ('classes', 64)):
        items = value[key]
        require(type(items) is list and 1 <= len(items) <= maximum
                and all(_text(item) for item in items) and len(items) == len(set(items)),
                'Public feature/class names are absent, duplicated or out of bounds')
    require(len(value['classes']) >= 2, 'Classification requires at least two declared string classes')
    seen = set()
    for split in ('train', 'test'):
        rows = value[split]
        require(type(rows) is list and 1 <= len(rows) <= 10000, 'Public split size is out of bounds')
        for row in rows:
            expected = {'id', 'features', 'label'} if split == 'train' else {'id', 'features'}
            require(type(row) is dict and set(row) == expected and _text(row['id']) and row['id'] not in seen,
                    'Public rows require unique IDs and test rows must contain no labels')
            seen.add(row['id'])
            features = row['features']
            require(type(features) is list and len(features) == len(value['feature_names'])
                    and all(_finite(number) for number in features),
                    'Public features must be finite numeric vectors of the declared dimension')
            if split == 'train':
                require(type(row['label']) is str and row['label'] in value['classes'],
                        'Training label is outside the declared string classes')
    return value


def parse_public_dataset(raw):
    require(type(raw) is bytes and 0 < len(raw) <= 16 * 1024 * 1024, 'Public dataset bytes exceed their bound')
    return validate_public_dataset(_json(raw))


def parse_predictions(raw, public, *, max_stdout_bytes):
    require(type(raw) is bytes and 0 < len(raw) <= max_stdout_bytes, 'Prediction output bytes exceed their bound')
    value = _json(raw)
    require(type(value) is dict and set(value) == {'predictions'} and type(value['predictions']) is list,
            'Child stdout must contain predictions only; reported metrics are not accepted')
    expected = {row['id'] for row in public['test']}
    predictions = {}
    for row in value['predictions']:
        require(type(row) is dict and set(row) == {'id', 'label'} and type(row['id']) is str
                and row['id'] in expected and row['id'] not in predictions
                and type(row['label']) is str and row['label'] in public['classes'],
                'Predictions contain a duplicate/unknown ID or undeclared class')
        predictions[row['id']] = row['label']
    require(set(predictions) == expected, 'Predictions do not cover every public test ID exactly once')
    return predictions


def _private_bytes(path):
    require(os.name == 'posix' and os.geteuid() == 0 and str(path) == PRIVATE_PATH,
            'Only the installed root scorer can open the fixed private holdout')
    parent = path.parent
    require(not path.is_symlink() and not parent.is_symlink()
            and parent.stat().st_uid == 0 and stat.S_IMODE(parent.stat().st_mode) == 0o700,
            'Private holdout directory custody is invalid')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        meta = os.fstat(fd)
        require(stat.S_ISREG(meta.st_mode) and meta.st_uid == 0 and meta.st_nlink == 1
                and stat.S_IMODE(meta.st_mode) == 0o600 and 0 < meta.st_size <= 4 * 1024 * 1024,
                'Private holdout file custody is invalid')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            return stream.read()
    finally:
        os.close(fd)


class RootClassificationScorer:
    def __init__(self, store, profile):
        require(os.name == 'posix' and os.geteuid() == 0, 'Root-only scoring registration is required')
        require(type(profile) is dict and set(profile) == PROFILE_FIELDS
                and profile['protocol'] == PROTOCOL and profile['public_file'] == 'data.json'
                and profile['holdout_path'] == PRIVATE_PATH,
                'Scoring profile is not the closed fixed classification protocol')
        validate('Ref', profile['public_dataset_ref'])
        for key in ('public_data_sha256', 'holdout_sha256', 'scorer_sha256'):
            require(type(profile[key]) is str and len(profile[key]) == 64
                    and all(ch in '0123456789abcdef' for ch in profile[key]), 'Scoring digest is invalid')
        require(type(profile['max_stdout_bytes']) is int and 1 <= profile['max_stdout_bytes'] <= 8388608,
                'Prediction stdout limit is invalid')
        require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == profile['scorer_sha256'],
                'Installed trusted scorer differs from its fixed source pin')
        self._store, self._profile = store, dict(profile)

    def score(self, job, raw, public_resource):
        require(os.geteuid() == 0 and 'trusted_scoring_ref' not in raw, 'Scoring is root-owned and cannot be repeated')
        profile = self._profile
        require(job.validation_ref == profile['public_dataset_ref']
                and self._store.read_record(profile['public_dataset_ref'], contract_id='resource-snapshot') == public_resource,
                'Scorer public resource differs from the exact issued job')
        files = [row for row in public_resource['files'] if row['path'] == profile['public_file']]
        require(len(files) == 1 and files[0]['artifact_ref']['sha256'] == profile['public_data_sha256'],
                'Scorer public data file differs from its frozen profile')
        public_raw = self._store.read_blob(files[0]['artifact_ref'])
        require(hashlib.sha256(public_raw).hexdigest() == profile['public_data_sha256'], 'Public data bytes changed')
        public = parse_public_dataset(public_raw)
        private_raw = _private_bytes(Path(profile['holdout_path']))
        require(hashlib.sha256(private_raw).hexdigest() == profile['holdout_sha256'], 'Private holdout bytes changed')
        holdout = _json(private_raw)
        require(type(holdout) is dict and set(holdout) == {'schema', 'dataset_id', 'public_data_sha256', 'labels'}
                and holdout['schema'] == 'ai4r-classification-holdout:1'
                and holdout['dataset_id'] == public['dataset_id']
                and holdout['public_data_sha256'] == profile['public_data_sha256'] and type(holdout['labels']) is list,
                'Private holdout does not join the exact public dataset')
        labels = {}
        for row in holdout['labels']:
            require(type(row) is dict and set(row) == {'id', 'label'} and type(row['id']) is str
                    and row['id'] not in labels and type(row['label']) is str and row['label'] in public['classes'],
                    'Private label identity or class is invalid')
            labels[row['id']] = row['label']
        require(set(labels) == {row['id'] for row in public['test']}, 'Private holdout ID coverage differs')
        require(raw['job_id'] == job.job_id and raw['contract_ref'] == dict(job.contract_ref)
                and raw['invocation_id'] == job.invocation_id and raw.get('observed_runtime') is True,
                'Scoring requires the exact original completed kernel execution')
        status, failure, metrics, correct = 'unmeasured', 'execution_failed', {}, None
        if raw['exit_code'] == 0 and raw.get('termination_reason') == 'completed':
            try:
                predictions = parse_predictions(self._store.read_blob(raw['stdout_ref']), public,
                                                max_stdout_bytes=profile['max_stdout_bytes'])
                correct = sum(predictions[key] == label for key, label in labels.items())
                metrics = {'accuracy': correct / len(labels)}
                status, failure = 'scored', None
            except ResearchError:
                failure = 'prediction_invalid'
        record = {'schema': 'ai4r-classification-scoring-receipt:1', 'id': 'classification-score:' + uuid.uuid4().hex,
            'run_id': job.run_id, 'node_id': job.node_id, 'attempt_id': job.attempt_id,
            'contract_ref': dict(job.contract_ref), 'invocation_id': job.invocation_id, 'job_id': job.job_id,
            'sequence': job.sequence, 'role': job.role, 'repeat_index': job.repeat_index, 'seed': job.seed,
            'subject_ref': dict(job.subject_ref), 'validation_ref': dict(job.validation_ref),
            'prediction_ref': dict(raw['stdout_ref']), 'execution_identity_sha256': hashlib.sha256(json_bytes(raw)).hexdigest(),
            'public_data_sha256': profile['public_data_sha256'], 'scorer_sha256': profile['scorer_sha256'],
            'holdout_commitment': profile['holdout_sha256'], 'status': status, 'failure_reason': failure,
            'sample_count': len(labels), 'correct_count': correct, 'metrics': metrics}
        validate(SCORE_SCHEMA, record)
        ref = self._store.append_record(SCORE_KIND, record)
        require(self._store.record_kind(ref) == SCORE_KIND and self._store.read_record(ref) == record,
                'Trusted score publication lost exact original custody')
        return dict(raw, trusted_scoring_ref=ref)


def scored_empirical_row(raw, score):
    """Consume a trusted score record without opening labels or trusting stdout metrics."""
    validate(SCORE_SCHEMA, score)
    original = {key: value for key, value in raw.items() if key != 'trusted_scoring_ref'}
    require(score['execution_identity_sha256'] == hashlib.sha256(json_bytes(original)).hexdigest()
            and score['prediction_ref'] == raw['stdout_ref'], 'Scored execution bytes or prediction identity differs')
    for key in ('job_id', 'contract_ref', 'invocation_id', 'sequence', 'role', 'repeat_index', 'seed', 'subject_ref'):
        require(score[key] == raw[key], 'Score proof differs from its original job identity')
    if score['status'] == 'scored':
        require(raw['exit_code'] == 0 and raw.get('termination_reason') == 'completed'
                and type(score['correct_count']) is int and 0 <= score['correct_count'] <= score['sample_count']
                and score['metrics'] == {'accuracy': score['correct_count'] / score['sample_count']}
                and score['failure_reason'] is None, 'Trusted score arithmetic or completion differs')
        return {'sequence': raw['sequence'], 'status': 'measured', 'metrics': dict(score['metrics']), 'unmeasured_metrics': {}}
    require(not score['metrics'] and score['correct_count'] is None and score['failure_reason'] is not None,
            'Unmeasured score must not claim an observation')
    reason = 'run_failed' if score['failure_reason'] == 'execution_failed' else 'metric_not_emitted'
    return {'sequence': raw['sequence'], 'status': 'unmeasured', 'metrics': {}, 'unmeasured_metrics': {'accuracy': reason}}


def failed_empirical_row(raw):
    require(raw['exit_code'] != 0 or raw.get('termination_reason') != 'completed',
            'A successful prediction job requires its trusted root scoring receipt')
    reason = {'timeout': 'timeout', 'deadline': 'timeout', 'resource_limit_exceeded': 'resource_limit_exceeded',
              'memory_limit': 'resource_limit_exceeded', 'cpu_limit': 'resource_limit_exceeded'}.get(
                  raw.get('termination_reason'), 'run_failed')
    return {'sequence': raw['sequence'], 'status': 'unmeasured', 'metrics': {}, 'unmeasured_metrics': {'accuracy': reason}}
