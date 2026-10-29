"""Finite job-scoped runner, offline referee and reproducible report commands."""
import argparse
import asyncio
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from .cases import schedule,validate_visible_case,ID
from .client import ResearchClient
from .evidence import canonical,write_once,read_verified,relative
from .ledger import Ledger
from .runner import Runner
from .referee import score_run
from .reports import build_report,markdown


def now():return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _root():return Path(os.environ.get('AI4R_QA_ROOT','/bench')).resolve(strict=True)


def _campaign(root,ident):
    from .campaign import load_campaign
    return load_campaign(root,ident)


async def run_campaign(args):
    root=_root();folder,campaign,cases=_campaign(root,args.campaign)
    schedule_path=folder/'schedule.json'
    planned=schedule(campaign,cases)
    if not schedule_path.exists() or json.loads(schedule_path.read_bytes())!=planned:raise ValueError('frozen host-prepared schedule absent or changed')
    result_root=root/'results'/args.campaign
    for name in ('campaign.json','schedule.json','module-map.json'):
        raw=(folder/name).read_bytes();destination=result_root/name
        if destination.exists():
            if destination.read_bytes()!=raw:raise ValueError('frozen campaign result identity changed')
        else:write_once(destination,raw)
    for pin in campaign['cases']:
        name='cases/'+pin['case_id']+'/case.json';raw=(folder/name).read_bytes();destination=result_root/name
        if destination.exists():
            if destination.read_bytes()!=raw:raise ValueError('frozen visible result case changed')
        else:write_once(destination,raw)
    job_path=Path(os.environ.get('AI4R_QA_JOB','/run/ai4r-qa/job.json'))
    job=json.loads(job_path.read_bytes())
    if job.get('campaign_id')!=args.campaign:raise ValueError('job grant does not authorize campaign')
    selected=[r for r in planned if r['module']==args.case and r['variant_id']==args.variant and (not args.run_id or r['run_id']==args.run_id)]
    if not selected:raise ValueError('requested case/variant/run is outside the frozen schedule')
    ledger=Ledger(root/'results'/args.campaign/'ledger.sqlite')
    client=None
    if args.case!='rsi':
        try:
            transport=None
            if job.get('delivery_fault') is not None:
                import httpx
                from .client import DropSubmitReplyOnce
                fault=job['delivery_fault']
                if (not isinstance(fault,dict) or set(fault)!={'mode','run_id'} or fault['mode']!='discard_successful_submit_reply_once'
                    or len(selected)!=1 or selected[0]['run_id']!=fault['run_id']):raise ValueError('Transport fault differs from the exact frozen scheduled job')
                transport=DropSubmitReplyOnce(httpx.AsyncHTTPTransport(retries=0,trust_env=False))
            client=ResearchClient(job['base_url'],job['token_file'],transport=transport)
        except (OSError,ValueError,KeyError):pass
    runner=Runner(client,ledger,root/'results'/args.campaign)
    try:
        for row in selected:
            case=next(c for c in cases if c['case_id']==row['case_id'])
            # Inventory/submission are immutable per scheduled run and populated
            # by the host launcher; a stale or missing row cannot be reused.
            inventory=json.loads(read_verified(folder,job['inventories'][row['run_id']]))
            if (inventory['run_id'],inventory['repeat_index'])!=(row['run_id'],row['repeat_index']):raise ValueError('inventory is not fresh for scheduled attempt')
            companions=[]
            if row['run_id'] in job.get('orchestration_inventories',{}):
                observed=json.loads(read_verified(folder,job['orchestration_inventories'][row['run_id']]))
                if (observed['campaign_id'],observed['run_id'],observed['repeat_index'],observed['role'])!=(row['campaign_id'],row['run_id'],row['repeat_index'],'orchestration'):raise ValueError('Separate orchestration inventory identity differs')
                if observed['inventory_id']!=inventory['inventory_id']:companions.append(observed['inventory_id'])
            if args.case=='rsi':
                from .adapters.rsi import JobClient
                try:
                    grant=job['rsi_jobs'][row['run_id']]
                    port=JobClient(job['rsi_socket'],job['rsi_peer_uid'],grant['job_ref'])
                except (OSError,ValueError,KeyError):
                    runner.blocked(row,case,inventory,'protected_rsi_job_grant_unavailable',additional_inventory_ids=companions);continue
                await runner.execute_rsi(row,case,inventory=inventory,port=port,signer=grant['signer'],deadline_s=case['budgets']['wall_time_s'],additional_inventory_ids=companions)
            else:
                submission=json.loads(read_verified(folder,job['submissions'][row['run_id']]))
                execute=runner.execute_evaluation if case['entry_mode'] in {'node_replay','single_cc'} else runner.execute
                await execute(row,case,inventory=inventory,submission=submission,expected_pins=job['expected_readiness_pins'],deadline_s=case['budgets']['wall_time_s'],additional_inventory_ids=companions)
    finally:
        if client:await client.close()
        ledger.close()
    return 0


