"""Finite root-authenticated receipt publication on the actual core Store.

The owning NativePorts instance installs this callback. It exposes neither a
general writer nor a caller-selected Store/runtime/method. Existing receipts
may be read back without starting work, claiming budget or renewing time.
"""
from __future__ import annotations

import copy
import hashlib
import time

from .contracts import ResearchError,validate
from .state import json_bytes


SCHEMAS={'scientific-attempt-preflight':'urn:ai4r:private:scientific-attempt-preflight:1',
         'scientific-attempt-activation':'urn:ai4r:private:scientific-attempt-activation:1'}


def _require(ok,detail):
    if not ok:raise ResearchError('scientific_receipt_custody',detail)


def publish_scientific_start_receipt(runner,kind,record,preparation_ref):
    from .runner import CapsuleRunner
    from .state import SQLiteRunStore
    from .invocation_start import validate_invocation_preparation
    _require(type(runner) is CapsuleRunner and type(runner.store) is SQLiteRunStore,
             'Only the actual installed core Runner/Store publishes start receipts')
    _require(kind in SCHEMAS and type(record) is dict,'Only the two closed scientific start receipts are accepted')
    validate('Ref',preparation_ref);validate(SCHEMAS[kind],record)
    raw=json_bytes(record)
    _require(len(raw)<=65536,'Scientific start receipt exceeds the finite custody bound')
    store=runner.store
    with store._lock:
        _require(store.record_kind(preparation_ref)=='invocation-preparation','Original preparation has another indexed kind')
        prepared=store.read_record(preparation_ref)
        validate('urn:ai4r:private:invocation-preparation:1',prepared)
        if kind=='scientific-attempt-preflight':
            _require(record['preparation_ref']==preparation_ref,'Preflight targets another original preparation')
            runtime=record['science_runtime_ref']
            _require(store.record_kind(runtime)=='science-runtime','Scientific runtime has another indexed kind')
            from .science_runtime import decode_science_runtime_record
            decode_science_runtime_record(store.read_record(runtime))
        else:
            preflight_ref=record['preflight_ref']
            _require(store.record_kind(preflight_ref)=='scientific-attempt-preflight','Activation has no original indexed preflight')
            preflight=store.read_record(preflight_ref)
            validate(SCHEMAS['scientific-attempt-preflight'],preflight)
            _require(preflight['preparation_ref']==preparation_ref
                     and preflight['broker_instance_id']==record['broker_instance_id']
                     and preflight['recorded_unix_ns']<=record['recorded_unix_ns'],
                     'Activation/preflight/preparation/broker chronology differs')
        _require(prepared['recorded_unix_ns']<=record['recorded_unix_ns']<=prepared['deadline_unix_ns'],
                 'Start receipt is outside the immutable original preparation allowance')
        expected={'id':record['id'],'sha256':hashlib.sha256(raw).hexdigest()}
        try:
            existing=store.record_ref(record['id'])
        except ResearchError as error:
            if error.code!='evidence_unavailable':raise
            existing=None
        if existing is not None:
            _require(existing==expected and store.record_kind(existing)==kind
                     and store.read_blob(existing)==raw,'Original receipt ID already has different bytes/kind')
            return copy.deepcopy(existing)  # read-only ambiguous-response reconciliation
        binding={key:copy.deepcopy(prepared[key]) for key in ('contract_ref','invocation_id','execution_id')}
        response=runner.authorize_executor_preparation(binding)
        validate_invocation_preparation(store,preparation_ref,response)
        _require(record['recorded_unix_ns']<=time.time_ns()<=prepared['deadline_unix_ns'],
                 'Scientific receipt publication is expired or future-dated')
        original=store.append_record(kind,copy.deepcopy(record))
        _require(original==expected and store.record_kind(original)==kind and store.read_blob(original)==raw,
                 'Scientific receipt did not retain its original indexed exact bytes')
        return original
