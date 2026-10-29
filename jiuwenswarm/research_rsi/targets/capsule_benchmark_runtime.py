"""Guarded batched benchmark child program; no generated code executes here.

Ported from Codex's ``capsule_benchmark_runtime.py``. The program reuses the
reviewed ``capsule_runtime._child_main`` bootstrap verbatim up to its driver
boundary (identity/inventory/ABI validation, pinned assets, the trusted input
snapshot guard) and replaces only the driver: the candidate is compiled once,
then ``warmups + iterations`` invocations each get a freshly decoded input and
fresh module globals (no cross-invocation memoization through the module), the
input guard runs after each, and every invocation must produce the same
output or error. The child reports no clock: timing authority is the
dispatcher's per-process wall (V18 receipt or the local dispatcher's timer)
divided by the fixed batch size.
"""
from __future__ import annotations

import base64
import hashlib
import inspect
import json

from .capsule_runtime import _child_main, bootstrap_config, capsule_job_assets

BOOTSTRAP_SCHEMA = 'ai4r-rsi-capsule-benchmark-bootstrap:2'
CHILD_SCHEMA = 'ai4r-rsi-capsule-benchmark-child:1'
MAX_CAPTURE_BYTES = 2 * 1024 * 1024
_BOUNDARY = '    module = types.ModuleType(module_name)\n'

_DRIVER = '''    import base64
    # Bind before any candidate top-level code. Every invocation receives a
    # newly decoded input and new module globals; ordinary memoization cannot
    # turn a batch into repeated lookup of one previously computed result.
    body_path = str(resources / 'body.py')
    compiled_candidate = compile(candidate, body_path, 'exec')
    execute_code = exec
    make_module = types.ModuleType
    make_spec = importlib.util.spec_from_loader
    installed_modules = sys.modules
    decode_json = json.loads
    digest_output = hashlib.sha256
    error_type = type
    error_text = str
    error_attr = getattr
    base_error = Exception
    stopped = StopIteration
    is_coroutine = inspect.iscoroutine
    encode_output = base64.b64encode
    encode_json = json.dumps
    write_output = sys.stdout.buffer.write
    input_snapshot = snapshot
    expected_input = original_snapshot
    warmups = WARMUPS
    observed = []
    raw = None
    for index in range(warmups + config['iterations']):
        current_input = decode_json(source_input)
        need(input_snapshot(current_input) == expected_input, 'fresh benchmark input differs')
        module = make_module(module_name)
        module.__package__ = module_name.rpartition('.')[0]
        module.__file__ = body_path
        module.__spec__ = make_spec(module_name, loader=None)
        installed_modules[module_name] = module
        error = None
        try:
            execute_code(compiled_candidate, module.__dict__)
            need(input_snapshot(current_input) == expected_input, 'capsule input mutation refused')
            invocation = module.execute(None, current_input)
            need(is_coroutine(invocation), 'actual async carrier entrypoint required')
            try:
                invocation.send(None)
            except stopped as complete:
                raw = complete.value['result'].data
            else:
                invocation.close()
                raise RuntimeError('pure capsule carrier must complete without asynchronous I/O')
            need(isinstance(raw, bytes) and len(raw) <= config['output_limit_bytes'], 'bounded actual serialized packet output required')
            decode_json(raw)
            observation = {'output_sha256': digest_output(raw).hexdigest()}
        except base_error as exception:
            raw = None
            error = {'type': error_type(exception).__name__, 'code': error_attr(exception, 'code', None), 'message': error_text(exception)}
            observation = {'error': error}
        need(input_snapshot(current_input) == expected_input, 'capsule input mutation refused')
        require_original()
        observed.append(observation)
    need(all(value == observed[0] for value in observed), 'batch output/error changed between iterations')
    result = {'schema': 'ai4r-rsi-capsule-benchmark-child:1',
        'iterations': config['iterations'], 'warmups': warmups,
        'input_unmodified': True, 'observation': observed[0],
        'output_base64': encode_output(raw).decode('ascii') if raw is not None else None}
    write_output(encode_json(result, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf8'))
'''


