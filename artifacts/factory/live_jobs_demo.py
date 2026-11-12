"""Operator live check of durable jobs (T03 acceptance): run with the real host queue.

  python artifacts/factory/live_jobs_demo.py submit   # client 1: submit a real build, print handle, exit (disconnect)
  python artifacts/factory/live_jobs_demo.py check    # client 2 (new process): duplicate submit + status until done
  python artifacts/factory/live_jobs_demo.py cancel   # submit a second build, cancel it, observe the stop

Every step appends to artifacts/factory/live-jobs-receipt.jsonl. Not an agent run; an operator receipt.
"""
import json, os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jiuwenswarm.factory.store import Store, NotFound
from jiuwenswarm.factory.builder import Builder
from jiuwenswarm.factory.jobs import Jobs

HOME = Path(os.environ.get('FACTORY_HOME', Path.home() / '.jiuwenswarm-factory'))
TASK = 'operator-live-jobs-1'
LOG = Path(__file__).with_name('live-jobs-receipt.jsonl')
SRC = dict(path=str(HOME / 'agent-workspace/llama.cpp'),
           commit='690e4713a55bae8dd6b40de3ccbdc8d7ea7e05f8', tree='43f95b1706aa65f50a3d3b74856cd1be3ddcaaa3')
REQ = dict(target='jetson-orin', source=SRC, tag='factory/llamacpp:livejobs-1', deadline_s=3600,
           env=dict(CUDA_HOME='/usr/local/cuda'))
CANCEL_REQ = dict(REQ, tag='factory/llamacpp:livejobs-cancel-2')


def log(event, **kw):
    rec = dict(event=event, t=time.time(), pid=os.getpid(), **kw)
    with LOG.open('a') as f:
        f.write(json.dumps(rec, sort_keys=True) + '\n')
    print(json.dumps(rec, sort_keys=True))


def store():
    s = Store(HOME)
    try:
        s.get_task(TASK)
    except NotFound:
        s.create_task(dict(task_id=TASK, objective='Operator live receipt: durable build survives client disconnect; '
                           'duplicate submit; observed cancellation', target={'profile': 'jetson-orin'}))
    return s


def brief(a):
    return {k: a.get(k) for k in ('attempt_id', 'state', 'jobq_id', 'idem_key', 'fingerprint')}


cmd = sys.argv[1]
s = store()
if cmd == 'submit':
    t0 = time.time()
    a = Builder(s).submit(TASK, REQ, 'livejobs-build-1')
    log('submitted', submit_s=round(time.time() - t0, 3), attempt=brief(a))
    log('client_exit', note='client process exits now; job continues under the host jobq supervisor')
elif cmd == 'check':
    a = Builder(s).submit(TASK, REQ, 'livejobs-build-1')
    log('duplicate_submit_same_key_same_request', attempt=brief(a),
        jobq_jobs_named=sum(1 for p in Jobs(s).jobq_dir.glob('job-*.json')
                            if json.loads(p.read_text())['name'] == 'factory:' + a['attempt_id']))
    try:
        Builder(s).submit(TASK, dict(REQ, tag='factory/llamacpp:livejobs-1-changed'), 'livejobs-build-1')
        log('changed_request_same_key', result='UNEXPECTED_ACCEPT')
    except Exception as exc:  # KeyConflict expected
        log('changed_request_same_key', result=type(exc).__name__, message=str(exc)[:200])
    while True:
        a = Builder(s).status(a['attempt_id'])
        if a['state'] in {'succeeded', 'failed', 'cancelled', 'unknown'}:
            break
        time.sleep(15)
    log('observed_terminal_by_new_client', attempt=brief(a), result=Builder(s).result(a['attempt_id']))
elif cmd == 'cancel':
    a = Builder(s).submit(TASK, CANCEL_REQ, 'livejobs-cancel-2')
    log('submitted_for_cancel', attempt=brief(a))
    while Builder(s).status(a['attempt_id'])['state'] != 'running':
        time.sleep(2)
    time.sleep(25)  # let the build start compiling
    log('running_before_cancel', attempt=brief(Builder(s).status(a['attempt_id'])))
    a = Builder(s).cancel(a['attempt_id'])
    log('cancel_observed', attempt=brief(a), history=[h.get('state') for h in a.get('history', [])],
        cleanup_state=a.get('cleanup_state'))