def runner_main(argv=None):
    supplied=list(sys.argv[1:] if argv is None else argv)
    if not supplied or (supplied[0] != 'launch' and not
            (supplied[0] == 'run' and '--campaign' in supplied and '--case' in supplied)):
        from .sequential import main
        return main(supplied)
    if supplied and supplied[0]=='launch':
        from .launcher import launch_main
        return launch_main(supplied[1:])
    parser=argparse.ArgumentParser(prog='benchmark-runner');sub=parser.add_subparsers(dest='command',required=True)
    run=sub.add_parser('run');run.add_argument('--campaign',required=True);run.add_argument('--case',required=True,choices=['capsule','verifier','routing','rsi']);run.add_argument('--variant',default='baseline');run.add_argument('--run-id',default=None)
    args=parser.parse_args(supplied)
    try:return asyncio.run(run_campaign(args))
    except (ValueError,OSError,KeyError):print('BLOCKED: frozen campaign, job grant, host inventory or supported runtime prerequisite unavailable.',file=sys.stderr);return 2


def referee_main(argv=None):
    parser=argparse.ArgumentParser(prog='benchmark-referee');sub=parser.add_subparsers(dest='command',required=True)
    score=sub.add_parser('score');score.add_argument('--campaign',required=True);score.add_argument('--oracle-version',required=True);score.add_argument('--case',choices=['capsule','verifier','routing','rsi'])
    args=parser.parse_args(argv);root=_root()
    # Referee must have no app control credential even if a misconfigured launch
    # inherited the runner environment. Explicitly refuse rather than ignore it.
    if any(k in os.environ for k in ('AI4R_QA_JOB','AI4R_APP_TOKEN','AI4R_RSI_JOB_SOCKET','AI4R_RSI_CUSTODIAN_SOCKET')) or any(k.endswith('_API_KEY') for k in os.environ):return 2
    try:
        folder,campaign,cases=_campaign(root,args.campaign)
        label_root=Path(os.environ.get('AI4R_QA_LABELS','/bench-private/labels'))
        from .frozen_records import strict_json
        scheduled={row['run_id']:row for row in schedule(campaign,cases)}
        retained=[]
        for path in sorted((root/'results'/args.campaign/'runs').glob('*/run_record.json')):
            run=strict_json(path.read_bytes())
            row=scheduled.get(run.get('run_id')) if isinstance(run,dict) else None
            if row is None or path.parent.name!=row['run_id']:raise ValueError('retained result is not an exact scheduled run')
            for key in ('run_id','campaign_id','case_id','case_version','config_id','repeat_index'):
                if type(run.get(key)) is not type(row[key]) or run[key]!=row[key]:raise ValueError('retained result differs from the frozen schedule')
            retained.append((path,run))
        for case in cases:
            if args.case and case['module']!=args.case:continue
            from .campaign import load_referee
            label_bytes=read_verified(label_root,{'path':case['referee_ref']['label_id']+'/referee.json','sha256':case['referee_ref']['referee_sha256']})
            label=load_referee(case,label_bytes)
            if args.oracle_version!=case['oracle_version']:raise ValueError('oracle version differs from frozen case')
            for run_path,run in retained:
                if run['case_id']!=case['case_id']:continue
                # Independent oracle observations must be signed/frozen by the
                # protected referee preparation, never read from product output.
                observation_path=label_root/case['referee_ref']['label_id']/'observations'/run['run_id']/(args.oracle_version+'.json')
                observations=json.loads(observation_path.read_bytes()) if observation_path.exists() else {}
                from .independent_oracles import evaluate_checks
                from .frozen_records import FrozenRecords
                if run['entry_mode'] in {'node_replay','single_cc'}:
                    # E2/E3 private kinds never enter the ordinary E1 decoder.
                    # The referee performs no HTTP operation and has no token.
                    from .evaluation_records import EvaluationRecords
                    frozen=None
                    try:
                        request_rows=[r for r in run['exports'] if r['path']=='evaluation-request.json']
                        if len(request_rows)!=1:raise ValueError('original evaluation request pin unavailable')
                        submitted=strict_json(read_verified(run_path.parent,request_rows[0]))
                        if submitted['request_id']!=run['request_id'] or submitted['campaign_id']!=run['campaign_id'] or submitted['case_id']!=run['case_id']:
                            raise ValueError('private export differs from exact scheduled run')
                        frozen=EvaluationRecords.from_frozen(run_path.parent/'evaluation-export',request_id=run['request_id'],
                            campaign_id=run['campaign_id'],expected_request=submitted,inventory=run['exports']).require_complete()
                        if frozen.request['entry_point']!=('E2' if run['entry_mode']=='node_replay' else 'E3'):
                            raise ValueError('private export entry point differs from scheduled run')
                    except (ValueError,OSError,KeyError,TypeError):frozen=None
                else:
                    export_path=run_path.parent/'export'
                    frozen=FrozenRecords(export_path) if export_path.exists() else None
                independent=evaluate_checks(label,frozen,run,run_path.parent)
                # Mechanical checks must execute the frozen independent oracle;
                # a prefilled producer/self-score cannot replace it. Human and
                # eligible benchmark-judge records use their separate authority.
                deterministic={c['check_id'] for c in label['mandatory_checks'] if c['kind']=='deterministic'}
                observations={k:v for k,v in observations.items() if k not in deterministic}
                observations.update(independent)
                result=score_run(run,label,observations,scored_at=now(),oracle_version=args.oracle_version)
                write_once(root/'scores'/args.campaign/run['run_id']/args.oracle_version/'score_record.json',result)
        return 0
    except (ValueError,OSError,KeyError):return 2


