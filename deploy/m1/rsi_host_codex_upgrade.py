"""Stopped, qualified host-policy upgrades; no inference or ledger rewriting.

Plan requires the old exact source/proof, a new actual offline wire proof, and
operator authorization. Apply archives originals, claims before replacement,
and publishes completion last. Incomplete transitions block every relay load.
"""
from __future__ import annotations
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from deploy.m1 import rsi_host_codex_recovery as guard

ROOT=guard.ROOT
RUN=guard.RUN
QUALIFICATION=guard.QUALIFICATION


def need(value):
    if not value: raise ValueError('Stopped qualified policy upgrade prerequisite unavailable')


def _records(root=ROOT):
    root=Path(root); claims=root/'policy-upgrades'; result=[]
    if not claims.exists(): return result
    guard.custody(claims,directory=True,mode=0o700)
    for directory in sorted(claims.iterdir()):
        guard.custody(directory,directory=True,mode=0o700)
        plan_raw=guard.read(directory/'plan.json'); plan=guard.document(plan_raw)
        claim_raw=guard.read(directory/'claim.json'); claim=guard.document(claim_raw)
        done=guard.document(guard.read(directory/'complete.json'))
        need(plan.get('schema')=='ai4r-host-codex-policy-upgrade-plan:1'
             and guard.digest(plan_raw)==directory.name
             and claim=={'schema':'ai4r-host-codex-policy-upgrade-claim:1','plan_sha256':directory.name}
             and done=={'schema':'ai4r-host-codex-policy-upgrade-complete:1',
                         'plan_sha256':directory.name,'claim_sha256':guard.digest(claim_raw),
                         'profile_sha256':plan['successor_profile_sha256']})
        for name,pin in plan['archive_sha256'].items():
            need('/' not in name and '\\' not in name and guard.digest(guard.read(directory/name))==pin)
        old=guard.document(guard.read(directory/'profile.before.json'))
        new=guard.document(guard.read(directory/'profile.after.json'))
        need(guard.digest(guard.read(directory/'profile.before.json'))==plan['prior_profile_sha256']
             and guard.digest(guard.read(directory/'profile.after.json'))==plan['successor_profile_sha256']
             and old['policy_sha256']==plan['prior_policy_sha256']
             and new['policy_sha256']==plan['successor_policy_sha256']
             and old['catalog']==new['catalog'] and old['session']==new['session'])
        result.append(plan)
    return result


def verify_upgrade_complete(root=ROOT):
    records=_records(root)
    if not records:return
    by_old={row['prior_policy_sha256']:row for row in records}
    need(len(by_old)==len(records))
    need(len({row['successor_policy_sha256'] for row in records})==len(records))
    tips=set(row['successor_policy_sha256'] for row in records)-set(by_old)
    need(len(tips)==1)
    current=next(iter(tips)); seen=set()
    by_new={row['successor_policy_sha256']:row['prior_policy_sha256'] for row in records}
    while current in by_new:
        need(current not in seen); seen.add(current);current=by_new[current]
    need(len(seen)==len(records) and current not in seen)
    profile=guard.document(guard.read(Path(root)/'profile.json'))
    need(profile['policy_sha256'] in tips)
    tip=next(row for row in records if row['successor_policy_sha256']==profile['policy_sha256'])
    need(guard.digest(guard.read(Path(root)/'profile.json'))==tip['successor_profile_sha256'])


def policy_ancestor(root,current,ancestor):
    verify_upgrade_complete(root)
    links={row['successor_policy_sha256']:row['prior_policy_sha256'] for row in _records(root)}
    seen=set()
    while current in links and current not in seen:
        seen.add(current);current=links[current]
        if current==ancestor:return True
    return False


def _policy(source,profile):
    catalog=profile['catalog']; binding={key:catalog[key] for key in ('gateway_id','backend','transport')}
    binding['model']=catalog['models'][0]
    q=profile['qualification']
    value={'schema':'ai4r-rsi-host-codex-policy:1','model':'gpt-6.1-sol','reasoning_effort':'medium',
           'binding_sha256':guard.digest(guard.encoded(binding)),
           'qualification_sha256':guard.digest(guard.encoded(q)),
           'source_sha256':{name:guard.digest((Path(source)/'jiuwenswarm'/name).read_bytes()) for name in guard.SOURCE_PATHS}}
    return dict(value,sha256=guard.digest(guard.encoded(value)))


def _qualification(proof_raw):
    proof=guard.document(proof_raw)
    return {'schema':'ai4r-rsi-host-codex-no-tools:1','native_version':proof['native_version'],
            'binary_sha256':proof['native_binary_sha256'],'helper_sha256':proof['helper_source_sha256'],
            'model_catalog_sha256':proof['cases'][0]['catalog_source_sha256'],
            'model':'gpt-6.1-sol','reasoning_effort':'medium','proof_sha256':guard.digest(proof_raw),
            'tools_count':0,'functions_count':0,'additional_tools_count':0,'tool_names':[]}


