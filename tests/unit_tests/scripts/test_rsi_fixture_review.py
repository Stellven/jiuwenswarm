"""Private owner-review packet projection; no review/worker/model authority."""
import copy
import hashlib
import importlib.util
import json
import contextlib
import io
from pathlib import Path
from unittest.mock import Mock

import pytest

SOURCE = Path(__file__).parents[3] / 'deploy/m1/rsi_fixture_review.py'
spec = importlib.util.spec_from_file_location('fixture_review_test', SOURCE)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def pin(name):
    return {'id': name, 'sha256': hashlib.sha256(name.encode()).hexdigest()}


def preparation():
    return {'parent_ref': pin('parent'), 'parent_declaration_ref': pin('declaration'),
            'origin_ref': pin('origin'), 'generator_ref': pin('generator'),
            'mutable_path': 'ranking_parent.txt', 'author': 'custodian-service',
            'private_seed': 'HIDDEN_SEED_DO_NOT_EXPORT', 'provenance': ['HIDDEN_PROVENANCE'],
            'prior_preparation_refs': [], 'children': [
                {'kind': kind, 'body_ref': pin('HIDDEN_CONTROL')} for kind in ['bad'] * 10 + ['good'] * 3],
            'partitions': {name: [{'input_ref': pin('HIDDEN_INPUT'), 'expected_ref': pin('HIDDEN_EXPECTED')}] * count
                for name, count in [('development', 12), ('hidden_loop', 20), ('hidden_final', 20), ('platform', 12)]}}


class Store:
    def __init__(self):
        self.writes = []

    def read(self, ref):
        assert ref == pin('generator')
        return Path(review.ranking.__file__).read_bytes()

    def put(self, value):
        self.writes.append(copy.deepcopy(value))
        return pin('packet')


def configure(monkeypatch):
    monkeypatch.setattr(review.ranking, 'require_custodian_store', lambda _: None)
    monkeypatch.setattr(review.ranking, '_read_preparation', lambda store, ref: preparation())
    monkeypatch.setattr(review.ranking, 'preparation_kind', lambda _: 'ranking-v1')


def test_packet_excludes_hidden_originals_and_contains_no_decisions(monkeypatch):
    configure(monkeypatch)
    store = Store()
    result = review.packet(store, pin('preparation'), [pin('preparation')])
    assert set(result) == {'status', 'packet_ref', 'review_completed', 'publication_performed'}
    assert result['review_completed'] is result['publication_performed'] is False
    packet = store.writes[0]
    assert packet['authority_granted'] is packet['hidden_originals_included'] is False
    assert 'HIDDEN_' not in json.dumps(packet)
    assert not any(key in packet for key in ['independent', 'provenance_approved', 'reviewer', 'evidence_refs'])
    assert packet['calibration_capture_inventory_repeat1'] == review.ranking.calibration_inventory(
        {'partitions': preparation()['partitions']}, 1)
    assert packet['controls'] == {'semantic_fault_sources': 10, 'preservation_sources': 3}


def test_unapproved_preparation_never_writes(monkeypatch):
    configure(monkeypatch)
    store = Store()
    with pytest.raises(ValueError):
        review.packet(store, pin('preparation'), [])
    assert store.writes == []


def test_wrong_identity_fails_before_any_record_write(monkeypatch):
    store = Store()
    def refuse(_):
        raise ValueError('wrong custodian')
    monkeypatch.setattr(review.ranking, 'require_custodian_store', refuse)
    with pytest.raises(ValueError, match='wrong custodian'):
        review.packet(store, pin('preparation'), [pin('preparation')])
    assert store.writes == []


def test_execute_approval_precedes_store_open(monkeypatch):
    monkeypatch.setattr(review.runtime, 'load_config', lambda: {'approved_preparation_refs': []})
    monkeypatch.setattr(review, 'RecordStore', lambda *a: pytest.fail('unapproved store access'))
    with pytest.raises(ValueError):
        review.execute(pin('preparation'))


def test_generation_rejects_unpinned_request_before_store(monkeypatch):
    monkeypatch.setattr(review.runtime, '_identity', lambda: None)
    monkeypatch.setattr(review.runtime, 'validate_private', lambda *a: None)
    monkeypatch.setattr(review, 'RecordStore', lambda *a: pytest.fail('unapproved store access'))
    config = {'record_root': review.PRIVATE_ROOT, 'source_capture_ref': pin('origin'),
              'request_ref': pin('foreign'), 'request': {'operation': 'prepare-ranking',
                  'parameters': {'origin_ref': pin('origin'), 'seed': None}}}
    with pytest.raises(ValueError):
        review.generate(config)


