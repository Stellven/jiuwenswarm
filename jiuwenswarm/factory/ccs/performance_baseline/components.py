"""Portable, explicit model accounting and bounded clairvoyant page replay."""
import math
from collections import defaultdict, deque


def number(value, name, zero=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value < 0 or (not zero and value == 0):
        raise ValueError('Invalid ' + name)
    return value


def inspect(model, hardware, workload):
    tensors=model['tensors']
    if not tensors or len(tensors)>100000:
        raise ValueError('Bounded tensor inventory required')
    required=0; gaps=[]; paths=set()
    for tensor in tensors:
        n=math.prod(tensor['shape'])
        if any(type(d) is not int or d<=0 for d in tensor['shape']):
            raise ValueError('Invalid tensor shape')
        block=tensor['block_elements']; block_bytes=tensor['block_bytes']
        if type(block) is not int or block<=0 or type(block_bytes) is not int or block_bytes<=0 or n%block:
            raise ValueError('Tensor shape is incompatible with packed block layout')
        actual=n//block*block_bytes
        if actual != tensor['bytes']:
            raise ValueError('Packed tensor byte count differs')
        required+=actual;paths.add(tensor['numerical_path'])
        if tensor['numerical_path'] not in hardware['supported_paths']:
            gaps.append('Unsupported kernel path: '+tensor['numerical_path'])
    experts=workload['demanded_experts']
    if type(experts) is not int or experts <= 0 or experts != model['demanded_experts']:
        raise ValueError('Every demanded expert must be retained')
    context=workload['context'];batch=workload['batch'];layers=model['layers']
    for v in (context,batch,layers,model['kv_heads'],model['head_dimension'],model['kv_element_bytes']):
        if type(v) is not int or v<=0: raise ValueError('Invalid workload dimension')
    kv=2*layers*context*batch*model['kv_heads']*model['head_dimension']*model['kv_element_bytes']
    memory=number(hardware['usable_memory_bytes'],'capacity')
    workspace=workload.get('workspace_bytes',0)
    reserved=hardware.get('reserved_memory_bytes',0)
    for value in (workspace,reserved):
        if type(value) is not int or value<0: raise ValueError('Invalid workspace or reserved capacity')
    capacity=memory-kv-workspace-reserved
    if capacity<0: raise ValueError('KV, workspace and reserved memory exceed capacity')
    return dict(kind='analytical_accounting',model_identity=model['identity'],weight_bytes=required,
        kv_bytes=kv,workspace_bytes=workspace,reserved_memory_bytes=reserved,weight_capacity_bytes=capacity,
        demanded_experts=experts,numerical_paths=sorted(paths),gaps=gaps,
        whole_model_measurement=False)


def replay(trace, page_bytes, capacity_bytes, storage_bytes_per_s, compute_seconds):
    if type(page_bytes) is not int or page_bytes<=0 or type(capacity_bytes) is not int or capacity_bytes<0:
        raise ValueError('Invalid page size or capacity')
    if not isinstance(trace,list) or not trace or len(trace)>100000:
        raise ValueError('Bounded trace required')
    if len(compute_seconds)!=len(trace): raise ValueError('Compute timing shape differs')
    slots=capacity_bytes//page_bytes
    bandwidth=number(storage_bytes_per_s,'storage bandwidth')
    future=defaultdict(deque)
    for t,pages in enumerate(trace):
        if not pages or len(pages)!=len(set(pages)) or any(type(p) is not int or p<0 for p in pages):
            raise ValueError('Each step needs unique nonnegative weight pages')
        if len(pages)>slots:
            raise ValueError('Compulsory working set exceeds capacity')
        for p in pages: future[p].append(t)
    resident=set(); reads=0; elapsed=0; schedule=[]
    for t,pages in enumerate(trace):
        demanded=set(pages)
        for p in pages: future[p].popleft()
        missing=demanded-resident
        for p in sorted(missing):
            if len(resident)==slots:
                candidates=resident-demanded
                victim=max(candidates,key=lambda v:(future[v][0] if future[v] else math.inf,v))
                resident.remove(victim)
            resident.add(p);reads+=1
        io=len(missing)*page_bytes/bandwidth
        compute=number(compute_seconds[t],'compute time',True)
        ready=elapsed+io;elapsed=ready+compute
        schedule.append(dict(step=t,read_pages=sorted(missing),ready_s=ready,done_s=elapsed,resident_pages=sorted(resident)))
    return dict(kind='simulation',policy='farthest_next_use_fixed_pages',page_reads=reads,
        bytes_read=reads*page_bytes,elapsed_s=elapsed,schedule=schedule,
        assumptions=['serial storage and compute; no prefetch overlap','weights ready before computation','fixed-size pages; all demanded pages resident'],
        globally_optimal=False, measured=False)


def ceilings(work, calibration, measured_engine=None, simulation=None):
    required={'flops','memory_bytes','dependency_s','precision','sparsity'}
    scope={'phase','shape','model_identity','workload_identity'}
    if set(work)-required-scope or required-set(work):
        raise ValueError('Incomplete compulsory work accounting')
    for key in ('precision','sparsity'):
        if not isinstance(work[key],str) or not work[key].strip() or not isinstance(calibration.get(key),str) or not calibration[key].strip():
            raise ValueError('Explicit calibration precision/sparsity required')
    gaps=[];terms={}
    for work_key,rate_key in [('flops','flops_per_s'),('memory_bytes','memory_bytes_per_s')]:
        amount=number(work[work_key],work_key,True)
        rate=calibration.get(rate_key)
        if rate is None: gaps.append('Missing '+rate_key);continue
        terms[work_key]=amount/number(rate,rate_key)
    if (calibration.get('precision'),calibration.get('sparsity')) != (work.get('precision'),work.get('sparsity')):
        raise ValueError('Calibration precision/sparsity path differs')
    terms['dependency']=number(work['dependency_s'],'dependency bound',True)
    bound=max(terms.values()) if not gaps else None
    comparable=True
    for key in sorted(scope):
        def declared(value):
            if key=='shape':
                return isinstance(value,(list,tuple)) and bool(value) and all(type(v) is int and v>0 for v in value)
            return isinstance(value,str) and bool(value.strip())
        if not declared(work.get(key)) or not declared(calibration.get(key)):
            gaps.append('Missing calibration comparability: '+key)
            comparable=False
        elif work[key]!=calibration[key]:
            gaps.append('Calibration '+key+' differs')
            comparable=False
            bound=None
    # This portable CC has no host receipt verifier. Retain supplied records as
    # declarations; a truthy object or a self-asserted verified flag is no proof.
    gaps.append('Calibration provenance is unverified')
    gaps.append('Missing matched end-to-end engine measurement' if measured_engine is None else 'Supplied engine measurement provenance and comparability are unverified')
    gaps.append('Missing capacity/routing replay' if simulation is None else 'Supplied replay provenance and workload match are unverified')
    return dict(phase=work.get('phase'),shape=work.get('shape'),
        measured_strata_baseline=measured_engine,
        ideal_expert_availability_reference=dict(kind='declared_hardware_bound' if calibration.get('kind')=='hardware_bound' else 'empirical_target',
            minimum_seconds=bound,terms_seconds=terms,whole_model_measured=False,
            scope_comparable=comparable,provenance_verified=False),
        capacity_constrained_reference=simulation,
        supplied_evidence_verified=False,gaps=gaps,
        next_measurements=list(gaps), resident_timings_are_whole_model_tokens_per_second=False)


def experiments(hypothesis, evidence_ids, budget, slice_spec, image):
    """Return an ordinary loop specification; never invoke a lab or scheduler."""
    if slice_spec['format'] != 'f32_le_row_major':
        return dict(status='unsupported_kernel',gap='Supply a model-native packed-format oracle; dequantized synthetic timings are not a model ceiling')
    import json
    from pathlib import Path
    harness=(Path(__file__).with_name('harness.py')).read_text()
    spec=dict(hypothesis=hypothesis,evidence_ids=evidence_ids,purpose='gpu_probe',
        changed_variables=['expert_availability'],artifacts={'harness.py':harness,'slice.json':json.dumps(slice_spec)},
        recipe=['python3','/probe/harness.py','/model/weights','/probe/slice.json'],
        measurements=['storage_read_s','resident_matvec_s','launch_overhead_s','copy_bandwidth_bytes_s','maximum_absolute_error'],
        interpretation='Resident slice timing only; retain all requested rows. FP64 CPU reference checks this slice, never replaces engine acceptance.',budget=budget)
    return dict(status='experiment_specification',image=image,specification=spec,execution_authorized=False)

TOOLS={name:globals()[name] for name in ('inspect','replay','ceilings','experiments')}

from model_layout import inspect_gguf
TOOLS["inspect_gguf"] = inspect_gguf


def native_experiment(hypothesis,evidence_ids,budget,offset,shape,repeats,replay_identity=None):
    rows,columns=shape
    if any(type(v) is not int or v<=0 for v in (rows,columns,repeats)) or rows*columns>16777216 or repeats>1000 or type(offset) is not int or offset<0:
        raise ValueError('Invalid bounded tensor slice')
    recipe=['/opt/strata/baseline_oracle','/model/weights',str(offset),str(rows),str(columns),str(repeats)]
    if replay_identity is not None:
        import re
        if rows>4096 or columns>262144 or set(replay_identity)!={'run_id','tensor_id'}:
            raise ValueError('Invalid bounded replay identity')
        for value in replay_identity.values():
            if not isinstance(value,str) or not re.fullmatch('[A-Za-z0-9_.-]{1,128}',value):
                raise ValueError('Invalid replay identity')
        recipe += ['9','batch',replay_identity['run_id'],replay_identity['tensor_id']]
    return dict(hypothesis=hypothesis,evidence_ids=evidence_ids,purpose='gpu_probe',
        changed_variables=['expert_availability'],artifacts={},
        recipe=recipe,
        measurements=['storage_read_s','resident_matvec_s','copy_bandwidth_bytes_s','launch_overhead_s','maximum_absolute_error',
                      'paired_samples.gpu_event_s','paired_samples.synchronized_host_s','paired_samples.reference_passed'],
        interpretation='Caller-declared FP32 slice: native oracle does not verify tensor format, boundaries or slice digest. Host metadata validation is required to establish actual FP32 identity. Deterministic calibration activations; Legacy invocations run without retained output/reference vectors. Opt-in replay_identity retains bounded vectors outside timing for independent host recomputation from pinned slice/input bytes; producer flags are not host verification. Default nine paired samples use batch synchronization; resident_matvec_s always uses legacy batch timing. GPU events include stream idle/enqueue gaps; host times include recording/completion. Samples are correlated and observer overhead is unknown. No packed-kernel or end-to-end claim.',budget=budget)

TOOLS['native_experiment']=native_experiment

from numerical_replay import verify_vectors
TOOLS['verify_vectors'] = verify_vectors
