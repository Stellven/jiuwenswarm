"""Custodian-owned paired final comparison; original parent is immutable."""
import uuid
import hashlib
import json
import math
from .records import encoded
from .statistics import qualify
from .custody import ExposureError


class Referee:
    def __init__(self,ledger,store,signer,paired_evaluate,validate):
        self.ledger,self.store,self.signer,self.paired_evaluate,self.validate=ledger,store,signer,paired_evaluate,validate
    async def final(self,session,attempt_ref,target_ref,parent_ref,child_ref,configuration_ref,*,repeats,qualification,mandatory_passed,integrity_passed):
        attempt=self.store.get(attempt_ref)
        self.validate('rsi-attempt',attempt)
        if attempt.get('schema_version')!='2.0.0' or attempt.get('attempt_status')!='proposed':raise ValueError('Only a current proposed attempt may enter final comparison')
        if any(attempt.get(k)!=v for k,v in {'session_id':session,'target_ref':target_ref,'parent_ref':parent_ref,'child_ref':child_ref,'configuration_ref':configuration_ref}.items()):raise ValueError('Final comparison differs from the exact proposed attempt')
        target=self.store.get(target_ref)
        fingerprint=hashlib.sha256(encoded({'attempt_ref':attempt_ref,'target_ref':target_ref,'parent_ref':parent_ref,'child_ref':child_ref,
            'configuration_ref':configuration_ref,'repeats':repeats,'qualification':qualification})).hexdigest()
        reservation=self.ledger.reserve(session,'original-parent-final','final',fingerprint=fingerprint)
        if reservation['state']=='complete':
            prior=json.loads(reservation['result']);return prior['decision'],prior['evidence_ref']
        if not reservation['fresh']:raise ExposureError('final sealed; reconcile existing protected evidence without replay')
        self.ledger.db.execute('UPDATE actions SET state=? WHERE session=? AND id=?',('evaluating',session,'original-parent-final'))
        capture=await self.paired_evaluate(parent_ref,child_ref,'hidden_final',repeats,configuration_ref)
        times=[*capture.get('parent_times',[]),*capture.get('child_times',[])]
        if (capture.get('warmups')!=5 or len(capture.get('parent_times',[]))!=7 or len(capture.get('child_times',[]))!=7
                or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in times)
                or capture.get('timing_unavailable_reason')):
            self.store.put({'schema':'ai4r-rsi-final-measurement-incomplete:1','session_id':session,
                'attempt_ref':attempt_ref,'target_ref':target_ref,'capture':capture,
                'reason':'Required source paired timing is missing or unstable; no certifiable referee signature'})
            raise ValueError('Required comparable final timing is unavailable; final remains sealed')
        decision=qualify(capture['parent'],capture['child'],repeats=repeats,
            independent=capture['independent'],mandatory_passed=mandatory_passed,integrity_passed=integrity_passed,
            parent_times=capture.get('parent_times'),child_times=capture.get('child_times'),warmups=capture.get('warmups',0),calibrated_noise=capture.get('calibrated_noise'),
            min_pass_gain=qualification['min_pass_rate_gain'],alpha=qualification['alpha'],
            min_timing_gain=qualification['min_timing_gain'],noise_multiplier=qualification['noise_multiplier'])
        stats=decision['statistics']
        # Paired totals/directions come only from the actual independently
        # captured fixture repetitions, never caller-supplied summary fields.
        pairs=[{'split':target['splits']['hidden_final'],'total':stats['fixture_units'],
            'parent_passed':stats['parent_passed'],'child_passed':stats['child_passed'],
            'gain_units':stats['gain_units'],'loss_units':stats['loss_units'],
            'parent_time_s':capture.get('parent_times',[]),'child_time_s':capture.get('child_times',[])}]
        record=self.signer.sign({'schema_version':'2.0.0','id':'referee:'+uuid.uuid4().hex,'attempt_ref':attempt_ref,
            'target_ref':target_ref,'parent_ref':parent_ref,'child_ref':child_ref,'pairs':pairs,
            'mandatory_parent_tests_passed':mandatory_passed,'integrity_passed':integrity_passed,'final_evaluations':1,
            'violations':capture.get('violations',[]),'configuration_ref':configuration_ref})
        self.validate('rsi-referee-evidence',record);ref=self.store.put(record)
        receipt={'evidence_ref':ref,'decision':decision}
        if capture.get('raw_measurement_ref') is not None:receipt['measurement_ref']=capture['raw_measurement_ref']
        self.ledger.complete(session,'original-parent-final',receipt)
        return decision,ref
