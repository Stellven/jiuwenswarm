#!/usr/bin/env python3
"""Operator-orchestrated pilot/main proof driver; no LLM is claimed here.

The parent task already contains the explicitly admitted policy and seed report.
For live-agent operation use the existing mission supervisor and factory CCs.
"""
from __future__ import annotations
import argparse
from contextlib import ExitStack
import fcntl
import json
from pathlib import Path
import subprocess
import time

from jiuwenswarm.factory.contract import atomic_json
from jiuwenswarm.factory.loop import FactoryLoop
from jiuwenswarm.factory.mission_supervisor import boot_id, mission_root
from jiuwenswarm.factory.store import NotFound, Store


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home',type=Path,required=True)
    parser.add_argument('--task',required=True)
    parser.add_argument('--evidence-id',action='append',required=True)
    parser.add_argument('--hypothesis-id',default='measure_prefill_chunk')
    parser.add_argument('--pilot-template',default='prefill-pilot')
    parser.add_argument('--main-template',default='prefill-main')
    parser.add_argument('--operator-host-quiet',action='store_true',help='Own control/supervisor locks, verify no running factory control containers, publish honest host quiet receipts')
    parser.add_argument('--poll-s',type=float,default=5)
    args=parser.parse_args()
    if not .1<=args.poll_s<=30:parser.error('--poll-s must be 0.1..30')
    home=args.home.expanduser().resolve()
    # Hold actual controller and supervisor locks while operator-host receipts
    # are valid; close Store connections before every poll wait.
    with ExitStack() as stack:
        if args.operator_host_quiet:
            for path in (home/'controller.lock',home.parent/'factory-supervisor.lock'):
                handle=stack.enter_context(path.open('a'))
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        evidence=args.evidence_id
        for index,template in enumerate((args.pilot_template,args.main_template),1):
            cycle_id='operator-'+('pilot' if index==1 else 'main')
            with Store(home) as store:
                loop=FactoryLoop(store,args.task)
                cycles=loop.status()['cycles']
                selected=next((c for c in cycles if c['cycle_id']==cycle_id),None)
                if selected is None:
                    rev=store.get_task(args.task)['current_decision_rev']
                    selected=loop.select(cycle_id,evidence,args.hypothesis_id,template,rev)
                    store.append_observation(args.task,dict(kind='operator_orchestration',
                        values=dict(cycle_id=cycle_id,driver='run-factory-campaign.py',
                            mode='operator_host' if args.operator_host_quiet else 'external_supervisor',llm_agent=False),
                        limitations='Explicit operator script choices; not autonomous agent evidence.'))
                sent=loop.execute(cycle_id)
                deadline=loop.status()['deadline']
            if args.operator_host_quiet and sent['state']!='collected':
                process=subprocess.run(['docker','ps','--filter','label=factory.mission.nonce','--format','{{.ID}}'],
                    capture_output=True,text=True,check=True,timeout=30)
                if process.stdout.strip():
                    raise RuntimeError('Factory control container still running; refusing host quiet receipt')
                root=mission_root(home,args.task)
                receipt=dict(attempt_id=sent['attempt_id'],control_stopped=True,boot_id=boot_id(),
                    recorded_at=time.time(),mode='operator_host',llm_agent=False,
                    proof=dict(controller_lock_held=True,supervisor_lock_held=True,running_factory_controls=[]),
                    limitation='Host operator orchestrates the campaign; no fabricated Docker control exit.')
                atomic_json(root/'quiet'/(sent['attempt_id']+'.json'),receipt)
            while True:
                with Store(home) as store:
                    loop=FactoryLoop(store,args.task)
                    collected=loop.collect(cycle_id)
                    if collected['state']=='collected':
                        print(json.dumps(dict(cycle_id=cycle_id,child_task_id=collected['child_task_id'],
                            attempt_id=collected['attempt_id'],result=collected['result'],
                            evidence_id=collected['evidence_id']),allow_nan=False),flush=True)
                        break
                    if time.time()>=deadline:
                        loop.stop('Operator campaign deadline exhausted; pending attempt retained')
                        raise TimeoutError('Campaign budget exhausted; reconcile using the same cycle ID')
                time.sleep(args.poll_s)
            if index==1 and collected['result'].get('analysis',{}).get('verdict')!='pilot_ok':
                with Store(home) as store:
                    FactoryLoop(store,args.task).stop('Pilot did not pass; main campaign not justified')
                return 1
            evidence=list(dict.fromkeys([*args.evidence_id,collected['evidence_id']]))
        return 0


if __name__=='__main__':
    raise SystemExit(main())
