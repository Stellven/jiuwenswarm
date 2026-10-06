"""Actual Windows readiness refusal; no credentials or provider calls printed."""
import asyncio
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(r'D:\research\ai_for_research\jiuwenswarm')))
from jiuwenswarm.ai4research.service import bootstrap
from jiuwenswarm.ai4research.characterization import run_campaign

ROOT=Path(r'D:\research\ai_for_research\jiuwenswarm')
PRIVATE=Path(r'D:\research\ai_for_research\.codex_work\trial-readiness-local-3')
OUT=ROOT/'docs/code/Missions/M0/M0-SYSTEM/evidence/RUN-20261006-RUNTIME-LOCAL-3'

async def main():
    app=None
    try:
        app,_,_,token_path=await bootstrap(PRIVATE/'state',PRIVATE/'workspace',origin='http://127.0.0.1:4311')
        ctx=app.identity.authenticate(token_path.read_text(encoding='utf-8'))
        readiness=await app.readiness()
        submitted=await app.submit(ctx,original_text='Compare batteries. Do not run experiments.',client_request_id='actual-windows-readiness-no-fallback')
        await asyncio.gather(*list(app.tasks.values()))
        projected=app.project(ctx,submitted['run_id'])
        stored=app.store.get_run(submitted['run_id'],caller_id=ctx.user_id)
        campaign=await run_campaign(app,ctx,corpus_path=ROOT/'tests/fixtures/ai4research/intent/characterization/locked-candidates.json',output_dir=PRIVATE/'characterization')
        assert readiness['ready'] is False and readiness['storage']['ready'] is True
        assert projected['status']=='ENVIRONMENT_BLOCKED' and projected['accepted_ref'] is None
        assert stored['attempts']==[]
        assert campaign['status']=='ENVIRONMENT_BLOCKED' and campaign['recorded_observations']==27
        assert all(case['observed']=='NOT_RUN' and case['actual_model_calls']==0 for case in campaign['outcomes'])
        result={'platform':'Actual Windows source service; required POSIX protected real IPC unavailable',
                'result':'PASS for environment refusal only; connected acceptance BLOCKED',
                'readiness':readiness,'projection':projected,'attempts':stored['attempts'],
                'real_provider_calls':0,'model_authentication':'Not probed because required secure IPC is unavailable.',
                'characterization':{'status':campaign['status'],'observations':27,'all_not_run':True,'provider_calls':0,'production_release':False},
                'limitations':['Windows ACL and protected IPC acceptance unestablished.','No real account or provider/model fidelity measurement.','Docker CLI absent from PATH and inspected standard installation paths; WSL Ubuntu has no detected docker/python3.']}
        (OUT/'actual-readiness.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'result':result['result'],'readiness':False,'attempts':0,'characterization_not_run':27}))
    finally:
        if app:
            try: await app.shutdown()
            finally:
                try: await app.bridge.close()
                finally: app.process_lease.release()

asyncio.run(main())
