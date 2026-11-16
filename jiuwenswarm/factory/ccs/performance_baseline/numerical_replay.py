"""Bounded independent FP32-slice arithmetic replay; no GPU or producer verdict."""
import hashlib
import json
import math
import struct

FORMAT = 'factory-fp32-replay/1'
CRITERION = 'abs(error)<=1e-5+1e-5*abs(reference)'
MAX_ELEMENTS = 16777216


def _json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError('Duplicate replay key')
            out[key] = value
        return out
    def invalid(value):
        raise ValueError('Nonfinite replay metadata')
    if len(raw) > 16384:
        raise ValueError('Replay metadata exceeds bound')
    value=json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    if not isinstance(value,dict):
        raise ValueError('Replay metadata must be an object')
    return value


def _vector(raw, count, kind):
    width = struct.calcsize(kind)
    if len(raw) != count * width:
        raise ValueError('Vector dimensions differ')
    values = [v[0] for v in struct.iter_unpack('<'+kind, raw)]
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Nonfinite vector')
    return values


def verify(expected, read_artifact, read_slice):
    """expected comes from independent admission, never the producer's metadata.

    read_artifact must verify retained artifact digests. read_slice returns the
    host's separately pinned model bytes, not an untrusted producer reference.
    """
    try:
        metadata = read_artifact('replay.json')
    except (FileNotFoundError, KeyError):
        return dict(status='unverified', reference_recomputed=False, reason='No retained replay material')
    meta = _json(metadata)
    if meta.get('format') != FORMAT or meta.get('criterion') != CRITERION:
        raise ValueError('Replay format or fixed criterion differs')
    for key in ('run_id', 'tensor_id', 'offset', 'shape', 'repeats', 'samples', 'synchronization', 'input_kind'):
        if key not in expected or json.dumps(meta.get(key),sort_keys=True) != json.dumps(expected[key],sort_keys=True):
            raise ValueError('Declared replay identity differs: '+key)
    rows, columns = expected['shape']
    if (any(type(v) is not int or v < 1 for v in (rows, columns, expected['repeats']))
            or rows > 4096 or columns > 262144 or rows*columns > MAX_ELEMENTS
            or type(expected['samples']) is not int or not 0 <= expected['samples'] <= 31 or expected['repeats'] > 1000
            or type(expected['offset']) is not int or expected['offset'] < 0):
        raise ValueError('Replay dimensions exceed bound')
    if expected['synchronization'] not in {'batch', 'each'}:
        raise ValueError('Invalid synchronization identity')
    raw = read_slice(expected['offset'], rows*columns*4)
    if hashlib.sha256(raw).hexdigest() != expected['slice_sha256']:
        raise ValueError('Pinned tensor slice digest differs')
    if len(raw) != rows*columns*4 or not all(math.isfinite(v[0]) for v in struct.iter_unpack('<f',raw)):
        raise ValueError('Nonfinite or truncated tensor bytes')
    input_raw = read_artifact('input.f32')
    if hashlib.sha256(input_raw).hexdigest() != expected['input_sha256']:
        raise ValueError('Pinned input digest differs')
    x = _vector(input_raw, columns, 'f')
    if expected['input_kind'] == 'calibration_mod17':
        canonical = b''.join(struct.pack('<f', (k%17-8)/17) for k in range(columns))
        if input_raw != canonical:
            raise ValueError('Deterministic calibration input differs')
    elif expected['input_kind'] != 'pinned_fp32':
        raise ValueError('Unsupported input identity')
    # Binary32 operands multiply exactly in binary64. fsum defines the independent
    # host reduction; the producer's FP64 accumulation is retained only for audit.
    reference = [math.fsum(v[0]*x[k] for k,v in enumerate(struct.iter_unpack('<f',raw[r*columns*4:(r+1)*columns*4]))) for r in range(rows)]
    if not all(math.isfinite(v) for v in reference):
        raise ValueError('Nonfinite recomputed reference')
    supplied = _vector(read_artifact('reference.f64'), rows, 'd')
    outputs = _vector(read_artifact('output.f32'), rows*(expected['samples']+1), 'f')
    def check(values):
        errors = [abs(v-reference[i%rows]) for i,v in enumerate(values)]
        return all(e <= 1e-5+1e-5*abs(reference[i%rows]) for i,e in enumerate(errors)), max(errors)
    passed, error = check(outputs)
    reference_matches, reference_error = check(supplied)
    return dict(status='verified' if passed and reference_matches else 'failed',
        reference_recomputed=True, criterion=CRITERION, output_passed=passed,
        producer_reference_matches=reference_matches, maximum_absolute_error=error,
        producer_reference_maximum_error=reference_error,
        run_id=expected['run_id'], tensor_id=expected['tensor_id'], shape=expected['shape'],
        slice_sha256=expected['slice_sha256'], input_sha256=expected['input_sha256'],
        vectors_checked=expected['samples']+1, tensor_metadata_verified=False,
        execution_provenance_verified=False, promotion_authorized=False,
        scope='FP32 row-major slice times pinned FP32 input; FP64 host fsum reference',
        limitations=['Tensor name/extent mapping is independently admitted, not parsed from model metadata here.',
                     'Retained outputs do not independently prove GPU execution or timing correctness.',
                     'No packed-expert, captured-activation or whole-model claim.'])


def verify_vectors(weights_path, replay_root, expected, artifact_sha256):
    """Portable offline capability: pins are caller declarations, not admission."""
    from pathlib import Path
    root = Path(replay_root).resolve()
    def read(name):
        path = root/name
        if not path.resolve().is_relative_to(root):
            raise ValueError('Escaping replay artifact')
        if not path.exists() and name == 'replay.json':
            raise FileNotFoundError(name)
        limit = {'replay.json':16384,'input.f32':1048576,'reference.f64':32768,'output.f32':524288}[name]
        with path.open('rb') as stream:
            raw = stream.read(limit+1)
        if len(raw)>limit or hashlib.sha256(raw).hexdigest()!=artifact_sha256.get(name):
            raise ValueError('Retained replay artifact digest or bound differs: '+name)
        return raw
    def slice_bytes(offset, size):
        with Path(weights_path).open('rb') as stream:
            stream.seek(offset)
            return stream.read(size)
    result = verify(expected,read,slice_bytes)
    return dict(result,admission_verified=False,identity_authority='caller-declared pins; use host verify_attempt for task admission')
