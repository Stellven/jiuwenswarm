"""Finite qualification parsing/provenance; synthetic frames cannot seed runtime."""
import json
from pathlib import Path

import pytest

from jiuwenswarm.research.builder_qualification import (PREFIX, PROBE_COMMAND, PROBE_PROMPT,
    QualificationBinding, QualificationEvents, command_is_probe, validate_probe, validate_tool_qualification)
from jiuwenswarm.research.executor import ExecutorBlocked
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import SQLiteRunStore


def probe(nonce='a' * 64):
    return {'schema': 'ai4r-builder-tool-probe-result:1', 'nonce': nonce, 'uid': 10002, 'gid': 10002,
        'cap_eff': '0000000000000000', 'no_new_privs': '1', 'workspace_write': True,
        'denied_paths': {k: True for k in ('run_state', 'main_credential', 'fixture', 'library')},
        'network': {k: {'denied': True, 'errno': 1} for k in ('ipv4', 'ipv6')}}


def feed(state, value):
    return state.feed(json.dumps(value).encode() + b'\n')


def completed_probe(value=None, command=PROBE_COMMAND):
    return {'type': 'item.completed', 'item': {'id': 'actual-tool-id', 'type': 'command_execution',
        'command': command, 'status': 'completed', 'exit_code': 0,
        'aggregated_output': PREFIX + json.dumps(probe() if value is None else value) + '\n'}}


def test_only_exact_fixed_command_or_transparent_native_shell_wrapper():
    assert command_is_probe(PROBE_COMMAND)
    assert command_is_probe('/bin/bash -lc ' + __import__('shlex').quote(PROBE_COMMAND))
    for value in [PROBE_COMMAND + '; true', PROBE_COMMAND + ' >result', 'echo ' + PROBE_COMMAND,
                  'python3 /resources/qualification_probe.py', 'cat /builder-home/auth.json',
                  '/bin/bash -lc ' + __import__('shlex').quote(PROBE_COMMAND + ' && pwd')]:
        assert not command_is_probe(value)


def test_agent_prose_cannot_substitute_for_completed_tool_event():
    state = QualificationEvents(2, 'a' * 64)
    feed(state, {'type': 'item.completed', 'item': {'id': 'answer', 'type': 'agent_message', 'text': PREFIX + json.dumps(probe())}})
    feed(state, {'type': 'turn.completed', 'usage': {}})
    assert state.success and state.probe_result is None and state.tool_count == 0
    # A successful provider response alone never meets qualification predicates.
    assert not (state.success and state.tool_count == 1 and state.probe_result is not None)


def test_actual_tool_frame_requires_nonce_identity_network_and_complete_denials():
    state = QualificationEvents(2, 'a' * 64)
    assert feed(state, completed_probe()) is None
    assert state.probe_result == probe() and state.tool_count == 1
    for key, value in [('nonce', 'b' * 64), ('uid', 0), ('cap_eff', '0000000000000001'), ('workspace_write', False)]:
        changed = probe(); changed[key] = value
        state = QualificationEvents(2, 'a' * 64)
        assert feed(state, completed_probe(changed)) == 'invalid_output'
    for role in ('run_state', 'main_credential', 'fixture', 'library'):
        changed = probe(); changed['denied_paths'][role] = False
        with pytest.raises(ExecutorBlocked): validate_probe(changed, 'a' * 64)
    for family in ('ipv4', 'ipv6'):
        changed = probe(); changed['network'][family] = {'denied': False, 'errno': 0}
        with pytest.raises(ExecutorBlocked): validate_probe(changed, 'a' * 64)
        changed['network'][family] = {'denied': True, 'errno': None}
        with pytest.raises(ExecutorBlocked): validate_probe(changed, 'a' * 64)


def test_second_command_file_change_and_unqualified_tools_fail_closed():
    state = QualificationEvents(3, 'a' * 64)
    assert feed(state, completed_probe()) is None
    extra = completed_probe(); extra['item']['id'] = 'second'
    assert feed(state, extra) == 'invalid_output'
    for item in [{'id': 'bad', 'type': 'command_execution', 'command': 'pwd'},
                 {'id': 'edit', 'type': 'file_change', 'changes': [{'path': '/workspace/poc/x'}]}]:
        state = QualificationEvents(2, 'a' * 64)
        assert feed(state, {'type': 'item.started', 'item': item}) == 'prohibited_tool'


def test_payload_kind_and_raw_blob_are_not_protected_producer_metadata(tmp_path):
    from types import SimpleNamespace
    with __import__('contextlib').closing(SQLiteRunStore(tmp_path / 'store')) as store:
        claimed = {'schema': 'ai4r-builder-tool-qualification-producer:1', 'kind': 'builder_tool_qualification',
                   'build_id': 'fake', 'codex_sha256': 'a' * 64}
        raw = store.put_blob(json.dumps(claimed).encode())
        runtime = SimpleNamespace(build_id='fake', codex_sha256='a' * 64)
        with pytest.raises((ExecutorBlocked, ResearchError)):
            validate_tool_qualification(store, {'producer_ref': raw, 'evidence_refs': [raw]}, runtime)
        ref = store.append_record('untrusted-proposal', claimed)
        with pytest.raises(ExecutorBlocked, match='PROTECTED_PROVENANCE'):
            validate_tool_qualification(store, {'producer_ref': ref, 'evidence_refs': [ref]}, runtime)


def test_closed_binding_has_no_placeholder_qualification_or_arbitrary_prompt(tmp_path):
    from jiuwenswarm.research.builder_qualification import PROBE_PATH, sha
    with __import__('contextlib').closing(SQLiteRunStore(tmp_path / 'store')) as store:
        value = {field: None for field in QualificationBinding.__dataclass_fields__}
        value.update(schema='ai4r-builder-qualification-binding:1', job_id='ai4r-builder-qual-unit', build_id='unit',
                     codex_version='0.144.4', qualification_ref={'id': 'synthetic', 'sha256': 'a' * 64})
        ref = store.put_blob(json.dumps(value).encode())
        with pytest.raises(ExecutorBlocked, match='BINDING_INVALID'):
            QualificationBinding.load(store, ref, build_id='unit')
        assert sha(PROBE_PATH.read_bytes()) != sha(PROBE_PROMPT.encode())


@pytest.mark.asyncio
async def test_transcript_kernel_cannot_invoke_production_qualification(tmp_path):
    from types import SimpleNamespace
    from jiuwenswarm.research.builder_qualification import qualify_builder_tools
    with __import__('contextlib').closing(SQLiteRunStore(tmp_path / 'store')) as store:
        with pytest.raises(ExecutorBlocked, match='ACTUAL_KERNEL_AND_STORE'):
            await qualify_builder_tools(store=store, executor=SimpleNamespace(_run_kernel=lambda: None),
                binding_ref={'id': 'never-read', 'sha256': 'a' * 64}, build_id='never-trusted')
