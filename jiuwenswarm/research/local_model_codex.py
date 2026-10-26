"""Diskless native Codex host helper. Importing this module performs no I/O.

The caller supplies public policy and pins, never credentials. Existing native
host authentication stays in its normal custody. Every invocation owns only its
new app-server process and empty working directory; it never retries inference.
"""
import asyncio
import base64
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

MAX_RESPONSE_BYTES = 1024 * 1024
MAX_PRIVATE_RECEIPT_BYTES = 4 * MAX_RESPONSE_BYTES
PROOF_RESERVE_BYTES = 64 * 1024
MODEL_KEYS = frozenset('id name model_name revision enabled context_window max_prompt_bytes timeout_s reasoning_effort'.split())
INPUT_KEYS = frozenset('model prompt timeout_s codex_executable codex_sha256 account_fingerprint working_directory'.split())
ERRORS = frozenset('auth_failed invalid_request provider_error timeout network_error invalid_output CONTAINMENT_UNCERTAIN'.split())
SYSTEM = 'Execute the supplied governed instruction. Tools are unavailable.'


class Failure(Exception):
    def __init__(self, code):
        self.code = code


def _positive(value, ceiling):
    return type(value) in (int, float) and math.isfinite(value) and 0 < value <= ceiling


def _digest(value):
    return isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value) is not None


def _validate(payload):
    if not isinstance(payload, dict) or set(payload) != INPUT_KEYS:
        raise Failure('invalid_request')
    model = payload['model']
    if not isinstance(model, dict) or set(model) != MODEL_KEYS:
        raise Failure('invalid_request')
    for key in ('id', 'name', 'model_name', 'revision'):
        if not isinstance(model[key], str) or not model[key].strip() or len(model[key]) > 256 or any(ord(c) < 32 for c in model[key]):
            raise Failure('invalid_request')
    if (model['enabled'] is not True or model['reasoning_effort'] != 'medium'
            or type(model['context_window']) is not int or model['context_window'] <= 0
            or type(model['max_prompt_bytes']) is not int or not 0 < model['max_prompt_bytes'] <= MAX_RESPONSE_BYTES
            or not _positive(model['timeout_s'], 600) or not _positive(payload['timeout_s'], model['timeout_s'])
            or not isinstance(payload['prompt'], str) or not payload['prompt'].strip()
            or len(payload['prompt'].encode('utf-8')) > model['max_prompt_bytes']
            or not _digest(payload['codex_sha256']) or not _digest(payload['account_fingerprint'])):
        raise Failure('invalid_request')
    for key in ('codex_executable', 'working_directory'):
        if not isinstance(payload[key], str) or not Path(payload[key]).is_absolute():
            raise Failure('invalid_request')
    binary = Path(payload['codex_executable']).resolve(strict=True)
    root = Path(payload['working_directory']).resolve(strict=True)
    if not binary.is_file() or not root.is_dir() or os.name == 'nt' and binary.suffix.lower() != '.exe':
        raise Failure('invalid_request')
    digest = hashlib.sha256()
    with binary.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != payload['codex_sha256']:
        raise Failure('invalid_request')
    return binary, root


def native_profile():
    """Restore the actual Windows profile when launched through WSL interop."""
    if os.name == 'nt':
        buffer = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x0028, None, 0, buffer) != 0:
            raise Failure('auth_failed')
        profile = Path(buffer.value)
        if not profile.is_absolute() or not profile.is_dir():
            raise Failure('auth_failed')
        return profile
    return Path.home()