def test_review_requires_human_tty_before_private_access(monkeypatch):
    monkeypatch.setattr(review.sys, 'stdin', io.StringIO())
    monkeypatch.setattr(review, 'RecordStore', lambda *a: pytest.fail('no non-TTY private access'))
    with pytest.raises(ValueError, match='visible terminal'):
        review.human_review({}, {})


def human_environment(monkeypatch):
    configure(monkeypatch)
    store = Store()
    store.db = Mock()
    store.db.execute.return_value.fetchone.return_value = None
    store.close = lambda: None
    store.get = lambda ref: {'synthetic_private_original': True}
    store.read = lambda ref: b'synthetic original for unit test only'
    result = {'packet_ref': pin('packet'), 'preparation_ref': pin('preparation'), 'request_ref': pin('request')}
    authority = {'schema': 'ai4r-rsi-fixture-review-authority:1', **result, 'reviewer': 'synthetic-owner'}
    monkeypatch.setattr(review, 'require_tty', lambda: None)
    monkeypatch.setattr(review.runtime, '_private_root', lambda _: Path('/synthetic-private'))
    monkeypatch.setattr(review, 'RecordStore', lambda _: store)
    monkeypatch.setattr(review, 'generation_result', lambda *a: result)
    monkeypatch.setattr(review, 'packet', lambda *a: {'packet_ref': result['packet_ref']})
    return store, authority


def test_quit_does_not_fabricate_review(monkeypatch):
    store, authority = human_environment(monkeypatch)
    monkeypatch.setattr('builtins.input', lambda _: 'quit')
    with contextlib.redirect_stdout(io.StringIO()):
        result = review.human_review({'record_root': review.PRIVATE_ROOT}, authority)
    assert result['status'] == 'REVIEW_NOT_CAPTURED'
    assert store.writes == []


def test_positive_answers_without_original_inspection_do_not_record_review(monkeypatch):
    store, authority = human_environment(monkeypatch)
    answers = iter(['decide', 'yes', 'yes', 'yes', 'yes', 'quit'])
    monkeypatch.setattr('builtins.input', lambda _: next(answers))
    with contextlib.redirect_stdout(io.StringIO()):
        result = review.human_review({'record_root': review.PRIVATE_ROOT}, authority)
    assert result['status'] == 'REVIEW_NOT_CAPTURED'
    assert store.writes == []


def test_explicit_synthetic_human_rejection_is_bound_to_packet_and_evidence(monkeypatch):
    store, authority = human_environment(monkeypatch)
    answers = iter(['decide', 'no', 'no', 'no', 'no', 'Cannot establish independence',
                    'Synthetic unit-test rejection; no real review', 'synthetic-owner',
                    'CAPTURE REVIEW ' + authority['packet_ref']['sha256']])
    monkeypatch.setattr('builtins.input', lambda _: next(answers))
    with contextlib.redirect_stdout(io.StringIO()):
        result = review.human_review({'record_root': review.PRIVATE_ROOT}, authority)
    assert result['status'] == 'HUMAN_REVIEW_CAPTURED'
    evidence, decision = store.writes[-2:]
    assert evidence['packet_ref'] == authority['packet_ref']
    assert evidence['inspected_sections'] == []
    assert decision['preparation_ref'] == authority['preparation_ref']
    assert decision['independent'] is decision['provenance_approved'] is False
    assert decision['evidence_refs']


def synthetic_chat_reply():
    quotes = {'provenance_approved': 'provenance yes', 'overlap_inventory_complete': 'overlap yes',
              'development_disclosure_approved': 'disclosure no', 'independent': 'independence no'}
    text = 'Synthetic unit test only. ' + '; '.join(quotes.values()) + '. Cannot establish independence. Reject synthetic fixture.'
    source = lambda quote: {'message_id': 'synthetic-user-reply', 'question_id': 'synthetic-question', 'quote': quote}
    return {'schema': 'ai4r-rsi-fixture-review-owner-reply:1', 'channel': 'authenticated_chat',
            'packet_ref': pin('packet'), 'preparation_ref': pin('preparation'), 'request_ref': pin('request'),
            'reviewer': 'synthetic-owner',
            'questions': [{'id': 'synthetic-question', 'text': 'Synthetic test: explicit review choices and rationale?'}],
            'human_messages': [{'id': 'synthetic-user-reply', 'role': 'user',
                                'question_ids': ['synthetic-question'], 'text': text}],
            'decisions': dict(zip(review.DECISION_FIELDS, [True, True, False, False])),
            'decision_sources': {key: source(quote) for key, quote in quotes.items()},
            'independence_reason': 'Cannot establish independence',
            'independence_source': source('Cannot establish independence'),
            'owner_findings': 'Reject synthetic fixture', 'findings_source': source('Reject synthetic fixture')}


