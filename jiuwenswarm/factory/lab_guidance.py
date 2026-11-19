"""Evidence-linked proposals only; existing task admission owns execution and scoring."""
import hashlib
import json
import math


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def recommend(bundle,evidence_id):
    if not isinstance(bundle,dict) or bundle.get('schema')!='factory.lab-guidance-input/1':
        raise ValueError('One immutable factory.lab-guidance-input/1 bundle required')
    refs=bundle.get('evidence_ids')
    if not isinstance(refs,list) or not refs or not all(isinstance(x,str) and x for x in refs):raise ValueError('Scoped evidence IDs required')
    result=dict(schema='factory.lab-guidance/1',recommendation='collect_more',evidence_ids=[evidence_id,*refs],bundle_sha256=digest(bundle),
        bottleneck='unknown',alternative_explanation='Missing telemetry cannot distinguish storage, scheduling, compute or observer effects.',
        benefit_range=None,cost_range=None,required_observations=[],source_owner=None,cc_candidates=[],ontology_delta=None,draft_child_contract=None,
        execution_authorized=False,promotion_authorized=False)
    budget=bundle.get('remaining',{})
    if budget.get('successors',0)<1 or budget.get('lab_attempts',0)<1:
        result.update(recommendation='stop',required_observations=['No remaining admitted successor/lab allowance.']);return result
    failure=bundle.get('failure')
    owners={'model_intake':('factory.lab_client','pinned model metadata intake'),
            'material_application':('engine.expert_weight_streaming_builder','CC material application'),
            'build':('factory.builder','source-to-binary construction'),
            'capture':('factory.lab_client','independent observation capture')}
    if failure:
        if failure.get('evidence_id') not in refs or failure.get('boundary') not in owners or not failure.get('source_commit') or not failure.get('reproducer'):
            raise ValueError('Failure proposal requires scoped evidence, source seam and bounded reproducer')
        cc,owner=owners[failure['boundary']]
        delta=dict(schema='factory.ontology-delta/1',base=bundle.get('ontology_base','factory-inference/1'),version=1,
            entities=['CapabilityInvocation','OwnedArtifact','VerificationBoundary'],
            relations=[{'from':'CapabilityInvocation','relation':'fails_at','to':'VerificationBoundary','observed_by':failure['evidence_id']}],
            inferred_state='The observed boundary failed; engine performance remains unknown.',evidence_ids=[failure['evidence_id']])
        child=dict(schema='factory.draft-child-contract/1',version=1,base_contract_sha256=bundle.get('identities',{}).get('contract_sha256'),ontology_delta_sha256=digest(delta),
            treatment='Repair only '+owner+' at the retained failing seam.',falsifier='The same bounded reproducer still fails or independent validation is weakened.',
            reproducer=failure['reproducer'],guardrails=['Preserve the failed receipt','Keep admission and numerical policy unchanged','Run focused CPU regression before hardware','At most one successor'],
            acceptance='A new actual CC call produces complete independently validated artifacts; no performance claim from repair alone.',draft_only=True,requires_operator_task_admission=True)
        result.update(recommendation='propose',bottleneck='Observed '+owner+' failure blocks qualification.',alternative_explanation='Failure may originate in the caller or environment; inspect the cited boundary before changing the CC.',
            source_owner={'owner':owner,'source_commit':failure['source_commit']},cc_candidates=[cc],ontology_delta=delta,draft_child_contract=child,
            required_observations=['Before/after real invocation receipts and retained failure details.'])
        return result
    identities=bundle.get('identities',{})
    if any(not identities.get(k) for k in ('source_commit','image_id','executable_sha256','model_manifest_sha256','contract_sha256')):
        result['required_observations']=['Complete build/model/contract lineage.'];return result
    quality=bundle.get('quality',{})
    if quality.get('complete') is not True or quality.get('correctness')!='pass' or quality.get('independent_aa') is not True:
        result['required_observations']=['Complete raw evidence, exact output/stop comparison and independent A/A.'];return result
    variation=quality.get('aa_relative_spread')
    if type(variation) not in (int,float) or not math.isfinite(variation) or not 0<=variation<=.05:
        result['required_observations']=['Resolve A/A noise above the fixed 5% bound before selecting a speed treatment.'];return result
    trace=bundle.get('trace',{})
    if trace.get('schema')=='startup-request-pairs/1':
        rows=trace.get('processes',[])
        if len(rows)<2 or trace.get('startup_warmup') is not False:
            result['required_observations']=['Two independently started processes with declared startup warmup policy.'];return result
        process_ids=[row.get('process_id') for row in rows]
        if any(not isinstance(p,str) or not p for p in process_ids) or len(set(process_ids))!=len(rows):
            raise ValueError('Distinct process identities required')
        for row in rows:
            if row.get('evidence_id') not in refs:raise ValueError('Startup trace is not linked to bundle evidence')
            for name in ('first_ttft_ms','warm_ttft_ms','launch_to_ready_ms'):
                value=row.get(name)
                if type(value) not in (int,float) or not math.isfinite(value) or value<=0:
                    raise ValueError('Finite positive observed startup/request durations required')
        cold=[r['first_ttft_ms'] for r in rows];warm=[r['warm_ttft_ms'] for r in rows]
        if (max(cold)-min(cold))/min(cold)>.1 or min(cold)<5*max(warm):
            result['required_observations']=['Repeatable first-request excess above warm latency; do not infer its cause from timing alone.'];return result
        mapping=bundle.get('source_mapping',{})
        if mapping.get('owner')!='llama_server_startup' or mapping.get('source_commit')!=identities['source_commit']:
            result['required_observations']=['Pinned server startup-policy source mapping.'];return result
        delta=dict(schema='factory.ontology-delta/1',base=bundle.get('ontology_base','factory-inference/1'),version=1,
            entities=['ProcessLaunch','EndpointReady','FirstRequest','WarmRequest'],
            relations=[{'from':'EndpointReady','relation':'precedes_initialization_cost_visible_in','to':'FirstRequest','observed_by':'paired first/warm client TTFT in independent processes'}],
            inferred_state='Repeatable excess first-request latency under disabled startup warmup; initialization cause remains unproven.',evidence_ids=[r['evidence_id'] for r in rows])
        child=dict(schema='factory.draft-child-contract/1',version=1,base_contract_sha256=identities['contract_sha256'],ontology_delta_sha256=digest(delta),
            treatment='Enable only the existing server startup warmup (remove --no-warmup); keep image, model, placement, prompts and all other settings fixed.',
            falsifier='First-request TTFT does not improve reproducibly, outputs differ, or initialization is merely shifted when the objective is launch-to-answer time.',
            guardrails=['Exact token IDs and stop reasons','Retain launch-to-ready and launch-to-first-completion costs','No artificial pressure or cache flush','Separate cold and warm requests','Fresh held-out prompt pair','At most one successor'],
            acceptance='Report request-ready TTFT separately from launch-to-answer; cost shifting is not an engine speedup. Require independent repeats and unchanged warm throughput before retaining a readiness policy.',
            draft_only=True,requires_operator_task_admission=True)
        result.update(recommendation='propose',bottleneck=delta['inferred_state'],alternative_explanation='Kernel/graph initialization, page faults or other first-use work; this evidence does not identify expert wait.',
            benefit_range=None,cost_range=None,source_owner=mapping,cc_candidates=['factory.lab_client'],ontology_delta=delta,draft_child_contract=child,
            required_observations=['Independent repeat and held-out exact-output checks; measure startup plus first completion, not TTFT alone.'])
        return result
    if trace.get('schema')!='expert-reader-timeline/1' or trace.get('critical_path_validated') is not True:
        result['required_observations']=['Phase-tagged demand/join/ready/release timing with validated critical-path attribution; byte/miss counters alone do not establish wait.'];return result
    if trace.get('evidence_id') not in refs:raise ValueError('Trace is not linked to bundle evidence')
    values=[trace.get(k) for k in ('decode_ms','uncovered_join_wait_ms','added_overhead_upper_ms')]
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in values):raise ValueError('Finite measured time bounds required')
    total,wait,overhead=values
    if total<=0 or wait>total:raise ValueError('Critical wait exceeds phase duration')
    if wait<=overhead:
        result.update(recommendation='stop',bottleneck='Measured join wait has no positive supported net benefit bound.',cost_range={'added_ms':[0,overhead]});return result
    mapping=bundle.get('source_mapping',{})
    if mapping.get('owner')!='expert_weight_streaming' or not mapping.get('path') or not mapping.get('source_commit')==identities['source_commit']:
        result['required_observations']=['Source/atlas mapping for the observed wait at the pinned revision.'];return result
    delta=dict(schema='factory.ontology-delta/1',base=bundle.get('ontology_base','factory-inference/1'),version=1,
        entities=['ExpertDemand','InFlightFill','ReadySlot','BackendReader'],
        relations=[{'from':'ExpertDemand','relation':'joins','to':'InFlightFill','observed_by':'join timestamp and shared fill identity'},
                   {'from':'InFlightFill','relation':'becomes_ready','to':'ReadySlot','observed_by':'ready timestamp and slot generation'},
                   {'from':'ReadySlot','relation':'retained_until','to':'BackendReader','observed_by':'last-reader release timestamp'}],
        inferred_state='Uncovered same-key join wait exists on the measured decode critical path.',evidence_ids=[trace['evidence_id']])
    upper=total/max(total-wait+overhead,1e-9)
    child=dict(schema='factory.draft-child-contract/1',version=1,base_contract_sha256=identities['contract_sha256'],ontology_delta_sha256=digest(delta),
        treatment='Change one fill-scheduling policy at the mapped source seam; preserve expert IDs, bytes and memory budget.',
        requirement='Reduce measured uncovered join wait after subtracting added overhead.',
        falsifier='Join wait or full client completion does not improve, or overhead consumes the reduction.',
        guardrails=['Exact token IDs and finish reason','Identical model, context and physical ceiling','No speculative expert omission','Original host memory/cleanup guards','Fresh held-out prompts','At most one admitted successor'],
        acceptance='Independent matched ABBA with exact outputs, complete engagement and client-visible gain above A/A noise; direct best-stack vs stock comparison.',
        draft_only=True,requires_operator_task_admission=True)
    result.update(recommendation='propose',bottleneck=delta['inferred_state'],alternative_explanation='Fill wait may be caused by storage or CPU scheduling; policy changes may merely move the wait.',
        benefit_range={'client_speedup':[1.0,upper],'kind':'optimistic measured-wait ceiling, not prediction'},cost_range={'added_ms':[0,overhead]},
        required_observations=['Verify actual intervention engagement and bounded waste; retain identical timeline instrumentation in both arms.'],
        source_owner=mapping,cc_candidates=['engine.expert_weight_streaming_builder','engine.expert_weight_residency_builder'],ontology_delta=delta,draft_child_contract=child)
    return result
