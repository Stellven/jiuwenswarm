"""Root scoring of original cache stdout against pinned public request traces."""
from __future__ import annotations
import hashlib
import os
import uuid
from pathlib import Path
from .cache_protocol import PROTOCOL, MAX_BYTES, require, parse_cache_dataset, parse_cache_output
from .contracts import ResearchError, validate
from .state import json_bytes

SCORE_KIND = 'cache-scoring-receipt'
SCORE_SCHEMA = 'urn:ai4r:private:cache-scoring-receipt:1'
PROFILE_FIELDS = {'protocol','public_dataset_ref','public_file','public_data_sha256','scorer_sha256','protocol_sha256','max_stdout_bytes'}


def validate_cache_profile(profile):
    require(type(profile) is dict and set(profile)==PROFILE_FIELDS and profile['protocol']==PROTOCOL and profile['public_file']=='data.json' and type(profile['max_stdout_bytes']) is int and profile['max_stdout_bytes']==MAX_BYTES, 'Closed cache scoring profile required')
    validate('Ref',profile['public_dataset_ref'])
    for key in ('public_data_sha256','scorer_sha256','protocol_sha256'):
        require(type(profile[key]) is str and len(profile[key])==64 and all(c in '0123456789abcdef' for c in profile[key]), 'Invalid cache profile digest')
    return profile


class RootCacheScorer:
    protocol = PROTOCOL
    def __init__(self, store, profile):
        require(os.name=='posix' and os.geteuid()==0, 'Cache scoring requires root custody')
        self.profile = dict(validate_cache_profile(profile))
        self.store = store
        from . import cache_protocol
        require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==profile['scorer_sha256'] and hashlib.sha256(Path(cache_protocol.__file__).read_bytes()).hexdigest()==profile['protocol_sha256'], 'Installed cache scorer differs from frozen source')

    def score(self, job, raw, public_resource):
        require(os.geteuid()==0 and 'trusted_scoring_ref' not in raw, 'Scoring is root owned and cannot be repeated')
        p = self.profile
        require(job.validation_ref==p['public_dataset_ref'] and self.store.read_record(p['public_dataset_ref'],contract_id='resource-snapshot')==public_resource, 'Cache public resource differs from exact issued job')
        files = public_resource['files']
        require(len(files)==1 and files[0]['path']==p['public_file'] and files[0]['artifact_ref']['sha256']==p['public_data_sha256'], 'Cache data differs from approved profile')
        public_raw = self.store.read_blob(files[0]['artifact_ref'])
        require(hashlib.sha256(public_raw).hexdigest()==p['public_data_sha256'], 'Cache public bytes changed')
        public = parse_cache_dataset(public_raw)
        require(raw.get('observed_runtime') is True and raw.get('job_id')==job.job_id and raw.get('contract_ref')==dict(job.contract_ref) and raw.get('invocation_id')==job.invocation_id, 'Exact observed original cache execution required')
        for key in ('sequence','role','repeat_index','seed','subject_ref'):
            expected = getattr(job,key)
            require(raw.get(key)==expected, 'Cache execution job selection differs')
        status, failure, observations, misses, metrics = 'unmeasured','execution_failed',None,None,{}
        requests = sum(len(t) for t in public['traces'].values())
        if raw.get('exit_code')==0 and raw.get('termination_reason')=='completed':
            try:
                observed = parse_cache_output(self.store.read_blob(raw['stdout_ref']),public,max_stdout_bytes=p['max_stdout_bytes'])
                observations = observed['results']
                key = 'unbounded_misses' if job.role=='baseline' else 'misses'
                require(job.role in {'baseline','treatment'}, 'Unknown cache measurement role')
                misses = sum(row[key] for row in observations.values())
                metrics = {'miss_ratio':misses/requests}
                status, failure = 'scored',None
            except ResearchError:
                failure = 'observation_invalid'
        record = {'schema':'ai4r-cache-scoring-receipt:1','id':'cache-score:'+uuid.uuid4().hex,
            **{key:getattr(job,key) for key in ('run_id','node_id','attempt_id','invocation_id','job_id','sequence','role','repeat_index','seed')},
            'contract_ref':dict(job.contract_ref),'subject_ref':dict(job.subject_ref),'validation_ref':dict(job.validation_ref),
            'prediction_ref':dict(raw['stdout_ref']), 'execution_identity_sha256':hashlib.sha256(json_bytes(raw)).hexdigest(),
            'public_data_sha256':p['public_data_sha256'],'scorer_sha256':p['scorer_sha256'],'protocol_sha256':p['protocol_sha256'],
            'source_id':public['source_id'],'unit':'requests','status':status,'failure_reason':failure,
            'sample_count':requests,'miss_count':misses,'observations':observations,'metrics':metrics}
        validate(SCORE_SCHEMA,record)
        ref = self.store.append_record(SCORE_KIND,record)
        require(self.store.record_kind(ref)==SCORE_KIND and self.store.read_record(ref)==record, 'Cache score publication lost original custody')
        return dict(raw,trusted_scoring_ref=ref)


def scored_empirical_row(raw, score):
    validate(SCORE_SCHEMA,score)
    original = {k:v for k,v in raw.items() if k!='trusted_scoring_ref'}
    require(score['execution_identity_sha256']==hashlib.sha256(json_bytes(original)).hexdigest() and score['prediction_ref']==raw['stdout_ref'], 'Cache original execution digest differs')
    for key in ('job_id','contract_ref','invocation_id','sequence','role','repeat_index','seed','subject_ref'):
        require(score[key]==raw[key], 'Cache score differs from original job')
    if score['status']=='scored':
        require(raw['exit_code']==0 and raw.get('termination_reason')=='completed' and score['failure_reason'] is None and type(score['miss_count']) is int and 0<=score['miss_count']<=score['sample_count'] and score['metrics']=={'miss_ratio':score['miss_count']/score['sample_count']}, 'Cache arithmetic or completion differs')
        observations=score['observations']
        require(type(observations) is dict and bool(observations), 'Cache observations absent')
        key='unbounded_misses' if raw['role']=='baseline' else 'misses'
        require(sum(r[key] for r in observations.values())==score['miss_count'] and sum(r['hits']+r['misses'] for r in observations.values())==score['sample_count'], 'Cache counts disagree with score')
        return {'sequence':raw['sequence'],'status':'measured','metrics':dict(score['metrics']),'unmeasured_metrics':{}}
    require(not score['metrics'] and score['miss_count'] is None and score['observations'] is None and score['failure_reason'] is not None, 'Unmeasured cache score claimed an observation')
    return {'sequence':raw['sequence'],'status':'unmeasured','metrics':{},'unmeasured_metrics':{'miss_ratio':'run_failed' if score['failure_reason']=='execution_failed' else 'metric_not_emitted'}}


def failed_empirical_row(raw):
    require(raw['exit_code']!=0 or raw.get('termination_reason')!='completed', 'Successful cache run requires its original root scoring receipt')
    reason={'timeout':'timeout','deadline':'timeout','resource_limit_exceeded':'resource_limit_exceeded','memory_limit':'resource_limit_exceeded','cpu_limit':'resource_limit_exceeded'}.get(raw.get('termination_reason'),'run_failed')
    return {'sequence':raw['sequence'],'status':'unmeasured','metrics':{},'unmeasured_metrics':{'miss_ratio':reason}}