def benchmark_worker_program(name, *, manifest_sha256, candidate_sha256, input_sha256, iterations, warmups,
                             execution_profile='v18-bwrap', resource_root=None, runtime_root=None):
    """Fixed child bytes for one batched benchmark job (protected or explicit local)."""
    from ..process_policy import POLICY, apply_policy
    if type(warmups) is not int or not 0 <= warmups <= 10:
        raise ValueError('Bounded benchmark warmups required')
    local = execution_profile == 'local_unprotected'
    policy = None if local else POLICY
    config = bootstrap_config(name, manifest_sha256=manifest_sha256, candidate_sha256=candidate_sha256,
        input_sha256=input_sha256, iterations=iterations, process_policy=policy,
        execution_profile=execution_profile, resource_root=resource_root, runtime_root=runtime_root)
    original = inspect.getsource(_child_main)
    if original.count(_BOUNDARY) != 1 or original.count('    require_original()\n') < 2:
        raise ValueError('Reviewed bootstrap driver boundary changed')
    prefix = original.split(_BOUNDARY)[0]
    driver = _DRIVER.replace('WARMUPS', repr(warmups))
    return apply_policy((prefix + driver + '\n_child_main(' + repr(config) + ')\n').encode(), policy)


def benchmark_job_assets(name, *, runtime_root, manifest, candidate, packet, iterations, warmups,
                         execution_profile='v18-bwrap', resource_root=None):
    """``capsule_job_assets`` with the guarded batched benchmark program as worker."""
    from .capsules import registered_capsule
    local = execution_profile == 'local_unprotected'
    assets = capsule_job_assets(name, runtime_root=runtime_root, manifest=manifest, candidate=candidate,
        inputs={registered_capsule(name).input_name: packet}, iterations=iterations,
        **({'execution_profile': execution_profile, 'resource_root': resource_root} if local else {}))
    assets['files']['worker.py'] = benchmark_worker_program(name,
        manifest_sha256=assets['runtime_manifest_sha256'], candidate_sha256=assets['candidate_sha256'],
        input_sha256=hashlib.sha256(assets['files']['input.json']).hexdigest(), iterations=iterations,
        warmups=warmups, execution_profile=execution_profile,
        resource_root=str(resource_root) if local else None, runtime_root=assets['runtime_root'] if local else None)
    assets.update(bootstrap_schema=BOOTSTRAP_SCHEMA, warmups=warmups)
    return assets


def decode_benchmark_output(raw):
    """Strict framing of the child envelope -> ``(envelope, output | None, error | None)``."""
    if not isinstance(raw, bytes) or len(raw) > MAX_CAPTURE_BYTES:
        raise ValueError('Bounded benchmark capture required')

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate benchmark output key')
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite benchmark JSON')))
    if (type(value) is not dict or set(value) != {'schema', 'iterations', 'warmups', 'input_unmodified', 'observation', 'output_base64'}
            or value['schema'] != CHILD_SCHEMA
            or type(value['iterations']) is not int or value['iterations'] <= 0
            or type(value['warmups']) is not int or value['warmups'] < 0 or value['input_unmodified'] is not True):
        raise ValueError('Exact original benchmark child framing required')
    observation = value['observation']
    if value['output_base64'] is None:
        if (type(observation) is not dict or set(observation) != {'error'}
                or type(observation['error']) is not dict or set(observation['error']) != {'type', 'code', 'message'}):
            raise ValueError('Exact benchmark error capture required')
        return value, None, observation['error']
    output = base64.b64decode(value['output_base64'], validate=True)
    if observation != {'output_sha256': hashlib.sha256(output).hexdigest()}:
        raise ValueError('Benchmark output digest differs')
    return value, output, None
