"""Literal mechanical verifier predicates, independent of semantic judgement."""
from __future__ import annotations
from ..contracts import ResearchError,contract_schema
from ..gate import assemble_assessment,zip_projection

CHECK_IDS=('declaration_pin_matches','output_hash_matches','assessment_schema',
           'verifier_assessment_schema','criterion_coverage_exact','verdict_follows_findings')


def contract_is(contract_id,name):
    try:return contract_schema(contract_id)==contract_schema(name)
    except ResearchError:return False


def verifier_predicates(store,contract,assessment_ref,criteria,declaration_ref,output_ref):
    predicates={key:False for key in CHECK_IDS}
    if assessment_ref is None:return predicates
    try:assessment=store.read_record(assessment_ref,contract_id='verifier-assessment')
    except ResearchError:return predicates
    named={p['name']:p['artifact_refs'] for p in contract['inputs']}
    predicates['declaration_pin_matches']=named.get('subject_declaration')==[declaration_ref] and all(declaration_ref in finding['evidence_refs'] for finding in assessment['findings'])
    reviewed=output_ref
    if assessment['subject_ref']!=output_ref:
        try:reviewed=store.put_blob(zip_projection(store.read_blob(output_ref)),media_type='text/plain;charset=utf-8')
        except ResearchError:reviewed=None
    predicates['output_hash_matches']=named.get('subject_output')==[output_ref] and assessment['subject_ref']==reviewed
    predicates['assessment_schema']=True;predicates['verifier_assessment_schema']=True
    predicates['criterion_coverage_exact']={f['criterion_id'] for f in assessment['findings']}=={c['criterion_id'] for c in criteria} and len(assessment['findings'])==len(criteria)
    reply={key:assessment[key] for key in ('uncertainties','limitations','required_correction')}
    reply['findings']=[{key:f[key] for key in ('criterion_id','outcome','reason')} for f in assessment['findings']]
    try:predicates['verdict_follows_findings']=assemble_assessment(reply,criteria,declaration_ref,assessment['subject_ref'],assessment['review_context_ref'])==assessment
    except ResearchError:pass
    return predicates


def verifier_checks(ctx,inputs,outputs):
    predicates={key:False for key in CHECK_IDS};reason='Exact literal verifier mechanical predicates recomputed'
    try:
        if len(ctx.output_refs)!=1:raise ResearchError('calibration_context','One actual verifier assessment is required')
        assessment_ref=next(iter(ctx.output_refs.values()));assessment=ctx.store.read_record(assessment_ref,contract_id='verifier-assessment')
        review=ctx.store.read_record(assessment['review_context_ref'],contract_id='review-context');plan=ctx.store.read_record(review['check_plan_ref'])
        profile=ctx.store.read_record(plan['profile_ref'],contract_id='checking-profile')
        criteria=[c for c in profile['criteria'] if c['criterion_id'] in review['criteria']]
        if len(criteria)!=len(review['criteria']) or len(review['criteria'])!=len(set(review['criteria'])):
            raise ResearchError('calibration_context','Exact original criterion population is unavailable')
        predicates=verifier_predicates(ctx.store,ctx.contract,assessment_ref,criteria,ctx.input_ref('subject_declaration'),ctx.input_ref('subject_output'))
    except (ResearchError,KeyError,TypeError,ValueError):reason='Actual verifier assessment/context cannot satisfy the mechanical predicates'
    return [{'check_id':key,'outcome':'PASS' if predicates[key] else 'FAIL','reason':reason,
        'evidence_refs':list(ctx.output_refs.values())} for key in CHECK_IDS]
