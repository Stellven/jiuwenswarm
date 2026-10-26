"""One versioned measurement vocabulary shared by prediction POC stages.

Metric names denote measurements, not arbitrary display labels. Never rename a
frozen Blueprint or reinterpret historical scores to make them fit a protocol.
"""
from __future__ import annotations

import copy
import json
from importlib.resources import files

from .contracts import ResearchError, contract_schema, validate

PROTOCOL_SCHEMA = 'urn:ai4r:metric-protocol:1.0.0'
PROTOCOL_FILE = 'metric-protocols/blind-classification-v1.json'


def metric_protocol(protocol=None):
    if protocol not in (None, 'ai4r-blind-classification:1', 'ai4r-cache-study:1'):
        raise ResearchError('metric_protocol_unsupported', 'Unknown registered metric protocol')
    source = 'metric-protocols/cache-study-v1.json' if protocol == 'ai4r-cache-study:1' else PROTOCOL_FILE
    value = json.loads(files('jiuwenswarm.research_contracts').joinpath(source).read_text('utf-8'))
    validate(PROTOCOL_SCHEMA, value)
    ids = [row['metric_id'] for row in value['metrics']]
    score = contract_schema(value['scoring_schema'])['properties']['metrics']
    if len(ids) != len(set(ids)) or set(ids) != set(score['properties']):
        raise ResearchError('metric_protocol_invalid', 'Metric registry and trusted scoring schema disagree')
    for row in value['metrics']:
        if row['valid_min'] is not None and row['valid_max'] is not None and row['valid_min'] > row['valid_max']:
            raise ResearchError('metric_protocol_invalid', 'Metric bounds are reversed')
    return value


def validate_metric_ids(metric_ids, protocol=None):
    expected = [row['metric_id'] for row in metric_protocol(protocol)['metrics']]
    if list(metric_ids) != expected:
        raise ResearchError('metric_protocol_unsupported',
            'This execution protocol requires canonical metric IDs ' + repr(expected) +
            '; aliases and unsupported measurements cannot be substituted')


def validate_metric_declarations(metrics, protocol=None):
    """Check meaning as well as spelling, before any code generation/execution."""
    validate_metric_ids([row['metric_id'] for row in metrics], protocol)
    for actual, expected in zip(metrics, metric_protocol(protocol)['metrics']):
        for key, value in expected.items():
            if actual.get(key) != value:
                raise ResearchError('metric_contract_mismatch',
                    f"{expected['metric_id']}.{key} must equal the registered measurement contract")


def hypothesis_reply_schema(protocol=None):
    """Narrow the adopted Blueprint schema; do not invent a second field layout."""
    schema = contract_schema('hypothesis-blueprint')
    schema['properties'].pop('dependent_variables')
    schema['required'].remove('dependent_variables')
    definitions = []
    for metric in metric_protocol(protocol)['metrics']:
        definition = copy.deepcopy(schema['$defs']['MetricDeclaration'])
        for key, value in metric.items():
            definition['properties'][key] = {'const': value}
        definitions.append(definition)
    schema['properties']['metrics'] = {'type': 'array', 'prefixItems': definitions,
        'items': False, 'minItems': len(definitions), 'maxItems': len(definitions)}
    ids = [row['metric_id'] for row in metric_protocol(protocol)['metrics']]
    schema['$defs']['OutcomeRule']['properties']['metric_id'] = {'enum': ids}
    schema['properties']['outcome_rules']['minItems'] = len(ids)
    schema['properties']['outcome_rules']['maxItems'] = len(ids)
    return schema


def validate_empirical_metric_ids(row, protocol=None):
    expected = {metric['metric_id'] for metric in metric_protocol(protocol)['metrics']}
    measured, missing = set(row['metrics']), set(row['unmeasured_metrics'])
    if measured & missing or measured | missing != expected:
        raise ResearchError('metric_contract_mismatch', 'Empirical metric coverage differs from the registered protocol')


def protocol_for_resource(resource, read_blob):
    """Identify a closed captured public resource, never model-authored authority."""
    from .cache_protocol import parse_cache_dataset
    if type(resource) is not dict or type(resource.get('files')) is not list:
        return None
    selected = [row for row in resource['files'] if row.get('path') == 'data.json']
    if len(resource['files']) != 1 or len(selected) != 1:
        return None
    try:
        parse_cache_dataset(read_blob(selected[0]['artifact_ref']))
    except ResearchError:
        return None
    return 'ai4r-cache-study:1'
