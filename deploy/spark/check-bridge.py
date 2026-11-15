"""Replay an existing build request and reject changes without starting new work."""
import json,os
from pathlib import Path
from jiuwenswarm.factory.bridge import call
root=Path(os.environ['FACTORY_HOME']).parent
handle=json.loads((root/'results/port-build-handle.json').read_text())
r=handle['resources'];aid=handle['attempt_id']
args=['submit','--class',r['job_class'],'--name','factory:'+aid,'--timeout',str(r['timeout_s']),'--',*[v.replace('{attempt_id}',aid) for v in r['argv']]]
env=dict(handle['request']['env'],FACTORY_HOME=os.environ['FACTORY_HOME'])
queue=Path(r['jobq_dir']);before=len(list(queue.glob('job-*.json')))
result=call('queue',args=args,env=env,qdir=str(queue));result.check_returncode()
assert result.stdout.strip()==handle['jobq_id']
bad=list(args);bad[bad.index('--timeout')+1]='5399'
try:call('queue',args=bad,env=env,qdir=str(queue))
except ValueError as exc:assert 'persisted identity' in str(exc)
else:raise AssertionError('Changed request was accepted')
assert before==len(list(queue.glob('job-*.json')))
record=dict(replay_job_id=result.stdout.strip(),job_count_before=before,job_count_after=before,changed_deadline_rejected=True)
(root/'results/port-live-bridge-check.json').write_text(json.dumps(record,indent=2));print(json.dumps(record))