def report_main(argv=None):
    parser=argparse.ArgumentParser(prog='benchmark-report');sub=parser.add_subparsers(dest='command',required=True)
    build=sub.add_parser('build');build.add_argument('--campaign',required=True);build.add_argument('--audience',choices=['referee','public'],required=True)
    args=parser.parse_args(argv);root=_root()
    try:
        folder,campaign,cases=_campaign(root,args.campaign)
        paths=sorted((root/'scores'/args.campaign).glob('*/*/score_record.json'));scores=[json.loads(p.read_bytes()) for p in paths]
        # Frozen metadata is reused for byte-identical rebuilds; no current clock
        # or random identifier enters an already selected report candidate.
        report=build_report(scores,audience=args.audience,report_id=args.campaign+'_'+args.audience,generated_at=campaign['frozen_at'],pins=campaign['pins'],source_scores=[str(p.relative_to(root)) for p in paths],case_metadata={c['case_id']:c for c in cases})
        destination=root/'reports'/(args.campaign+'_'+args.audience)
        for name,value in [('report.json',canonical(report)),('report.md',markdown(report).encode())]:
            path=destination/name
            if path.exists():
                if path.read_bytes()!=value:raise ValueError('report candidate changed; use new report identity')
            else:write_once(path,value)
        return 0
    except (ValueError,OSError,KeyError):return 2
