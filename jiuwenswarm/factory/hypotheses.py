"""Persist bounded agent-authored research hypotheses linked to scoped evidence.

Proposals are unverified reasoning, never measurements, admission or authority.
Citation URLs are retained as text and are never fetched by this module.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sqlite3
from urllib.parse import urlsplit

from .store import NotFound, encoded

VERSION = '1.0.0'
FIELDS = {'mechanism', 'applicability', 'evidence_ids', 'primary_source_urls',
          'changed_variable', 'prediction', 'required_counters', 'falsification',
          'correctness_obligations'}
MAX_BYTES = 32768


def _object(value, keys, name):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(name + ' has invalid or missing fields')


def _text(value, name, maximum=2000):
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(ord(c) < 32 and c not in '\n\t' for c in value)):
        raise ValueError(name + ' must be bounded nonempty text')


def _texts(value, name, maximum=20, item_length=1000):
    if not isinstance(value, list) or not 1 <= len(value) <= maximum:
        raise ValueError(name + ' must be a bounded nonempty list')
    for item in value:
        _text(item, name, item_length)
    if len(set(value)) != len(value):
        raise ValueError(name + ' must contain unique entries')


def validate(hypothesis_id, hypothesis):
    if not isinstance(hypothesis_id, str) or not re.fullmatch('[a-z][a-z0-9_-]{0,63}', hypothesis_id):
        raise ValueError('hypothesis_id must be a stable lowercase slug of at most 64 characters')
    _object(hypothesis, FIELDS, 'hypothesis')
    for field in ('mechanism', 'prediction', 'falsification'):
        _text(hypothesis[field], field)
    application = hypothesis['applicability']
    _object(application, {'hardware', 'model', 'source_revision', 'limits'}, 'applicability')
    for field, value in application.items():
        _text(value, 'applicability.' + field, 1000)
    variable = hypothesis['changed_variable']
    _object(variable, {'name', 'baseline', 'candidate'}, 'changed_variable')
    for field, value in variable.items():
        _text(value, 'changed_variable.' + field, 1000)
    if variable['baseline'] == variable['candidate']:
        raise ValueError('changed_variable must declare distinct baseline and candidate values')
    _texts(hypothesis['evidence_ids'], 'evidence_ids', 20, 256)
    _texts(hypothesis['required_counters'], 'required_counters')
    _texts(hypothesis['correctness_obligations'], 'correctness_obligations')
    urls = hypothesis['primary_source_urls']
    if not isinstance(urls, list) or len(urls) > 10:
        raise ValueError('primary_source_urls must contain 0..10 citation URLs')
    if urls:
        _texts(urls, 'primary_source_urls', 10, 2048)
    for url in urls:
        try:
            parsed = urlsplit(url)
            if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
                    or parsed.password is not None or any(c.isspace() for c in url)):
                raise ValueError('Citations require credential-free HTTPS URLs')
        except ValueError as exc:
            raise ValueError('Invalid primary-source citation URL') from exc
    if len(encoded(hypothesis).encode('utf-8')) > MAX_BYTES:
        raise ValueError('Hypothesis exceeds 32 KiB bound')
    return copy.deepcopy(hypothesis)


def _evidence(store, task_id, ids):
    sources = []
    readable = set(getattr(store, 'readable', ()))
    readable = sorted(readable - {task_id})
    for identifier in ids:
        for source_task in [task_id, *readable]:
            try:
                record = store.read(source_task, identifier)
                break
            except NotFound:
                continue
        else:
            raise NotFound('Cited evidence not found in authorized tasks')
        if 'obs_id' not in record and 'artifact_id' not in record:
            raise ValueError('Cited evidence must be an observation or verified artifact')
        # Avoid copying reports/previews into the proposal. Snapshot only their
        # identity; artifact Store.read has already checked its content hash.
        identity = {k: v for k, v in record.items() if k != 'text_preview'}
        sources.append(dict(task_id=source_task, evidence_id=identifier,
            record_kind='observation' if 'obs_id' in record else 'artifact',
            record_sha256=hashlib.sha256(encoded(identity).encode('utf-8')).hexdigest()))
    return sources


def _existing(store, task_id, obs_id, digest):
    record = store.read(task_id, obs_id)
    if (record.get('kind') != 'hypothesis_proposal'
            or record.get('values', {}).get('hypothesis_sha256') != digest):
        raise ValueError('hypothesis_id already names a different immutable proposal')
    return {'proposal': record['values'], 'observation_id': obs_id, 'replayed': True}


def propose(store, task_id, hypothesis_id, hypothesis):
    hypothesis = validate(hypothesis_id, hypothesis)
    store.get_task(task_id)
    digest = hashlib.sha256(encoded(hypothesis).encode('utf-8')).hexdigest()
    obs_id = 'hypothesis-proposal-' + hypothesis_id
    try:
        return _existing(store, task_id, obs_id, digest)
    except NotFound:
        pass
    sources = _evidence(store, task_id, hypothesis['evidence_ids'])
    proposal = dict(schema_version=1, methodology_version=VERSION,
        hypothesis_id=hypothesis_id, hypothesis_sha256=digest, hypothesis=hypothesis,
        evidence_sources=sources, status='proposed_unmeasured', expected_benefit='unknown',
        citations_unverified=True, citations_fetched=False,
        primary_source_status='agent-supplied URLs; primary-source classification and claims not verified',
        evidence_role='retained scoped evidence cited by agent; causality and applicability remain hypotheses',
        maximum_changed_variables=1, execution_authorized=False, promotion_authorized=False,
        correctness_status='not_evaluated', performance_status='not_evaluated',
        authority='Observation persistence only; no jobs, grants, contract changes, acceptance or promotion.')
    try:
        store.append_observation(task_id, dict(obs_id=obs_id, kind='hypothesis_proposal',
            values=proposal, limitations='Agent-authored unmeasured proposal; citations unverified and never fetched; papers do not prove transfer to this hardware/model.'))
    except sqlite3.IntegrityError:
        # Concurrent identical callers converge on the same committed record.
        return _existing(store, task_id, obs_id, digest)
    return {'proposal': proposal, 'observation_id': obs_id, 'replayed': False}


def dispatch(store, task_id, operation, inputs):
    if operation != 'propose':
        raise ValueError('Unknown hypothesis capability')
    _object(inputs, {'hypothesis_id', 'hypothesis'}, 'inputs')
    return propose(store, task_id, inputs['hypothesis_id'], inputs['hypothesis'])
