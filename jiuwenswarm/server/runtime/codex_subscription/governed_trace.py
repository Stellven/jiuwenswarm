"""Lossless, call-owned native packets in the protected evidence store."""
from __future__ import annotations

import copy
import re

from .transport import CodexError


SCOPE_FIELDS = frozenset({'run_id', 'node_id', 'subnode_id', 'attempt_id',
    'execution_id', 'invocation_id', 'call_id', 'contract_ref', 'model_call_start_ref'})


class GovernedTrace:
    def __init__(self, scope, append_record, put_blob):
        refs = {'contract_ref', 'model_call_start_ref'}
        if (not isinstance(scope, dict) or set(scope) != SCOPE_FIELDS
                or any(not isinstance(scope[key], str) or not scope[key] for key in SCOPE_FIELDS - refs)
                or any(not isinstance(scope[key], dict) or set(scope[key]) != {'id', 'sha256'}
                    or not isinstance(scope[key]['id'], str) or not scope[key]['id']
                    or not isinstance(scope[key]['sha256'], str)
                    or re.fullmatch('[0-9a-f]{64}', scope[key]['sha256']) is None for key in refs)
                or not callable(append_record) or not callable(put_blob)):
            raise CodexError('AUDIT_UNAVAILABLE')
        self.scope = copy.deepcopy(scope)
        self.append_record, self.put_blob = append_record, put_blob
        self.event_refs = []
        self.thread_id = None
        self.pending = []
        self.pending_bytes = 0

    def _capture(self, direction, raw, method):
        try:
            if direction not in {'in', 'out'} or not isinstance(raw, bytes):
                raise ValueError('Invalid packet')
            raw_ref = self.put_blob(raw)
            ref = self.append_record('native-governed-trace-event', {
                'schema': 'ai4r-native-governed-trace-event:1', 'scope': self.scope,
                'sequence': len(self.event_refs), 'direction': direction,
                'method': method, 'raw_ref': raw_ref})
            self.event_refs.append(ref)
        except Exception:
            raise CodexError('AUDIT_UNAVAILABLE') from None

    def request_observer(self, method):
        def observe(direction, raw, envelope):
            if method == 'thread/start' and direction == 'in':
                thread_id = ((envelope.get('result') or {}).get('thread') or {}).get('id')
                if isinstance(thread_id, str):
                    self.bind_thread(thread_id)
            self._capture(direction, raw, method)
        return observe

    def notification(self, direction, raw, envelope):
        params = envelope.get('params') or {}
        thread_id = params.get('threadId')
        if thread_id is None and envelope.get('method') == 'thread/started':
            thread_id = (params.get('thread') or {}).get('id')
        # Only call-owned thread packets are research evidence. Account/login
        # packets never enter this store, even when interleaved on native stdio.
        if not isinstance(thread_id, str):
            return
        if self.thread_id is None:
            if len(self.pending) >= 4096 or self.pending_bytes + len(raw) > 16 * 1024 * 1024:
                raise CodexError('AUDIT_UNAVAILABLE')
            self.pending.append((direction, raw, envelope))
            self.pending_bytes += len(raw)
        elif thread_id == self.thread_id:
            self._capture(direction, raw, envelope['method'])

    def bind_thread(self, thread_id):
        self.thread_id = thread_id
        pending, self.pending = self.pending, []
        self.pending_bytes = 0
        for direction, raw, envelope in pending:
            self.notification(direction, raw, envelope)

    def finish(self, status):
        try:
            return self.append_record('native-governed-trace', {
                'schema': 'ai4r-native-governed-trace:1', 'scope': self.scope,
                'status': status, 'event_refs': list(self.event_refs)})
        except Exception:
            raise CodexError('AUDIT_UNAVAILABLE') from None
