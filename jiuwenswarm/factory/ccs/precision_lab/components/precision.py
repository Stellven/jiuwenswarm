"""Portable custom INT4 reference; not a GGUF/EXL2 or CUDA format."""
import math
import struct


def integer(value, name, lo=0, hi=2**63-1):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError(name + ' outside integer bounds')
    return value


def values(data):
    if not isinstance(data, list) or not 1 <= len(data) <= 65536:
        raise ValueError('values length must be 1..65536')
    if any(isinstance(x, bool) or not isinstance(x, (int,float)) or not math.isfinite(x) or abs(x) > 1e300 for x in data):
        raise ValueError('values must be finite bounded numbers')
    return data


def quantize(data):
    source = values(data['values'])
    block = integer(data.get('block_size', 32), 'block_size', 1, 4096)
    scales, codes = [], []
    for offset in range(0, len(source), block):
        chunk = source[offset:offset+block]
        peak = max(abs(x) for x in chunk)
        scale = peak/7 if peak else 1.0
        # Tiny subnormal scales can underflow; reject rather than emit a bad codec.
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError('scale not representable')
        scales.append(scale)
        codes.extend(max(-7, min(7, round(x/scale))) & 15 for x in chunk)
    packed = [codes[i] | ((codes[i+1] if i+1 < len(codes) else 0) << 4) for i in range(0, len(codes), 2)]
    codec = dict(format='reference-symmetric-int4-f64scale-v1', count=len(source),
                 block_size=block, scales=scales, packed=packed)
    return dict(codec=codec, decoded=unpack(codec), packed_bytes=len(packed),
                scale_bytes=8*len(scales), numerical_change=True,
                qualification='cpu_reference_qualified', engine_format_compatible=False)


def unpack(codec):
    if codec.get('format') != 'reference-symmetric-int4-f64scale-v1':
        raise ValueError('unknown codec')
    count = integer(codec['count'], 'count', 1, 65536)
    block = integer(codec['block_size'], 'block_size', 1, 4096)
    scales, packed = codec['scales'], codec['packed']
    if len(scales) != (count+block-1)//block or len(packed) != (count+1)//2:
        raise ValueError('codec length mismatch')
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x <= 0 for x in scales):
        raise ValueError('invalid scale')
    for byte in packed:
        integer(byte, 'packed byte', 0, 255)
    if count % 2 and packed[-1] >> 4:
        raise ValueError('nonzero padding nibble')
    result = []
    for i in range(count):
        code = (packed[i//2] >> (4*(i%2))) & 15
        if code == 8:
            raise ValueError('reserved -8 code')
        signed = code if code < 8 else code-16
        value = signed*scales[i//block]
        if not math.isfinite(value):
            raise ValueError('nonfinite reconstruction')
        result.append(value)
    return result


def evaluate(data):
    reference, candidate = values(data['reference']), values(data['candidate'])
    if len(reference) != len(candidate):
        raise ValueError('length mismatch')
    # Subtract first: an unrelated equal outlier must not erase tiny errors.
    # Inputs are capped at 1e300, so these differences cannot overflow.
    errors = [abs(a-b) for a,b in zip(reference,candidate)]
    maximum = max(errors)
    rmse = maximum * math.sqrt(sum((x/maximum)**2 for x in errors)/len(errors)) if maximum else 0.0
    budget = data.get('max_abs_budget', 0.0)
    if isinstance(budget,bool) or not isinstance(budget,(int,float)) or not math.isfinite(budget) or budget < 0:
        raise ValueError('invalid error budget')
    if not math.isfinite(maximum) or not math.isfinite(rmse):
        raise ValueError('unrepresentable error metric')
    exact = reference == candidate
    return dict(max_abs_error=maximum, rmse=rmse, within_budget=maximum <= budget,
                exact_equal=exact, exact_gate=exact, numerical_change=not exact,
                approximation_gate=maximum <= budget,
                qualification='cpu_reference_qualified', model_quality_proven=False)


def calibrate(data):
    source = values(data['values'])
    candidates = data.get('block_sizes', [16,32,64])
    if not isinstance(candidates,list) or not 1 <= len(candidates) <= 16:
        raise ValueError('1..16 block sizes required')
    results = []
    for block in candidates:
        result = quantize(dict(values=source, block_size=block))
        metrics = evaluate(dict(reference=source, candidate=result['decoded'],
                                max_abs_budget=data['max_abs_budget']))
        results.append(dict(block_size=block, bytes=result['packed_bytes']+result['scale_bytes'], **metrics))
    passing = [x for x in results if x['within_budget']]
    return dict(candidates=results, selected=min(passing,key=lambda x:x['bytes']) if passing else None,
                calibration_scope='supplied tensor only; not held-out model quality',
                qualification='cpu_reference_qualified', numerical_change=True)


def memory_plan(data):
    count = integer(data['weight_elements'], 'weight_elements')
    block = integer(data.get('block_size',32), 'block_size',1,4096)
    tokens = integer(data['tokens'], 'tokens')
    layers = integer(data.get('layers',40), 'layers',1,10000)
    heads = integer(data['kv_heads'], 'kv_heads',1,10000)
    dim = integer(data['head_dim'], 'head_dim',1,10000)
    batch = integer(data.get('batch',1), 'batch',1,10000)
    elements = batch*tokens*layers*heads*dim*2
    bits = integer(data.get('kv_candidate_bits',8), 'kv_candidate_bits',1,16)
    return dict(weight_reference_int4_bytes=(count+1)//2+8*((count+block-1)//block),
                weight_fp16_bytes=2*count, kv_fp16_bytes=elements*2,
                kv_candidate_payload_bytes=(elements*bits+7)//8,
                kv_candidate_bits=bits, kv_candidate_approximate=True,
                kv_metadata_bytes_included=False,
                notes=['KV candidate excludes scales/zero points/alignment and allocator workspace',
                       'KV formula describes conventional K and V; MLA needs its actual cache layout',
                       'reference INT4 uses float64 scales; native formats differ'],
                qualification='cpu_reference_qualified', numerical_change=True)