def prepare(proof_path,prior_proof_path,prior_source,authorization,*,root=ROOT,run=RUN,qualification=QUALIFICATION):
    need(os.name=='posix' and os.geteuid()==0 and isinstance(authorization,str) and 1<=len(authorization)<=4096)
    root=Path(root);run=Path(run);qualification=Path(qualification)
    # Boot RPC restoration follows the completed persistent transition.
    need(not os.path.lexists(run))
    guard.verify_recovery_complete(root);verify_upgrade_complete(root)
    old_raw=guard.read(root/'profile.json');old=guard.document(old_raw)
    oldq_raw=guard.read(qualification,mode=0o400);oldq=guard.document(oldq_raw)
    need(oldq==old['qualification'])
    prior=_policy(prior_source,old);need(prior['sha256']==old['policy_sha256'])
    oldproof=Path(prior_proof_path).read_bytes();newproof=Path(proof_path).read_bytes()
    need(len(oldproof)<=2*1024*1024 and len(newproof)<=2*1024*1024
         and guard.digest(oldproof)==oldq['proof_sha256'])
    guard.no_tools(oldq,guard.document(oldproof),prior['source_sha256'])
    newq=_qualification(newproof)
    from jiuwenswarm.research_rsi.host_codex_backend import validate_qualification,validate_host_catalog
    validate_host_catalog(old['catalog']);validate_qualification(newq,old['catalog'])
    source=Path(__file__).resolve().parents[2]
    new=dict(old,qualification=newq);successor=_policy(source,new)
    guard.no_tools(newq,guard.document(newproof),successor['source_sha256'])
    need(successor['sha256']!=prior['sha256'])
    new['policy_sha256']=successor['sha256'];new_raw=guard.encoded(new)
    ledger=root/'relay/requests.sqlite3';guard.custody(ledger)
    before=guard.digest(ledger.read_bytes())
    from jiuwenswarm.research.local_model_relay import LocalModelRelay
    relay=LocalModelRelay.__new__(LocalModelRelay);relay.runtime=root/'relay';relay.recovery_policy_sha256=prior['sha256']
    db=sqlite3.connect('file:'+str(ledger)+'?mode=ro',uri=True)
    try:
        need(db.execute('PRAGMA integrity_check').fetchone()==('ok',))
        rows=list(db.execute('SELECT id,digest,result FROM requests'))
        for ident,digest,result in rows:
            need(result is not None)
            if guard.document(result).get('outcome')=='outcome_unknown':
                relay._validate_disposition(ident,digest,result)
    finally:db.close()
    need(guard.digest(ledger.read_bytes())==before)
    archive={'profile.before.json':old_raw,'profile.after.json':new_raw,'qualification.before.json':oldq_raw,
             'qualification.after.json':guard.encoded(newq),'proof.before.json':oldproof,'proof.after.json':newproof,
             'policy.before.json':guard.encoded(prior),'policy.after.json':guard.encoded(successor)}
    plan={'schema':'ai4r-host-codex-policy-upgrade-plan:1','prior_policy_sha256':prior['sha256'],
          'successor_policy_sha256':successor['sha256'],'prior_profile_sha256':guard.digest(old_raw),
          'successor_profile_sha256':guard.digest(new_raw),'ledger_sha256':before,'ledger_rows':len(rows),
          'authorization':authorization,'model_calls':0,'catalog_and_session_preserved':True,
          'archive_sha256':{name:guard.digest(raw) for name,raw in archive.items()}}
    return plan,archive


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('plan','apply'))
    parser.add_argument('--proof',type=Path,required=True);parser.add_argument('--prior-proof',type=Path,required=True)
    parser.add_argument('--prior-source',type=Path,required=True);parser.add_argument('--authorization',required=True)
    parser.add_argument('--review-sha256')
    args=parser.parse_args()
    with ExitStack() as stack:
        stack.enter_context(guard.runtime_lock())
        from jiuwenswarm.research.local_model_recovery import RuntimeLock
        relay_lock=RuntimeLock(ROOT/'relay');stack.callback(relay_lock.close)
        plan,archive=prepare(args.proof,args.prior_proof,args.prior_source,args.authorization)
        raw=guard.encoded(plan);sha=guard.digest(raw)
        if args.command=='apply':
            need(args.review_sha256==sha)
            upgrades=ROOT/'policy-upgrades';guard._directory(upgrades)
            directory=upgrades/sha;need(not directory.exists());guard._directory(directory)
            guard.write_new(directory/'plan.json',raw)
            claim=guard.encoded({'schema':'ai4r-host-codex-policy-upgrade-claim:1','plan_sha256':sha})
            guard.write_new(directory/'claim.json',claim)
            for name,data in archive.items():guard.write_new(directory/name,data)
            guard.replace(QUALIFICATION,archive['qualification.after.json'],mode=0o400)
            guard.replace(ROOT/'profile.json',archive['profile.after.json'])
            need(guard.digest((ROOT/'relay/requests.sqlite3').read_bytes())==plan['ledger_sha256'])
            guard.write_new(directory/'complete.json',guard.encoded({'schema':'ai4r-host-codex-policy-upgrade-complete:1',
                'plan_sha256':sha,'claim_sha256':guard.digest(claim),'profile_sha256':plan['successor_profile_sha256']}))
            verify_upgrade_complete()
        print(json.dumps({'status':'UPGRADE_'+('APPLIED' if args.command=='apply' else 'PLANNED'),
                          'plan_sha256':sha,**plan},sort_keys=True))

if __name__=='__main__':main()