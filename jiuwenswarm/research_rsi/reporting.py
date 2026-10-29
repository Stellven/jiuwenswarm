"""Audience-safe aggregate exports and explicit incomplete requirement coverage."""
from datetime import datetime,timezone
import uuid


def evidence_export(attempt_ref,attempt,referee_ref,referee,*,validate):
    if attempt.get('schema_version')!='2.0.0' or attempt.get('attempt_status')!='proposed' or referee.get('schema_version')!='2.0.0':raise ValueError('Only a current proposed finalist may have paired evidence export')
    if referee['attempt_ref']!=attempt_ref or referee['parent_ref']!=attempt['parent_ref'] or referee['child_ref']!=attempt['child_ref']:raise ValueError('paired export identity mismatch')
    pairs=referee['pairs']
    summary='; '.join(f"parent mean-score sum {p['parent_passed']}/{p['total']}, child mean-score sum {p['child_passed']}/{p['total']}" for p in pairs)
    record={'schema_version':'1.0.0','id':'rsi_export:'+uuid.uuid4().hex,'attempt_ref':attempt_ref,'referee_ref':referee_ref,
        'parent_ref':attempt['parent_ref'],'child_ref':attempt['child_ref'],'summary':summary,
        'redactions':['Hidden fixture contents, case identities, answers, per-case outcomes and scoring implementation withheld.'],
        'violations':list(referee['violations'])}
    validate('rsi-evidence-export',record);return record


def completion_report(results,*,coverage,tests,modalities,verify,validate,onboarding=(),transfer_evidence=(),claim_transfer=False,
                      blockers=(),uncertainties=(),unavailable=(),containment_limitations=(),compiled_by='ai4r-rsi'):
    if not results:raise ValueError('completion report requires actual session results')
    for ref,result in results:verify(result)
    if 'text' in modalities and not any(t['test_id']=='text_native_path' and t['outcome']=='passed' and t['evidence_ref'] for t in tests):raise ValueError('text modality requires actual bounded native path evidence')
    if claim_transfer and (not transfer_evidence or not onboarding):raise ValueError('transfer claim requires independent held-out transfer and unrelated-target evidence')
    for test in tests:
        if test['outcome']!='not_run' and not test['evidence_ref']:raise ValueError('executed test has no evidence')
    record={'schema_version':'1.0.0','id':'rsi_completion:'+uuid.uuid4().hex,'session_result_refs':[ref for ref,result in results],
        'requirement_coverage':list(coverage),'executed_tests':list(tests),'modalities':list(modalities),
        'qualified_result_refs':[ref for ref,result in results if result['outcome']=='QUALIFIED'],
        'onboarding_evidence_refs':list(onboarding),'transfer_claim':'supported' if claim_transfer else 'none',
        'transfer_evidence_refs':list(transfer_evidence),'blockers':list(blockers),'uncertainties':list(uncertainties),
        'unavailable':list(unavailable),'containment_limitations':list(containment_limitations),'compiled_by':compiled_by,
        'recorded_at':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    validate('rsi-completion-report',record);return record