def child_environment(profile):
    allowed = {'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'TMPDIR', 'LANG', 'LC_ALL', 'PATHEXT', 'COMSPEC'}
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    # No CODEX_HOME override, provider keys, endpoint overrides, proxy variables,
    # browser tokens, or inherited Linux HOME enter the child.
    env['HOME'] = str(profile)
    if os.name == 'nt':
        env['USERPROFILE'] = str(profile)
        env['APPDATA'] = str(profile / 'AppData' / 'Roaming')
        env['LOCALAPPDATA'] = str(profile / 'AppData' / 'Local')
    return env


def arguments(binary, effort):
    overrides = {
        'forced_login_method': 'chatgpt', 'model_reasoning_effort': effort,
        'approval_policy': 'never', 'sandbox_mode': 'read-only', 'web_search': 'disabled',
        'project_doc_max_bytes': 0, 'features.shell_tool': False, 'features.apps': False,
        'features.js_repl': False, 'features.apply_patch_freeform': False,
        'features.unified_exec': False, 'features.skill_mcp_dependency_install': False,
        'tools.view_image': False, 'mcp_servers': {},
    }
    argv = [str(binary), 'app-server', '--listen', 'stdio://']
    for key, value in overrides.items():
        argv.extend(['-c', key + '=' + json.dumps(value)])
    return argv


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def packed_frame(direction, raw):
    """One reversible encoding of original bytes, unaffected by JSON escaping."""
    return {'direction': direction, 'raw_b64': base64.b64encode(raw.encode('utf-8')).decode('ascii')}


def pack_bundle(bundle, frames, *, full, observed_frames, observed_bytes):
    """References replace duplicate start/terminal payloads; no provider rewriting."""
    value = {key: val for key, val in bundle.items() if key != 'wire_frames'}
    value['schema'] = 'ai4r-host-codex-response:2'
    value['wire_frames'] = [packed_frame(frame['direction'], frame['raw']) for frame in frames]
    for key, payload_key in (('thread_start', 'result'), ('turn_start', 'result'), ('turn_completed', 'params')):
        original = bundle[key]
        value[key] = None
        if original is not None:
            for index, frame in enumerate(frames):
                parsed = json.loads(frame['raw'])
                if frame['direction'] == 'in' and parsed.get(payload_key) == original:
                    if key != 'turn_completed' or parsed.get('method') == 'turn/completed':
                        value[key] = index
                        break
    value['evidence'] = {'full_original_trace': full, 'unavailable_reason': None if full else 'wire_budget',
        'observed_frames': observed_frames, 'observed_bytes': observed_bytes}
    return value


def unpack_bundle(value):
    """Structural v2 readback only; the caller must validate ownership and policy."""
    if not isinstance(value, dict):
        raise ValueError('Invalid native receipt')
    if value.get('schema') != 'ai4r-host-codex-response:2':
        return value
    fields = {'schema', 'requested_model', 'account_fingerprint', 'binary_sha256', 'reasoning_effort',
        'thread_start', 'turn_start', 'turn_completed', 'wire_frames', 'error_code', 'outcome', 'evidence'}
    if set(value) != fields or not isinstance(value['wire_frames'], list):
        raise ValueError('Invalid native receipt')
    evidence = value['evidence']
    if (not isinstance(evidence, dict) or set(evidence) != {'full_original_trace', 'unavailable_reason', 'observed_frames', 'observed_bytes'}
            or type(evidence['full_original_trace']) is not bool
            or evidence['unavailable_reason'] != (None if evidence['full_original_trace'] else 'wire_budget')
            or any(type(evidence[k]) is not int or not 0 <= evidence[k] <= 2**63 - 1 for k in ('observed_frames', 'observed_bytes'))):
        raise ValueError('Invalid native evidence status')
    frames = []
    for frame in value['wire_frames']:
        if (not isinstance(frame, dict) or set(frame) != {'direction', 'raw_b64'}
                or frame['direction'] not in ('in', 'out') or not isinstance(frame['raw_b64'], str)):
            raise ValueError('Invalid native frame')
        raw = base64.b64decode(frame['raw_b64'], validate=True).decode('utf-8')
        if base64.b64encode(raw.encode('utf-8')).decode('ascii') != frame['raw_b64']:
            raise ValueError('Noncanonical native frame')
        frames.append({'direction': frame['direction'], 'raw': raw})
    actual_bytes = sum(len(frame['raw'].encode('utf-8')) for frame in frames)
    if (evidence['observed_frames'] < len(frames) or evidence['observed_bytes'] < actual_bytes
            or evidence['full_original_trace'] and (evidence['observed_frames'] != len(frames) or evidence['observed_bytes'] != actual_bytes)
            or not evidence['full_original_trace'] and (value['outcome'] == 'completed' or value['error_code'] not in ('invalid_output', 'CONTAINMENT_UNCERTAIN'))):
        raise ValueError('Invalid native evidence accounting')
    result = {key: val for key, val in value.items() if key != 'evidence'}
    result['wire_frames'] = frames
    result['schema'] = 'ai4r-host-codex-response:1'
    for key, payload_key in (('thread_start', 'result'), ('turn_start', 'result'), ('turn_completed', 'params')):
        index = value[key]
        if index is None:
            continue
        if type(index) is not int or not 0 <= index < len(frames) or frames[index]['direction'] != 'in':
            raise ValueError('Invalid native evidence reference')
        parsed = json.loads(frames[index]['raw'])
        if not isinstance(parsed, dict) or payload_key not in parsed or key == 'turn_completed' and parsed.get('method') != 'turn/completed':
            raise ValueError('Invalid native evidence reference')
        result[key] = parsed[payload_key]
    return result


async def execute_async(payload, *, spawn=None, profile_resolver=None):
    """One native turn; injected process/profile adapters support offline fixtures."""
    started = time.monotonic()
    model = payload.get('model', {}) if isinstance(payload, dict) else {}
    model = model if isinstance(model, dict) else {}
    bundle = {'schema': 'ai4r-host-codex-response:1',
        'requested_model': model.get('model_name') if isinstance(model.get('model_name'), str) else None,
        'account_fingerprint': None, 'binary_sha256': None,
        'reasoning_effort': model.get('reasoning_effort') if isinstance(model.get('reasoning_effort'), str) else None,
        'thread_start': None, 'turn_start': None, 'turn_completed': None,
        'wire_frames': [], 'error_code': None, 'outcome': 'failed'}
    proc = None
    work = None
    thread_id = turn_id = None
    turn_submitted = terminal = False
    seq = 0
    captured_ids = set()
    pending = []
    deferred_frame_positions = []
    pending_bytes = 0
    capture_bytes = control_bytes = 0
    observed_frames = observed_bytes = 0
    overflow = False
    cleaning_up = False
    private_frames = []
    private_bytes = 0
    private_full = True
    deadline = main_deadline = started

    def capture(direction, raw, *, control=False, admission=False):
        nonlocal capture_bytes, control_bytes, overflow, observed_frames, observed_bytes, private_bytes, private_full
        frame = {'direction': direction, 'raw': raw}
        cost = len(_json(packed_frame(direction, raw)).encode('utf-8')) + 1
        fits = not overflow and capture_bytes + cost <= MAX_RESPONSE_BYTES - PROOF_RESERVE_BYTES
        # A generation request must be admissible before its bytes can be sent.
        if admission and not fits and not control:
            overflow = True
            raise Failure('invalid_output')
        observed_frames += 1
        observed_bytes += len(raw.encode('utf-8'))
        # Bounded private custody is independent of the public evidence budget.
        if private_bytes + cost <= 2 * MAX_RESPONSE_BYTES:
            private_frames.append(frame)
            private_bytes += cost
        else:
            private_full = False
            if control and cost <= 2 * MAX_RESPONSE_BYTES:
                # Prefer original terminal/control proof when a very long stream
                # exhausts private custody too; omission remains explicit.
                while private_frames and private_bytes + cost > 2 * MAX_RESPONSE_BYTES:
                    removed = private_frames.pop()
                    private_bytes -= len(_json(packed_frame(removed['direction'], removed['raw'])).encode('utf-8')) + 1
                private_frames.append(frame)
                private_bytes += cost
        control_fits = control and control_bytes + cost <= MAX_RESPONSE_BYTES
        if fits or control_fits:
            bundle['wire_frames'].append(frame)
            capture_bytes += cost
            if control and not fits:
                control_bytes += cost
        if not fits:
            overflow = True
            if not control and not cleaning_up:
                raise Failure('invalid_output')

    async def write(envelope, until, record=False, control=False):
        nonlocal turn_submitted
        raw = _json(envelope) + '\n'
        if record and not control:
            capture('out', raw, admission=True)
        # Containment/refusal cannot be prevented by exhausted evidence storage.
        if record and control:
            capture('out', raw, control=True)
        if envelope.get('method') == 'turn/start':
            # Admission succeeded; once writing starts the delivery may be unknown.
            turn_submitted = True
        proc.stdin.write(raw.encode('utf-8'))
        await asyncio.wait_for(proc.stdin.drain(), max(0.001, until-time.monotonic()))

    async def send(method, params, until, record=False):
        nonlocal seq
        seq += 1
        if record:
            captured_ids.add(seq)
        await write({'id': seq, 'method': method, 'params': params}, until, record, method == 'turn/interrupt')
        return seq

    def belongs(message):
        params = message.get('params') or {}
        method = message.get('method', '')
        if isinstance(method, str) and (method.startswith(('account/', 'auth/', 'login/')) or method in ('model/list', 'logout')):
            return False
        return bool(thread_id and isinstance(params, dict) and
                    (params.get('threadId') == thread_id or
                    isinstance(params.get('thread'), dict) and params['thread'].get('id') == thread_id))

    async def receive(until):
        remaining = until - time.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        raw = await asyncio.wait_for(proc.stdout.readline(), remaining)
        if not raw:
            raise Failure('network_error')
        text = raw.decode('utf-8')
        message = json.loads(text)
        if not isinstance(message, dict):
            raise Failure('invalid_output')
        method = message.get('method')
        owned = belongs(message)
        if ('id' in message and message['id'] in captured_ids and not method) or owned:
            capture('in', text, control=(method == 'turn/completed' and (message.get('params', {}).get('turn') or {}).get('id') == turn_id) or bool(method and 'id' in message))
        if method and 'id' in message:
            await write({'id': message['id'], 'error': {'code': -32601,
                'message': 'Tools and approvals are unavailable.'}}, until, owned, True)
            raise Failure('provider_error')
        if method == 'model/rerouted' and owned:
            raise Failure('invalid_output')
        return message, text, owned

    async def request(method, params, until, record=False):
        nonlocal pending_bytes
        ident = await send(method, params, until, record)
        while True:
            msg, raw, owned = await receive(until)
            if msg.get('id') == ident and 'method' not in msg:
                if 'error' in msg:
                    raise Failure('provider_error')
                value = msg.get('result')
                if not isinstance(value, dict):
                    raise Failure('invalid_output')
                return value
            if msg.get('method') and (owned or record and method == 'thread/start'):
                # Buffered account messages are never persisted; only matching
                # thread notifications are admitted after thread/start resolves.
                pending_bytes += len(raw.encode('utf-8'))
                if pending_bytes > MAX_RESPONSE_BYTES:
                    raise Failure('invalid_output')
                pending.append((msg, raw, owned))
                if record and method == 'thread/start' and not owned:
                    deferred_frame_positions.append((len(bundle['wire_frames']), msg, raw))

    try:
        binary, root = _validate(payload)
        budget = payload['timeout_s']
        deadline = started + budget
        cleanup_s = min(5.0, budget / 5)
        main_deadline = deadline - cleanup_s
        if time.monotonic() >= main_deadline:
            raise TimeoutError()
        profile = (profile_resolver or native_profile)()
        bundle['binary_sha256'] = payload['codex_sha256']
        work = Path(tempfile.mkdtemp(prefix='ai4r-codex-', dir=root))
        kwargs = {'cwd': str(work), 'env': child_environment(profile),
            'stdin': asyncio.subprocess.PIPE, 'stdout': asyncio.subprocess.PIPE,
            'stderr': asyncio.subprocess.DEVNULL, 'limit': MAX_RESPONSE_BYTES + 1}
        if os.name == 'nt':
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        proc = await asyncio.wait_for((spawn or asyncio.create_subprocess_exec)(
            *arguments(binary, model['reasoning_effort']), **kwargs), max(0.001, main_deadline-time.monotonic()))
        await request('initialize', {'clientInfo': {'name': 'ai4r_host_codex', 'version': '0.1.0'},
            'capabilities': {'experimentalApi': True, 'optOutNotificationMethods': [
                'item/agentMessage/delta', 'item/reasoning/textDelta', 'item/reasoning/summaryTextDelta']}}, main_deadline)
        await write({'method': 'initialized'}, main_deadline)
        account = (await request('account/read', {'refreshToken': False}, main_deadline)).get('account') or {}
        email = account.get('email')
        fingerprint = hashlib.sha256(email.encode()).hexdigest() if isinstance(email, str) and email else None
        if account.get('type') != 'chatgpt' or fingerprint != payload['account_fingerprint']:
            raise Failure('auth_failed')
        bundle['account_fingerprint'] = fingerprint
        del account, email, fingerprint
        # Catalog is metadata, never an entitlement assertion. The operator's
        # exact model pin must be resolved by thread/start before inference.
        await request('model/list', {'limit': 100}, main_deadline)
        result = await request('thread/start', {'cwd': str(work), 'sandbox': 'read-only',
            'approvalPolicy': 'never', 'modelProvider': 'ai4r_governed',
            'model': model['model_name'], 'ephemeral': True, 'allowProviderModelFallback': False,
            'developerInstructions': SYSTEM, 'config': {
                'model_reasoning_effort': model['reasoning_effort'],
                'model_providers.ai4r_governed.name': 'AI4Research governed subscription',
                'model_providers.ai4r_governed.wire_api': 'responses',
                'model_providers.ai4r_governed.requires_openai_auth': True,
                'model_providers.ai4r_governed.request_max_retries': 0,
                'model_providers.ai4r_governed.stream_max_retries': 0}}, main_deadline, True)
        bundle['thread_start'] = result
        thread_id = (result.get('thread') or {}).get('id')
        if (not isinstance(thread_id, str) or not thread_id
                or result.get('model') != model['model_name']
                or result.get('reasoningEffort') != model['reasoning_effort']):
            raise Failure('invalid_output')
        offset = 0
        for index, msg, raw in deferred_frame_positions:
            if belongs(msg):
                # Preserve original arrival order around the thread/start reply.
                capture('in', raw)
                frame = bundle['wire_frames'].pop()
                bundle['wire_frames'].insert(index + offset, frame)
                if private_frames and private_frames[-1] is frame:
                    private_frames.insert(index + offset, private_frames.pop())
                offset += 1
        result = await request('turn/start', {'threadId': thread_id,
            'input': [{'type': 'text', 'text': payload['prompt']}], 'model': model['model_name'],
            'approvalPolicy': 'never'}, main_deadline, True)
        bundle['turn_start'] = result
        turn_id = (result.get('turn') or {}).get('id')
        if not isinstance(turn_id, str) or not turn_id:
            raise Failure('invalid_output')
        while True:
            msg, _, _ = pending.pop(0) if pending else await receive(main_deadline)
            if not belongs(msg):
                continue
            params = msg.get('params') or {}
            if msg.get('method') == 'model/rerouted':
                raise Failure('invalid_output')
            if msg.get('method') == 'turn/completed' and (params.get('turn') or {}).get('id') == turn_id:
                if params['turn'].get('status') not in {'completed', 'failed', 'interrupted'}:
                    raise Failure('invalid_output')
                bundle['turn_completed'] = params
                terminal = True
                if params['turn'].get('status') != 'completed':
                    raise Failure('provider_error')
                bundle['outcome'] = 'completed'
                break
    except asyncio.CancelledError:
        bundle['error_code'] = 'timeout'
    except TimeoutError:
        bundle['error_code'] = 'timeout'
    except Failure as error:
        bundle['error_code'] = error.code
    except (OSError, UnicodeError, ValueError, TypeError, KeyError):
        bundle['error_code'] = 'invalid_request' if proc is None else 'invalid_output'
    except Exception:
        bundle['error_code'] = 'provider_error'
    finally:
        cleaning_up = True
        uncertain = turn_submitted and not terminal
        if proc is not None:
            if uncertain and proc.returncode is None and thread_id and turn_id:
                try:
                    until = deadline - min(0.5, max(0.01, (deadline-time.monotonic()) / 4))
                    await send('turn/interrupt', {'threadId': thread_id, 'turnId': turn_id}, until, True)
                    while time.monotonic() < until:
                        msg, _, _ = pending.pop(0) if pending else await receive(until)
                        params = msg.get('params') or {}
                        if (belongs(msg) and msg.get('method') == 'turn/completed'
                                and (params.get('turn') or {}).get('id') == turn_id
                                and params['turn'].get('status') in {'completed', 'failed', 'interrupted'}):
                            bundle['turn_completed'] = params
                            terminal = True
                            uncertain = False
                            break
                except BaseException:
                    pass
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            try:
                await asyncio.wait_for(proc.wait(), max(0.001, min(0.5, deadline-time.monotonic())))
            except BaseException:
                uncertain = turn_submitted and not terminal
            if uncertain:
                bundle['error_code'] = 'CONTAINMENT_UNCERTAIN'
                bundle['outcome'] = 'outcome_unknown'
        if bundle['outcome'] != 'completed':
            bundle['outcome'] = 'outcome_unknown' if uncertain else 'failed'
        if work is not None:
            try:
                work.rmdir()  # Only our empty directory; never recursively delete.
            except OSError:
                pass
    def response_for(frames, full):
        packed = pack_bundle(bundle, frames, full=full,
            observed_frames=observed_frames, observed_bytes=observed_bytes)
        return {'outcome': bundle['outcome'], 'http_status': None,
            'response_text': _json(packed), 'provider_request_id': turn_id}

    frames = bundle['wire_frames']
    complete_trace = (observed_frames == len(frames) and observed_bytes == sum(len(f['raw'].encode('utf-8')) for f in frames))
    response = response_for(frames, complete_trace)
    if not complete_trace or len(_json(response).encode('utf-8')) > MAX_RESPONSE_BYTES:
        overflow = True
        bundle['error_code'] = 'invalid_output' if terminal else 'CONTAINMENT_UNCERTAIN'
        bundle['outcome'] = 'failed' if terminal else 'outcome_unknown'
        # Closed failures retain original correlated control/terminal proof, with
        # explicit unavailability of the full stream. Never synthesize a frame.
        proof = []
        latest_usage = next((frame for frame in reversed(frames)
            if json.loads(frame['raw']).get('method') == 'thread/tokenUsage/updated'), None)
        for frame in frames:
            parsed = json.loads(frame['raw'])
            method = parsed.get('method')
            if (frame['direction'] == 'out' or 'id' in parsed
                    or method == 'turn/completed' and parsed.get('params') == bundle['turn_completed']
                    or frame is latest_usage):
                proof.append(frame)
        if terminal and not any(json.loads(f['raw']).get('method') == 'turn/completed' and json.loads(f['raw']).get('params') == bundle['turn_completed'] for f in proof):
            bundle['outcome'] = 'outcome_unknown' if turn_submitted else 'failed'
            bundle['error_code'] = 'CONTAINMENT_UNCERTAIN' if turn_submitted else 'invalid_output'
            bundle['turn_completed'] = None
        response = response_for(proof, False)
        if len(_json(response).encode('utf-8')) > MAX_RESPONSE_BYTES:
            # An original terminal larger than the public bound cannot be
            # independently validated. Keep honest uncertainty and private bytes.
            bundle['outcome'] = 'outcome_unknown' if turn_submitted else 'failed'
            bundle['error_code'] = 'CONTAINMENT_UNCERTAIN' if turn_submitted else 'invalid_output'
            bundle['turn_completed'] = None
            proof = [frame for frame in proof if json.loads(frame['raw']).get('method') != 'turn/completed']
            response = response_for(proof, False)
        if len(_json(response).encode('utf-8')) > MAX_RESPONSE_BYTES:
            # Admission reserves start proof, so this is only malformed/oversized
            # incoming metadata. No unavailable proof may authorize more effects.
            response = {'outcome': 'outcome_unknown', 'http_status': None,
                'response_text': None, 'provider_request_id': turn_id}
        private = {'schema': 'ai4r-host-codex-private-evidence:1',
            'full_original_trace': private_full,
            'wire_frames': [packed_frame(f['direction'], f['raw']) for f in private_frames],
            'observed_frames': observed_frames, 'observed_bytes': observed_bytes}
        carrier = {**response, '_private_evidence': private}
        if len(_json(carrier).encode('utf-8')) <= MAX_PRIVATE_RECEIPT_BYTES:
            response = carrier
    return response



def execute(payload, **adapters):
    return asyncio.run(execute_async(payload, **adapters))


def main():
    try:
        raw = sys.stdin.buffer.read(2 * MAX_RESPONSE_BYTES + 1)
        if len(raw) > 2 * MAX_RESPONSE_BYTES:
            raise ValueError()
        result = execute(json.loads(raw))
    except Exception:
        result = {'outcome': 'failed', 'http_status': None,
                  'response_text': None, 'provider_request_id': None}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(',', ':')))


if __name__ == '__main__':
    main()
