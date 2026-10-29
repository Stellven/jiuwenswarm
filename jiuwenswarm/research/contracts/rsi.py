"""Independent admission-side RSI evidence validation. No workbench imports."""

from __future__ import annotations

import base64
import copy
import fnmatch
import json
import math
import statistics
from fractions import Fraction

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from . import ResearchError,validate


def require(condition,code,detail):
    if not condition:raise ResearchError(code,detail)


def verify_signature(record,public_key,key_id):
    require(record.get('signer_key_id')==key_id,'rsi_signature','Signer is not the operator-pinned custodian')
    try:
        signature=record['signature'];raw=base64.b64decode(signature+'='*(-len(signature)%4),altchars=b'-_',validate=True)
        require(len(raw)==64 and '=' not in signature,'rsi_signature','Invalid signature representation')
        body={k:v for k,v in record.items() if k!='signature'}
        message=json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
        Ed25519PublicKey.from_public_bytes(public_key).verify(raw,message)
    except ResearchError:raise
    except Exception as exc:raise ResearchError('rsi_signature','Custodian signature verification failed') from exc


def verify_package(package,store,*,public_key,key_id,protected_body_hashes=()):
    validate('candidate-package',package)
    def record(ref,contract=None):return store.read_record(ref,contract_id=contract)
    session=record(package['session_ref'],'rsi-session');result=record(package['session_result_ref'],'rsi-session-result')
    referee=record(package['referee_evidence_ref'],'rsi-referee-evidence');target=record(package['target_profile_ref'],'rsi-target-profile')
    provenance=record(package['provenance_ref'],'candidate-provenance')
    parent=record(package['parent_declaration_ref'],'capsule-declaration');child=record(package['child_declaration_ref'],'capsule-declaration')
    verify_signature(result,public_key,key_id);verify_signature(referee,public_key,key_id)
    for pin,declaration,ref in [(package['parent'],parent,package['parent_declaration_ref']),(package['child'],child,package['child_declaration_ref'])]:
        require(pin=={'cc_name':declaration['identity']['name'],'cc_version':declaration['identity']['version_label'],'declaration_sha256':ref['sha256']},'rsi_identity','Pin differs from exact declaration')
    require(package['parent']['cc_name']==package['child']['cc_name'] and package['parent']['cc_version']!=package['child']['cc_version'],'rsi_identity','Child must preserve name and change version')
    require(parent['evolution']['rsi']=='propose','rsi_scope','Parent does not permit RSI proposals')
    lineage=child['identity'].get('lineage',{})
    require(lineage.get('parent')==package['parent_declaration_ref'] and lineage.get('relation')=='supersedes' and lineage.get('builder')=='rsi_workbench','rsi_lineage','Child lineage does not name exact parent')
    stripped=[]
    for declaration in (parent,child):
        value=copy.deepcopy(declaration)
        for key in ('version_label','carrier','body','lineage'):value['identity'].pop(key,None)
        stripped.append(value)
    require(stripped[0]==stripped[1],'rsi_scope','Child changed an always-protected declaration field')
    before={v['path']:v['sha256'] for v in parent['identity']['body']};after={v['path']:v['sha256'] for v in child['identity']['body']}
    touched={p for p in before.keys()|after.keys() if before.get(p)!=after.get(p)}
    globs=[value[6:] for value in parent['evolution']['may_change'] if value.startswith('files:')]
    require(touched and all(any(fnmatch.fnmatchcase(path,pattern) for pattern in globs) for path in touched),'rsi_scope','Changed body file is outside parent mutable files globs')
    require(len(package['mutable_paths_touched'])==len(set(package['mutable_paths_touched'])) and set(package['mutable_paths_touched'])==touched and touched.issubset(target['mutable_paths']),'rsi_security_halt','Touched paths differ from actual child body or protected target')
    require(not (set(after.values()) & set(protected_body_hashes)),'rsi_no_copy','Child copied protected non-RSI body bytes')
    require(provenance['declaration_ref']==package['child_declaration_ref'] and provenance['parent_ref']==target['parent_ref'],'rsi_identity','Provenance names another candidate or prior implementation')
    require(session['target_profile_ref']==package['target_profile_ref'] and session['parent']==package['parent'] and session['parent_declaration_ref']==package['parent_declaration_ref'],'rsi_identity','Session parent/target mismatch')
    require(result['outcome']=='QUALIFIED' and result['qualified_by']!='none' and result['statistics'] is not None,'rsi_not_qualified','Only qualified signed results can enter admission')
    for key in ('parent','child','child_declaration_ref','referee_evidence_ref'):
        require(result[key]==package[key],'rsi_identity','Result/package mismatch: '+key)
    require(result['session_ref']==package['session_ref'] and referee['attempt_ref']==result['final_attempt_ref'],'rsi_identity','Final result/referee attempt mismatch')
    require(referee['mandatory_parent_tests_passed'] and referee['integrity_passed'] and referee['final_evaluations']==1 and not referee['violations'],'rsi_not_qualified','Mandatory protected final prerequisites did not pass')
    require(target['parent_declaration_ref']==package['parent_declaration_ref'],'rsi_identity','Target names another parent declaration')
    for key in ('configuration_ref','improver_ref','scoring_adapter_ref'):
        require(session[key]==target[key],'rsi_identity','Session differs from frozen target context')
    require(referee['target_ref']==package['target_profile_ref'] and referee['parent_ref']==target['parent_ref'] and referee['configuration_ref']==session['configuration_ref'],'rsi_identity','Referee target/parent body/configuration mismatch')
    genesis=record(session['chain_root_ref']);store.read_blob(session['hash_profile_ref'])
    require(genesis.get('session_id')==session['session_id'] and genesis.get('target_ref')==session['target_profile_ref'] and genesis.get('hash_profile_ref')==session['hash_profile_ref'],'rsi_chain','Genesis does not pin session, target and hash profile')
    require(genesis.get('interface_revision')=='M1-IF-009@r2','rsi_chain','New candidate evidence must freeze the current interface revision')
    require(not any('attempt' in key for key in genesis),'rsi_chain','Genesis cannot contain an attempt hash')
    previous=None;final=None;query_count=0;seen=set()
    for sequence,ref in enumerate(result['attempt_refs'],1):
        identity=(ref['id'],ref['sha256'])
        require(identity not in seen and ref!=session['chain_root_ref'],'rsi_chain','Attempt chain repeats an entry or its genesis')
        seen.add(identity)
        attempt=record(ref,'rsi-attempt')
        require(attempt['sequence']==sequence and attempt['previous_ref']==previous and attempt['session_id']==session['session_id'],'rsi_chain','Attempt sequence or immediate previous link is invalid')
        for key in ('chain_root_ref','hash_profile_ref','configuration_ref'):require(attempt[key]==session[key],'rsi_chain','Attempt session pin mismatch')
        require(attempt['target_ref']==session['target_profile_ref'] and attempt['parent_ref']==target['parent_ref'],'rsi_chain','Attempt target or parent body changed')
        require(query_count<=attempt['queries_used']<=session['limits']['session_query_limit'],'rsi_chain','Attempt query exposure decreased or exceeded the frozen session cap')
        query_count=attempt['queries_used']
        for evidence in attempt['failure_evidence_refs']+attempt['visible_evidence_refs']+attempt['observation_refs']:store.read_blob(evidence)
        for field in ('child_ref','diff_ref'):
            if attempt[field] is not None:store.read_blob(attempt[field])
        if ref==result['final_attempt_ref']:final=attempt
        previous=ref
    require(final is not None and result['attempts_used']==len(result['attempt_refs'])<=session['limits']['max_attempts'],'rsi_chain','Finalist is absent from the exact complete attempt chain')
    require(final['attempt_status']=='proposed' and not final['violations'],'rsi_not_qualified','A rejected or violating attempt cannot become the finalist')
    require(query_count<=result['queries_used']<=session['limits']['session_query_limit'],'rsi_chain','Terminal query exposure erased an actual query or exceeded the frozen cap')
    require(provenance['builder_ref']==result['final_attempt_ref'] and lineage.get('builder_ref')==result['final_attempt_ref'],'rsi_identity','Candidate builder is not its selected proposed attempt')
    require(final['diff_ref']==package['diff_ref'] and final['child_ref']==referee['child_ref'],'rsi_identity','Final diff/assessed child mismatch')
    diff=record(package['diff_ref']);store.read_blob(final['child_ref'])
    require(diff.get('format')=='ai4r-body-diff-v1' and isinstance(diff.get('files'),list),'rsi_diff','Unsupported protected body diff representation')
    diffpaths=[f.get('path') for f in diff['files']]
    require(len(diffpaths)==len(set(diffpaths)) and set(diffpaths)==touched,'rsi_diff','Diff paths do not equal actual changed body files')
    for file in diff['files']:
        path=file['path']
        for key,hashes in [('before_ref',before),('after_ref',after)]:
            ref=file.get(key)
            require((ref is None and path not in hashes) or isinstance(ref,dict) and ref.get('sha256')==hashes.get(path),'rsi_diff','Diff file pins disagree with exact declarations')
            if ref is not None:store.read_blob(ref)
    require(len(diff['files'])==1 and diff['files'][0]['before_ref']==target['parent_ref'] and diff['files'][0]['after_ref']==final['child_ref'] and final['child_ref']['sha256']!=target['parent_ref']['sha256'],'rsi_diff','Assessed mutable body differs from exact final diff bytes or aliases its parent')
    implementations=provenance['implementation_refs']
    for ref in implementations:store.read_blob(ref)
    require(set(after.values()).issubset({ref['sha256'] for ref in implementations}),'rsi_identity','Provenance is missing exact child implementation closure')
    stats=result['statistics'];policy=session['qualification'];pair=[p for p in referee['pairs'] if p['split']==target['splits']['hidden_final']]
    require(len(pair)==1,'rsi_not_qualified','There must be one hidden-final paired comparison')
    pair=pair[0];n=stats['fixture_units'];g=stats['gain_units'];loss=stats['loss_units']
    repeats=session['pass_count_repeats']
    require(repeats in (1,3),'rsi_not_qualified','Matched pass observations require one or three frozen repeats')
    def mean_sum(value,total):
        require(type(value) in (int,float) and math.isfinite(value) and 0<=value<=total,'rsi_not_qualified','Mean-score sum is outside its fixture bounds')
        exact=Fraction(round(value*repeats),repeats)
        require(float(exact)==value,'rsi_not_qualified','Mean-score sum does not encode the frozen matched-repeat grid')
        return exact
    for comparison in referee['pairs']:
        mean_sum(comparison['parent_passed'],comparison['total']);mean_sum(comparison['child_passed'],comparison['total'])
        require(comparison['gain_units']+comparison['loss_units']<=comparison['total'],'rsi_not_qualified','Paired directions exceed independent fixture units')
    parent_sum=mean_sum(stats['parent_passed'],n);child_sum=mean_sum(stats['child_passed'],n)
    require(n==pair['total'] and stats['parent_passed']==pair['parent_passed'] and stats['child_passed']==pair['child_passed'] and g==pair['gain_units'] and loss==pair['loss_units']==0 and g+loss<=n,'rsi_not_qualified','Signed final mean scores and independent paired directions disagree')
    gain=float((child_sum-parent_sum)/n)
    require(stats['pass_rate_gain']==gain,'rsi_not_qualified','Mean-score pass-rate gain does not recompute')
    require(0<policy['alpha']<=0.05 and policy['min_pass_rate_gain']>=0.05 and policy['min_timing_gain']>=0.1 and policy['noise_multiplier']>=3 and policy['warmup_batches']==5 and policy['paired_rounds']==7,'rsi_not_qualified','Frozen qualification policy widened a source threshold')
    p=sum(math.comb(g+loss,k) for k in range(g,g+loss+1))/(2**(g+loss)) if g+loss else None
    require(stats['p_value']==p,'rsi_not_qualified','Exact paired-binomial probability does not recompute')
    if result['qualified_by']=='pass_gain':
        require(g>0 and child_sum>parent_sum and gain>=policy['min_pass_rate_gain'] and p<=policy['alpha'],'rsi_not_qualified','Exact paired-binomial qualification failed')
    elif result['qualified_by']=='timing_tiebreak':
        timing=stats['timing'];require(timing is not None and g==0 and child_sum==parent_sum,'rsi_not_qualified','Timing cannot offset a mean-score or fixture regression')
        require(len(pair['parent_time_s'])==len(pair['child_time_s'])==7 and all(v>0 for v in pair['parent_time_s']+pair['child_time_s']),'rsi_not_qualified','Timing must have seven real paired durations')
        parent_median=statistics.median(pair['parent_time_s']);child_median=statistics.median(pair['child_time_s'])
        exact_relative=1-Fraction(str(child_median))/Fraction(str(parent_median))
        relative=float(exact_relative)
        require(timing['warmup_batches']==5 and timing['paired_rounds']==7 and timing['parent_median_s']==parent_median and timing['child_median_s']==child_median and timing['relative_gain']==relative,'rsi_not_qualified','Timing statistics do not recompute')
        require(timing['noise_multiplier']==policy['noise_multiplier'] and timing['calibrated_relative_noise']==target['scoring']['calibrated_relative_noise'] and timing['min_relative_gain']>=policy['min_timing_gain'] and exact_relative>=Fraction(str(timing['min_relative_gain'])) and exact_relative>Fraction(str(policy['noise_multiplier']))*Fraction(str(timing['calibrated_relative_noise'])),'rsi_not_qualified','Calibrated timing qualification failed')
    else:raise ResearchError('rsi_not_qualified','Unknown qualification mode')
    return {'session':session,'result':result,'referee':referee,'provenance':provenance,'parent':parent,'child':child,'touched':sorted(touched)}
