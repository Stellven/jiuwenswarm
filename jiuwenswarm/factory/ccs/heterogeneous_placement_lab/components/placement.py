"""Measured-cost CPU reference. No device allocation or model modifications."""
import math


def number(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum or abs(value) > 1e100:
        raise ValueError(name + ' must be finite and >= ' + str(minimum))
    return value


def integer(value, name, minimum=0, maximum=2**63-1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(name + ' outside integer bounds')
    return value


def selected(data):
    ids = data['selected_experts']
    if not isinstance(ids, list) or len(ids) != 6 or len(set(ids)) != 6:
        raise ValueError('exactly six distinct selected experts required')
    for expert in ids:
        integer(expert, 'expert', 0, 383)
    return ids


def plan(data):
    ids = selected(data)
    integer(data.get('layer', 0), 'layer', 0, 39)
    capacity = integer(data['physical_capacity_bytes'], 'physical_capacity_bytes')
    reserved = integer(data.get('reserved_bytes', 0), 'reserved_bytes')
    cpu_bytes = integer(data.get('cpu_resident_bytes', 0), 'cpu_resident_bytes')
    gpu_bytes = integer(data.get('gpu_resident_bytes', 0), 'gpu_resident_bytes')
    scratch = integer(data.get('scratch_bytes', 0), 'scratch_bytes')
    unified = data.get('unified_memory', True)
    if type(unified) is not bool:
        raise ValueError('unified_memory must be boolean')
    # Counts allocations once, including explicit GPU replicas even on unified RAM.
    used = reserved + cpu_bytes + gpu_bytes + scratch
    if used > capacity:
        raise ValueError('shared physical memory budget exceeded')
    bandwidth = number(data['transfer_bytes_per_second'], 'transfer_bytes_per_second', 1e-12)
    costs = data['measurements']
    resident = data.get('gpu_resident_experts', [])
    if not isinstance(resident, list) or any(type(x) is not int or not 0 <= x < 384 for x in resident):
        raise ValueError('invalid gpu_resident_experts')
    free = capacity - used
    decisions = []
    for expert in ids:
        sample = costs[str(expert)]
        cpu = number(sample['cpu_ms'], 'cpu_ms')
        gpu = number(sample['gpu_ms'], 'gpu_ms')
        weight = integer(sample['weight_bytes'], 'weight_bytes')
        activation = integer(sample['activation_bytes'], 'activation_bytes')
        # activation_bytes includes both input and returned output traffic.
        cpu_total = cpu + activation / bandwidth * 1000
        transfer = 0 if expert in resident else weight / bandwidth * 1000
        gpu_total = gpu + transfer
        extra = 0 if expert in resident else weight
        device = 'gpu' if gpu_total < cpu_total and extra <= free else 'cpu'
        if device == 'gpu':
            free -= extra
        decisions.append(dict(expert=expert, device=device, cpu_total_ms=cpu_total,
                              gpu_total_ms=gpu_total, weight_transfer_ms=transfer,
                              activation_transfer_ms=activation / bandwidth * 1000,
                              estimated_ms=gpu_total if device == 'gpu' else cpu_total))
    return dict(qualification='cpu_reference_qualified', exact_selected_experts=True,
                selected_experts=ids, decisions=decisions, physical_used_bytes=capacity-free,
                free_bytes=free, unified_memory=unified, estimate_only=True,
                algorithm='ordered greedy marginal choice; not global optimum')


def execute_reference(data):
    ids = selected(data)
    vector = data['activation']
    if not isinstance(vector, list) or not 1 <= len(vector) <= 256:
        raise ValueError('activation length must be 1..256')
    for x in vector:
        number(x, 'activation', -1e100)
    coefficients = data['router_weights']
    if len(coefficients) != 6:
        raise ValueError('six router weights required')
    outputs = []
    width = None
    for expert, coefficient in zip(ids, coefficients):
        number(coefficient, 'router weight', -1e100)
        matrix = data['expert_matrices'][str(expert)]
        if not isinstance(matrix, list) or not 1 <= len(matrix) <= 256:
            raise ValueError('matrix rows must be 1..256')
        if width is None:
            width = len(matrix)
        if len(matrix) != width:
            raise ValueError('expert output widths differ')
        out = []
        for row in matrix:
            if len(row) != len(vector):
                raise ValueError('matrix shape mismatch')
            for x in row:
                number(x, 'matrix entry', -1e100)
            out.append(sum(x*y for x,y in zip(row, vector))*coefficient)
        outputs.append(out)
    result = [sum(row[i] for row in outputs) for i in range(width)]
    if not all(math.isfinite(x) for x in result):
        raise ValueError('nonfinite output')
    return dict(output=result, executed_experts=ids, router_weights=coefficients,
                qualification='cpu_reference_qualified', execution_backend='stdlib_cpu',
                exact_selected_experts=True)


def overlap_schedule(data):
    stages = data['stages']
    if not isinstance(stages, list) or not 1 <= len(stages) <= 4096:
        raise ValueError('stages length must be 1..4096')
    transfer_end = compute_end = serial = 0.0
    events = []
    for index, stage in enumerate(stages):
        transfer = number(stage['transfer_ms'], 'transfer_ms')
        compute = number(stage['compute_ms'], 'compute_ms')
        # Independent transfer engine plus compute stream, unlimited lifetime buffers.
        transfer_start = transfer_end
        transfer_end += transfer
        start = max(transfer_end, compute_end)
        compute_end = start + compute
        serial += transfer + compute
        events.append(dict(stage=index, transfer_start_ms=transfer_start,
                           ready_ms=transfer_end, compute_start_ms=start, end_ms=compute_end))
    tokens = integer(data.get('tokens', 1), 'tokens', 1, 1000000)
    return dict(events=events, serial_ms=serial, optimistic_overlap_ms=compute_end,
                estimated_ms_per_token=compute_end/tokens, tokens=tokens,
                mode='decode' if tokens == 1 else 'batch_or_prefill', estimate_only=True,
                assumptions=['independent engines', 'unlimited staging lifetimes',
                             'no unified bandwidth contention; measure on GB10'],
                qualification='cpu_reference_qualified')
