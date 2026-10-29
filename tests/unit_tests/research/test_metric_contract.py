"""A spelling mismatch must stop before Builder, without changing its meaning."""
import copy
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.metric_contract import (
    hypothesis_reply_schema, metric_protocol, validate_metric_declarations,
    validate_empirical_metric_ids,
)


def declaration():
    return dict(metric_protocol()['metrics'][0], aggregation='median', target_id='target:user_accuracy')


def test_generation_schema_and_consumer_use_the_same_canonical_measurement():
    schema = hypothesis_reply_schema()
    metric_schema = schema['properties']['metrics']
    Draft202012Validator(metric_schema).validate([declaration()])
    validate_metric_declarations([declaration()])
    for field, value in [('metric_id', 'validation_accuracy'), ('unit', 'percent'),
                         ('measurement', 'Accuracy on the training data'), ('valid_max', 100)]:
        wrong = copy.deepcopy(declaration())
        wrong[field] = value
        assert not Draft202012Validator(metric_schema).is_valid([wrong])
        with pytest.raises(ResearchError):
            validate_metric_declarations([wrong])


def test_unsupported_measurement_is_not_renamed_to_accuracy():
    metric = declaration()
    metric['metric_id'] = 'f1_score'
    with pytest.raises(ResearchError) as error:
        validate_metric_declarations([metric])
    assert error.value.code == 'metric_protocol_unsupported'
    assert metric['metric_id'] == 'f1_score'


def test_measured_and_missing_rows_share_the_registered_metric_keys():
    validate_empirical_metric_ids({'metrics': {'accuracy': 0.8}, 'unmeasured_metrics': {}})
    validate_empirical_metric_ids({'metrics': {}, 'unmeasured_metrics': {'accuracy': 'timeout'}})
    for row in [{'metrics': {'validation_accuracy': 0.8}, 'unmeasured_metrics': {}},
                {'metrics': {}, 'unmeasured_metrics': {}},
                {'metrics': {'accuracy': 0.8}, 'unmeasured_metrics': {'accuracy': 'timeout'}}]:
        with pytest.raises(ResearchError):
            validate_empirical_metric_ids(row)


def test_hypothesis_uses_the_real_restricted_capsule_artifact_interface(tmp_path, monkeypatch):
    from jiuwenswarm.research.capsules import hypothesis
    from jiuwenswarm.research.runner import CapsuleArtifacts
    from jiuwenswarm.research.state import SQLiteRunStore

    fixture = Path(hypothesis.__file__).parents[1] / 'resources/calibration/hypothesis_blueprint.json'
    reply = json.loads(fixture.read_bytes())
    reply.pop('ext', None)
    reply.pop('dependent_variables')
    reply['metrics'] = [declaration()]
    reply['outcome_rules'] = [dict(reply['outcome_rules'][0], metric_id='accuracy')]

    async def answer(*args, **kwargs):
        errors = [(list(error.path), error.message) for error in
                  Draft202012Validator(kwargs['reply_schema']).iter_errors(reply)]
        assert not errors
        return reply

    monkeypatch.setattr(hypothesis, 'ask', answer)
    store = SQLiteRunStore(tmp_path)
    try:
        ctx = SimpleNamespace(store=CapsuleArtifacts(store, [], scope={'run_id': 'run:restricted'}),
            input_ref=lambda name: {'id': name, 'sha256': 'a' * 64})
        resource = {'availability': 'available', 'environment_ref': reply['environment_ref']}
        outputs = asyncio.run(hypothesis.execute(ctx,
            {'baseline_resource': resource, 'validation_resource': resource}))
        blueprint = json.loads(outputs['blueprint'].data)
        assert blueprint['dependent_variables'] == ['accuracy']
        assert not list(store.iter_records(run_id='run:restricted'))
    finally:
        store.close()
