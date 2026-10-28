"""Finite trusted helper registrations, deliberately outside the controller.

Only installed entries can select an entrypoint. Profiles cannot register code,
callbacks, module names or arbitrary commands through this registry.
"""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable

from .ranking import rank_opportunities
from .unrelated_helper import normalize_labels


@dataclass(frozen=True)
class HelperDescriptor:
    target_kind: str
    input_name: str
    entrypoint: str
    validate_inputs: Callable
    reference: Callable
    validate_visible_inputs: Callable


def _ranking_inputs(data):
    if (not isinstance(data, dict) or set(data) != {'scores'}
            or not isinstance(data['scores'], list) or len(data['scores']) > 3
            or any(not isinstance(row, dict) for row in data['scores'])):
        raise ValueError('Unknown legitimate ranking input')
    return data


def _label_inputs(data):
    if (not isinstance(data, dict) or set(data) != {'labels'}
            or not isinstance(data['labels'], list) or len(data['labels']) > 256
            or any(not isinstance(label, str) or len(label) > 256 for label in data['labels'])):
        raise ValueError('Unknown legitimate label input')
    return data


def _ranking_visible_inputs(data):
    """Approved visible helper projection; never executes the scoring oracle."""
    _ranking_inputs(data)
    if not data['scores']:
        raise ValueError('Visible ranking reproduction needs one to three scores')
    seen = set()
    fields = {'idea_id', 'novelty', 'feasibility', 'compute_alignment', 'eligible'}
    for row in data['scores']:
        if (set(row) != fields or not isinstance(row.get('idea_id'), str) or not row['idea_id']
                or row['idea_id'] in seen or type(row.get('eligible')) is not bool
                or any(type(row.get(key)) is not int or not 1 <= row[key] <= 5
                       for key in ('novelty', 'feasibility', 'compute_alignment'))):
            raise ValueError('Invalid visible ranking projection')
        seen.add(row['idea_id'])
    if not any(row['eligible'] for row in data['scores']):
        raise ValueError('Visible ranking reproduction needs an eligible score')
    return data


def _ranking_reference(data):
    _ranking_inputs(data)
    return rank_opportunities(data['scores'])


def _label_reference(data):
    _label_inputs(data)
    return normalize_labels(data['labels'])


_HELPERS = MappingProxyType({
    'ranking-v1': HelperDescriptor('ranking-v1', 'scores', 'rank_opportunities', _ranking_inputs, _ranking_reference, _ranking_visible_inputs),
    'normalize-labels-v1': HelperDescriptor('normalize-labels-v1', 'labels', 'normalize_labels', _label_inputs, _label_reference, _label_inputs),
})


def registered_helper(kind):
    if not isinstance(kind, str) or kind not in _HELPERS:
        raise ValueError('Unknown finite helper registration')
    return _HELPERS[kind]