@pytest.mark.parametrize('change', ['missing-decision', 'non-boolean', 'non-user', 'invented-reason', 'missing-reason', 'foreign-question'])
def test_chat_requires_every_explicit_fact_and_verbatim_user_source(change):
    value = synthetic_chat_reply()
    if change == 'missing-decision':
        value['decisions'].pop('independent')
    elif change == 'non-boolean':
        value['decisions']['independent'] = 1
    elif change == 'non-user':
        value['human_messages'][0]['role'] = 'assistant'
    elif change == 'invented-reason':
        value['independence_reason'] = 'Agent invented rationale'
        value['independence_source']['quote'] = value['independence_reason']
    elif change == 'missing-reason':
        value['independence_reason'] = ''
        value['independence_source']['quote'] = ''
    else:
        value['independence_source']['question_id'] = 'unknown-question'
    with pytest.raises(ValueError):
        review.validate_owner_reply(value)


def test_authentic_chat_capture_is_private_no_tty_claim_and_does_not_duplicate_or_overwrite(tmp_path, monkeypatch):
    reply = synthetic_chat_reply()
    authority = {key: reply[key] for key in ('packet_ref', 'preparation_ref', 'request_ref', 'reviewer')}
    authority['schema'] = 'ai4r-rsi-fixture-review-authority:1'
    result = {key: reply[key] for key in ('packet_ref', 'preparation_ref', 'request_ref')}
    configure(monkeypatch)
    monkeypatch.setattr(review.runtime, '_identity', lambda: None)
    monkeypatch.setattr(review.runtime, '_private_root', lambda _: tmp_path)
    monkeypatch.setattr(review, 'generation_result', lambda *a: result)
    monkeypatch.setattr(review, 'packet', lambda *a: {'packet_ref': reply['packet_ref']})
    config = {'record_root': review.PRIVATE_ROOT}
    first = review.capture_owner_reply(config, authority, reply)
    assert set(first) == {'status', 'packet_ref', 'review_ref', 'publication_performed'}
    assert first['publication_performed'] is False
    second = review.capture_owner_reply(config, authority, reply)
    assert second['review_ref'] == first['review_ref']
    assert second['status'] == 'HUMAN_REVIEW_ALREADY_CAPTURED'
    store = review.RecordStore(tmp_path)
    try:
        decision = store.get(first['review_ref'])
        evidence = store.get(decision['evidence_refs'][0])
        assert evidence['channel'] == 'authenticated_chat'
        assert evidence['inspected_sections'] == []
        assert evidence['owner_findings'] == reply['owner_findings']
        assert store.get(evidence['owner_reply_ref']) == reply
        assert store.db.execute("SELECT count(*) FROM jobs WHERE state='reviewed'").fetchone()[0] == 1
    finally:
        store.close()
    changed = copy.deepcopy(reply)
    changed['decisions']['independent'] = True
    with pytest.raises(ValueError):
        review.capture_owner_reply(config, authority, changed)
    store = review.RecordStore(tmp_path)
    try:
        assert store.get(first['review_ref']) == decision
    finally:
        store.close()


def test_chat_packet_or_reviewer_substitution_refused_before_store(monkeypatch):
    reply = synthetic_chat_reply()
    authority = {key: reply[key] for key in ('packet_ref', 'preparation_ref', 'request_ref', 'reviewer')}
    authority['reviewer'] = 'different-owner'
    monkeypatch.setattr(review.runtime, '_identity', lambda: None)
    monkeypatch.setattr(review, 'RecordStore', lambda *a: pytest.fail('mismatched owner must not open store'))
    with pytest.raises(ValueError):
        review.capture_owner_reply({}, authority, reply)
