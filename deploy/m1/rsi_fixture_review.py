"""Custodian-private fixture-review packet, never a review decision or export.

Run as Linux UID12002 with the fixed root-owned preparation-service config.
Generation/packets grant no review decision. The separate review command needs
an uncaptured human TTY and exact root-pinned reviewer/packet authority. No model,
worker, signer, admission, calibration, or publication operation is available.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
from datetime import datetime, timezone

from jiuwenswarm.research_rsi import preparation_runtime as runtime
from jiuwenswarm.research_rsi.records import RecordStore, encoded
from jiuwenswarm.research_rsi.targets import ranking_preparation as ranking

SOURCE_CONFIG = Path('/run/ai4r-rsi/fixture-review-source.json')
REVIEW_AUTHORITY = Path('/run/ai4r-rsi/fixture-review-authority.json')
OWNER_REPLY = Path('/run/ai4r-rsi/fixture-review-owner-reply.json')
PRIVATE_ROOT = '/var/lib/ai4r-rsi-fixture-review'
DECISION_FIELDS = ('provenance_approved', 'overlap_inventory_complete', 'development_disclosure_approved', 'independent')


def owner_reply():
    """Root is the trusted publisher of authentic user-role chat originals."""
    value = protected_json(OWNER_REPLY)
    validate_owner_reply(value)
    return value


def validate_owner_reply(value):
    fields = {'schema', 'channel', 'packet_ref', 'preparation_ref', 'request_ref', 'reviewer',
              'questions', 'human_messages', 'decisions', 'decision_sources',
              'independence_reason', 'independence_source', 'owner_findings', 'findings_source'}
    runtime._need(isinstance(value, dict) and set(value) == fields
                  and value['schema'] == 'ai4r-rsi-fixture-review-owner-reply:1'
                  and value['channel'] == 'authenticated_chat'
                  and isinstance(value['reviewer'], str) and 0 < len(value['reviewer']) <= 128)
    for name in ('packet_ref', 'preparation_ref', 'request_ref'):
        runtime.ref(value[name])
    questions = value['questions']
    messages = value['human_messages']
    runtime._need(isinstance(questions, list) and 1 <= len(questions) <= 16
                  and isinstance(messages, list) and 1 <= len(messages) <= 16)
    def identity(text):
        return isinstance(text, str) and 0 < len(text) <= 256 and not any(ord(c) < 32 for c in text)
    question_map = {}
    for question in questions:
        runtime._need(isinstance(question, dict) and set(question) == {'id', 'text'}
                      and identity(question['id']) and question['id'] not in question_map
                      and isinstance(question['text'], str) and 0 < len(question['text']) <= 32768)
        question_map[question['id']] = question
    message_map = {}
    for message in messages:
        runtime._need(isinstance(message, dict) and set(message) == {'id', 'role', 'question_ids', 'text'}
                      and identity(message['id']) and message['id'] not in message_map and message['role'] == 'user'
                      and isinstance(message['text'], str) and 0 < len(message['text']) <= 32768
                      and isinstance(message['question_ids'], list) and message['question_ids']
                      and all(identity(item) and item in question_map for item in message['question_ids'])
                      and len(set(message['question_ids'])) == len(message['question_ids']))
        message_map[message['id']] = message
    def source(source):
        runtime._need(isinstance(source, dict) and set(source) == {'message_id', 'question_id', 'quote'}
                      and identity(source['message_id']) and source['message_id'] in message_map
                      and identity(source['question_id']) and source['question_id'] in question_map)
        message = message_map[source['message_id']]
        runtime._need(source['question_id'] in message['question_ids'] and isinstance(source['quote'], str)
                      and source['quote'].strip() and len(source['quote']) <= 8192
                      and source['quote'] in message['text'])
    runtime._need(isinstance(value['decisions'], dict) and set(value['decisions']) == set(DECISION_FIELDS)
                  and all(type(item) is bool for item in value['decisions'].values())
                  and isinstance(value['decision_sources'], dict) and set(value['decision_sources']) == set(DECISION_FIELDS))
    for item in value['decision_sources'].values():
        source(item)
    for name, evidence in [('independence_reason', 'independence_source'), ('owner_findings', 'findings_source')]:
        source(value[evidence])
        runtime._need(isinstance(value[name], str) and value[name].strip()
                      and value[name] == value[evidence]['quote'])
    # Semantic attribution is the independent Root publisher's responsibility.
    # This code supplies no interpretation, inferred approvals, or default facts.


def capture_owner_reply(config, authority, reply):
    """Capture explicit authentic chat facts; never claim a TTY inspection."""
    runtime._identity()
    validate_owner_reply(reply)
    runtime._need(all(reply[key] == authority[key] for key in ('packet_ref', 'preparation_ref', 'request_ref', 'reviewer')))
    root = runtime._private_root(config['record_root'])
    store = RecordStore(root)
    try:
        ranking.require_custodian_store(store)
        result = generation_result(store, config)
        runtime._need(all(result[key] == authority[key] for key in ('packet_ref', 'preparation_ref', 'request_ref')))
        prep = ranking._read_preparation(store, result['preparation_ref'])
        actual = packet(store, result['preparation_ref'], [result['preparation_ref']])
        runtime._need(actual['packet_ref'] == authority['packet_ref'] and authority['reviewer'] != prep['author'])
        review_id = 'fixture-review:' + result['packet_ref']['sha256']
        with store.lock:
            store.db.execute('BEGIN IMMEDIATE')
            try:
                old = store.db.execute('SELECT ref,state FROM jobs WHERE id=?', (review_id,)).fetchone()
                if old is not None:
                    runtime._need(old[1] == 'reviewed')
                    old_ref = json.loads(old[0])
                    prior = store.get(old_ref)
                    runtime.validate_private(ranking.REVIEW_SCHEMA, prior)
                    runtime._need(prior['preparation_ref'] == reply['preparation_ref']
                                  and prior['reviewer'] == reply['reviewer']
                                  and all(prior[key] == reply['decisions'][key] for key in DECISION_FIELDS)
                                  and prior['independence_reason'] == reply['independence_reason']
                                  and len(prior['evidence_refs']) == 1)
                    evidence = store.get(prior['evidence_refs'][0])
                    runtime._need(all(evidence[key] == reply[key] for key in ('packet_ref', 'preparation_ref', 'request_ref', 'reviewer', 'owner_findings')))
                    store.db.execute('COMMIT')
                    return {'status': 'HUMAN_REVIEW_ALREADY_CAPTURED', 'packet_ref': reply['packet_ref'],
                            'review_ref': old_ref, 'publication_performed': False}
                reply_ref = store.put(reply)
                authority_ref = store.put(authority)
                evidence = {'schema': 'ai4r-rsi-fixture-review-human-evidence:1',
                    'channel': 'authenticated_chat', 'packet_ref': reply['packet_ref'],
                    'preparation_ref': reply['preparation_ref'], 'request_ref': reply['request_ref'],
                    'reviewer': reply['reviewer'], 'recorded_at': datetime.now(timezone.utc).isoformat(),
                    'decisions': reply['decisions'], 'independence_reason': reply['independence_reason'],
                    'owner_findings': reply['owner_findings'], 'authority_record_ref': authority_ref,
                    'owner_reply_ref': reply_ref, 'inspected_sections': []}
                evidence_ref = store.put(evidence)
                decision = {'schema': 'ai4r-rsi-ranking-review:1', 'preparation_ref': reply['preparation_ref'],
                            'reviewer': reply['reviewer'], **reply['decisions'],
                            'independence_reason': reply['independence_reason'], 'evidence_refs': [evidence_ref]}
                runtime.validate_private(ranking.REVIEW_SCHEMA, decision)
                review_ref = store.put(decision)
                store.db.execute('INSERT INTO jobs(id,ref,state) VALUES(?,?,?)',
                                 (review_id, encoded(review_ref).decode(), 'reviewed'))
                store.db.execute('COMMIT')
                return {'status': 'HUMAN_REVIEW_CAPTURED', 'packet_ref': reply['packet_ref'],
                        'review_ref': review_ref, 'publication_performed': False}
            except BaseException:
                store.db.execute('ROLLBACK')
                raise
    finally:
        store.close()


def protected_json(path):
    runtime._identity()
    path = runtime._path(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        meta = os.fstat(descriptor)
        runtime._need(stat.S_ISREG(meta.st_mode) and (meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode)) == (0, 12002, 0o440)
                      and meta.st_nlink == 1 and 0 < meta.st_size <= 2 * 1024 * 1024)
        raw = os.read(descriptor, 2 * 1024 * 1024 + 1)
    finally:
        os.close(descriptor)
    return runtime._json(raw)


def source_config():
    value = protected_json(SOURCE_CONFIG)
    runtime._need(isinstance(value, dict) and set(value) == {'schema', 'record_root', 'source_capture_ref', 'request_ref', 'request', 'originals'}
                  and value['schema'] == 'ai4r-rsi-fixture-review-source:1' and value['record_root'] == PRIVATE_ROOT)
    return value


def review_authority():
    value = protected_json(REVIEW_AUTHORITY)
    runtime._need(isinstance(value, dict) and set(value) == {'schema', 'packet_ref', 'preparation_ref', 'request_ref', 'reviewer'}
                  and value['schema'] == 'ai4r-rsi-fixture-review-authority:1'
                  and isinstance(value['reviewer'], str) and 0 < len(value['reviewer']) <= 128)
    for key in ('packet_ref', 'preparation_ref', 'request_ref'):
        runtime.ref(value[key])
    return value


def generate(config):
    """Only root-pinned public source imports and unexecuted private fixtures."""
    runtime._identity()
    runtime._need(config['record_root'] == PRIVATE_ROOT)
    request = config['request']
    runtime.validate_private(runtime.REQUEST_SCHEMA, request)
    runtime._need(request['operation'] == 'prepare-ranking'
                  and request['parameters']['origin_ref'] == config['source_capture_ref']
                  and request['parameters']['seed'] is None)
    raw_request = encoded(request)
    runtime._need(config['request_ref'] == {'id': hashlib.sha256(raw_request).hexdigest() + '.json',
                                          'sha256': hashlib.sha256(raw_request).hexdigest()})
    parameters = request['parameters']
    expected_originals = [parameters['parent_ref'], parameters['parent_declaration_ref'], config['source_capture_ref']]
    runtime._need(isinstance(config['originals'], list) and len(config['originals']) == 3
                  and {encoded(row['ref']) for row in config['originals']} == {encoded(pin) for pin in expected_originals})
    root = runtime._private_root(config['record_root'])
    store = RecordStore(root)
    try:
        ranking.require_custodian_store(store)
        # A published source capture is an origin fact, not an admission/review.
        for row in config['originals']:
            runtime._need(set(row) == {'ref', 'bytes_base64'})
            store.put_ref(row['ref'], base64.b64decode(row['bytes_base64'], validate=True))
        origin = store.get(config['source_capture_ref'])
        runtime._need(origin.get('schema') == 'ai4r-rsi-bootstrap-source-capture:1'
                      and origin.get('status') == 'SOURCE_CAPTURED_NOT_READY'
                      and origin.get('screening_declaration_ref') == parameters['parent_declaration_ref']
                      and origin.get('screening_helper_ref') == parameters['parent_ref'])
        generator = Path(ranking.__file__).read_bytes()
        store.put_ref(parameters['generator_ref'], generator)
        runtime._need(store.put(request) == config['request_ref'])
        # Prevent a restart from silently renewing a hidden suite/seed.
        prior = store.db.execute("SELECT ref FROM jobs WHERE id='fixture-review-generation' AND state='prepared'").fetchone()
        if prior is not None:
            result = store.get(json.loads(prior[0]))
            runtime._need(result['request_ref'] == config['request_ref'])
            packet(store, result['preparation_ref'], [result['preparation_ref']])
            return result
        runtime._need(store.db.execute("SELECT 1 FROM jobs WHERE id='fixture-review-generation'").fetchone() is None)
        store.db.execute("INSERT INTO jobs(id,ref,state) VALUES('fixture-review-generation',?,'started')", (encoded(config['request_ref']).decode(),))
        pin = ranking.prepare_ranking(store, **parameters, declaration=store.get(parameters['parent_declaration_ref']))
        review_packet = packet(store, pin, [pin])
        result = {'status': 'PRIVATE_REVIEW_PACKET_PREPARED', 'request_ref': config['request_ref'],
                  'preparation_ref': pin, 'packet_ref': review_packet['packet_ref'],
                  'review_completed': False, 'publication_performed': False}
        result_ref = store.put(result)
        store.db.execute("UPDATE jobs SET ref=?,state='prepared' WHERE id='fixture-review-generation' AND state='started'",
                         (encoded(result_ref).decode(),))
        return result
    finally:
        store.close()

CHECKLIST = (
    {'id': 'owner_authority', 'requirement':
     'Authenticate the independent module owner separately; reviewer must differ from the preparation author. This packet grants no reviewer authority.'},
    {'id': 'real_parent', 'requirement':
     'Review the exact production Screening declaration and mutable ranking body, declared RSI permission, scoring contract, origin and generator originals. Parent admission remains a separate live library gate.'},
    {'id': 'oracle_semantics', 'requirement':
     'Privately inspect input and expected-output originals in all four partitions. Check eligibility, three score dimensions, descending total, lexical tie order, one-based ranks and selected first eligible idea. Never send hidden originals to a model or controller.'},
    {'id': 'historical_inventory', 'requirement':
     'Reconcile every prior registration, including retired and disclosed suites, against the nominated lineage and operator inventory. Automated disjointness over nominated records does not prove the historical inventory complete.'},
    {'id': 'independence', 'requirement':
     'Assess sampling units, shared generator assumptions, patterned coverage, correlations and suitability for the intended statistical test. Per-unit pseudorandom seeds and no duplicate hashes do not establish independence. Record the actual rationale and reject unsupported independence.'},
    {'id': 'controls', 'requirement':
     'Privately review the ten semantic-fault and three preservation source controls against the exact parent. They are unexecuted sources, not evidence of detection, headroom or speed.'},
    {'id': 'disclosure', 'requirement':
     'Decide development-only disclosure separately. Do not disclose hidden inputs, expected outputs, seed, provenance, controls, review evidence or fixture manifests to the controller/model.'},
    {'id': 'authentic_evidence', 'requirement':
     'Author actual review evidence under authenticated owner authority. Custodian may then capture rsi-ranking-review:1 with explicit decisions, independence reason and evidence_refs. This packet creates none of those decisions.'},
)


def packet(store, preparation_ref, approved_preparation_refs):
    ranking.require_custodian_store(store)
    runtime._approved(preparation_ref, approved_preparation_refs)
    prep = ranking._read_preparation(store, preparation_ref)
    if ranking.preparation_kind(prep) != 'ranking-v1':
        raise ValueError('This finite review packet requires the actual Screening ranking preparation')
    if store.read(prep['generator_ref']) != Path(ranking.__file__).read_bytes():
        raise ValueError('Prepared generator does not match the installed reviewed source')
    prior = []
    for pin in prep['prior_preparation_refs']:
        # Exact nominated lineage only, never a recursive Ref or directory walk.
        historical = store.get(pin)
        if ranking.preparation_kind(historical) != 'ranking-v1':
            raise ValueError('Historical fixture target differs')
        prior.append({'preparation_ref': pin,
                      'partition_counts': {name: len(historical['partitions'][name]) for name in ranking.PARTITIONS}})
    counts = {name: len(prep['partitions'][name]) for name in ranking.PARTITIONS}
    # Only population lengths enter the inventory formula; no hidden originals
    # or per-case identities enter this metadata projection.
    inventory = ranking.calibration_inventory({'partitions': prep['partitions']}, 1)
    value = {
        'schema': 'ai4r-rsi-fixture-review-packet:1',
        'status': 'INDEPENDENT_OWNER_REVIEW_REQUIRED',
        'preparation_ref': preparation_ref,
        'parent_ref': prep['parent_ref'],
        'parent_declaration_ref': prep['parent_declaration_ref'],
        'origin_ref': prep['origin_ref'],
        'generator_ref': prep['generator_ref'],
        'target_kind': 'ranking-v1',
        'mutable_path': prep['mutable_path'],
        'preparation_author': prep['author'],
        'partition_counts': counts,
        'nominated_prior_inventory': prior,
        'controls': {'semantic_fault_sources': sum(row['kind'] == 'bad' for row in prep['children']),
                     'preservation_sources': sum(row['kind'] == 'good' for row in prep['children'])},
        'source_reconciliation': 'Original input/oracle bytes, within-nominated-lineage overlap, source controls and split identities reconciled; no execution or independence finding',
        'calibration_capture_inventory_repeat1': inventory,
        'review_contract': ranking.REVIEW_SCHEMA,
        'checklist': list(CHECKLIST),
        'remaining_gates': [
            'Authenticated independent owner review with original evidence',
            'Explicit root-approved plan and current draft security qualification before calibration timing effects',
            'Actual bounded worker calibration, reviewed raw captures, noise and measurable headroom',
            'Verified signed calibration and frozen target; final current qualification before session',
            'Exact live admitted parent, separately approved budgets/job, actual doctor readiness and human session start',
        ],
        'authority_granted': False,
        'hidden_originals_included': False,
    }
    # Persist only inside the already validated UID12002/private RecordStore.
    # The stdout result is one opaque Ref, not a review or fixture payload.
    pin = store.put(value)
    return {'status': 'PRIVATE_REVIEW_PACKET_PREPARED', 'packet_ref': pin,
            'review_completed': False, 'publication_performed': False}


def execute(preparation_ref):
    config = runtime.load_config()
    runtime._approved(preparation_ref, config['approved_preparation_refs'])
    root = runtime._private_root(config['record_root'])
    store = RecordStore(root)
    try:
        ranking.require_custodian_store(store)
        return packet(store, preparation_ref, config['approved_preparation_refs'])
    finally:
        store.close()


def generation_result(store, config):
    row = store.db.execute("SELECT ref FROM jobs WHERE id='fixture-review-generation' AND state='prepared'").fetchone()
    runtime._need(row is not None)
    result = store.get(json.loads(row[0]))
    runtime._need(result['request_ref'] == config['request_ref'])
    return result


def summary(config):
    """Finite poll output. Never includes private fixtures or human evidence."""
    root = runtime._private_root(config['record_root'])
    store = RecordStore(root)
    try:
        ranking.require_custodian_store(store)
        result = generation_result(store, config)
        review_id = 'fixture-review:' + result['packet_ref']['sha256']
        row = store.db.execute('SELECT ref FROM jobs WHERE id=? AND state=?', (review_id, 'reviewed')).fetchone()
        return {'status': 'HUMAN_REVIEW_CAPTURED' if row else 'HUMAN_REVIEW_REQUIRED',
                'packet_ref': result['packet_ref'], 'preparation_ref': result['preparation_ref'],
                'review_ref': json.loads(row[0]) if row else None,
                'publication_performed': False}
    finally:
        store.close()


def require_tty():
    if not all(stream.isatty() for stream in (sys.stdin, sys.stdout, sys.stderr)):
        raise ValueError('Human fixture review requires an uncaptured visible terminal')


def human_review(config, authority):
    """Only actual TTY answers create a review, bound to this concrete packet."""
    require_tty()
    root = runtime._private_root(config['record_root'])
    store = RecordStore(root)
    try:
        ranking.require_custodian_store(store)
        result = generation_result(store, config)
        runtime._need(all(authority[key] == result[key] for key in ('packet_ref', 'preparation_ref', 'request_ref')))
        prep = ranking._read_preparation(store, result['preparation_ref'])
        actual = packet(store, result['preparation_ref'], [result['preparation_ref']])
        runtime._need(actual['packet_ref'] == authority['packet_ref'] and authority['reviewer'] != prep['author'])
        review_id = 'fixture-review:' + result['packet_ref']['sha256']
        runtime._need(store.db.execute('SELECT 1 FROM jobs WHERE id=?', (review_id,)).fetchone() is None)
        inspected = []
        print('HUMAN-ONLY PRIVATE FIXTURE REVIEW. Do not capture, share, or send terminal contents to a model.')
        print('This operation records your actual decisions; it grants no calibration, admission or qualification.')
        print('Reviewer:', authority['reviewer'], '\nPacket SHA256:', authority['packet_ref']['sha256'])
        print('Sections: summary, parent, generator, fixtures, lineage, controls. Then decide or quit.')
        while True:
            command = input('review> ').strip()
            if command == 'quit':
                return {'status': 'REVIEW_NOT_CAPTURED', 'packet_ref': authority['packet_ref']}
            if command == 'summary':
                print(json.dumps(store.get(result['packet_ref']), indent=2))
            elif command == 'parent':
                for key in ('parent_declaration_ref', 'parent_ref', 'origin_ref'):
                    print('\n---', key, '---\n', store.read(prep[key]).decode('utf8'))
                inspected.append(command)
            elif command == 'generator':
                print(store.read(prep['generator_ref']).decode('utf8'))
                inspected.append(command)
            elif command == 'fixtures':
                for name in ranking.PARTITIONS:
                    print('\nPRIVATE PARTITION:', name)
                    for row in prep['partitions'][name]:
                        print(json.dumps({'case_id': row['id'], 'input': store.get(row['input_ref']),
                                          'expected': store.get(row['expected_ref'])}, ensure_ascii=False))
                inspected.append(command)
            elif command == 'lineage':
                print(json.dumps({'current_provenance': prep['provenance'],
                                  'nominated_prior_refs': prep['prior_preparation_refs']}, indent=2))
                for pin in prep['prior_preparation_refs']:
                    prior = store.get(pin)
                    print(json.dumps({'preparation_ref': pin, 'provenance': prior['provenance']}, indent=2))
                print('Completeness beyond this nominated inventory requires your independent operator reconciliation.')
                inspected.append(command)
            elif command == 'controls':
                for row in prep['children']:
                    print('\nPRIVATE CONTROL:', row['id'], row['kind'])
                    print(store.read(row['body_ref']).decode('utf8'))
                inspected.append(command)
            elif command == 'decide':
                answers = {}
                for key in ('provenance_approved', 'overlap_inventory_complete', 'development_disclosure_approved', 'independent'):
                    while True:
                        answer = input(key + ' [type yes or no; no default]: ').strip()
                        if answer in {'yes', 'no'}:
                            answers[key] = answer == 'yes'
                            break
                if any(answers.values()) and not {'parent', 'generator', 'fixtures', 'lineage', 'controls'} <= set(inspected):
                    print('Positive decisions require privately inspecting each listed section first. No review recorded.')
                    continue
                reason = input('Your actual independence assessment and rationale (required): ').strip()
                notes = input('Your actual provenance/overlap/disclosure findings and evidence notes (required): ').strip()
                if not reason or not notes or max(len(reason), len(notes)) > 8192:
                    print('Nonempty bounded human findings are required. No review recorded.')
                    continue
                if input('Type your authorized reviewer ID exactly: ').strip() != authority['reviewer']:
                    print('Reviewer identity differs. No review recorded.')
                    continue
                confirmation = 'CAPTURE REVIEW ' + authority['packet_ref']['sha256']
                if input('Type exactly ' + confirmation + ': ').strip() != confirmation:
                    print('No review recorded.')
                    continue
                evidence = {'schema': 'ai4r-rsi-fixture-review-human-evidence:1',
                    'packet_ref': authority['packet_ref'], 'preparation_ref': authority['preparation_ref'],
                    'request_ref': authority['request_ref'], 'reviewer': authority['reviewer'],
                    'recorded_at': datetime.now(timezone.utc).isoformat(), 'inspected_sections': inspected,
                    'decisions': answers, 'independence_reason': reason, 'owner_findings': notes,
                    'authority_record_ref': {'id': hashlib.sha256(encoded(authority)).hexdigest() + '.json',
                                             'sha256': hashlib.sha256(encoded(authority)).hexdigest()}}
                store.put(authority)
                evidence_ref = store.put(evidence)
                decision = {'schema': 'ai4r-rsi-ranking-review:1', 'preparation_ref': authority['preparation_ref'],
                            'reviewer': authority['reviewer'], **answers, 'independence_reason': reason,
                            'evidence_refs': [evidence_ref]}
                runtime.validate_private(ranking.REVIEW_SCHEMA, decision)
                review_ref = store.put(decision)
                store.db.execute('INSERT INTO jobs(id,ref,state) VALUES(?,?,?)',
                                 (review_id, encoded(review_ref).decode(), 'reviewed'))
                return {'status': 'HUMAN_REVIEW_CAPTURED', 'packet_ref': authority['packet_ref'],
                        'review_ref': review_ref, 'publication_performed': False}
            else:
                print('Choose a listed section, decide, or quit. No commands are executed.')
    finally:
        store.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    sub = parser.add_subparsers(dest='operation', required=True)
    sub.add_parser('generate', allow_abbrev=False)
    sub.add_parser('summary', allow_abbrev=False)
    sub.add_parser('review', allow_abbrev=False)
    sub.add_parser('capture-owner-reply', allow_abbrev=False)
    existing = sub.add_parser('packet', allow_abbrev=False)
    existing.add_argument('--preparation-ref', required=True,
                        help='Exact root-approved private preparation Ref as JSON; no store/output path is selectable')
    args = parser.parse_args(argv)
    try:
        if args.operation == 'packet':
            value = execute(runtime._json(args.preparation_ref.encode('utf8')))
        elif args.operation == 'generate':
            value = generate(source_config())
        elif args.operation == 'summary':
            value = summary(source_config())
        elif args.operation == 'capture-owner-reply':
            value = capture_owner_reply(source_config(), review_authority(), owner_reply())
        else:
            require_tty()
            value = human_review(source_config(), review_authority())
    except (ValueError, KeyError, TypeError, OSError, AttributeError, RecursionError, sqlite3.Error, EOFError):
        print(json.dumps({'status': 'BLOCKED', 'reason': 'Custodian identity, protected config, approved preparation or original reconciliation is unavailable'}))
        return 2
    print(encoded(value).decode('utf8'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
