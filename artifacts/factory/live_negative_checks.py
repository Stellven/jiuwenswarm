"""Operator live negative checks against the real factory store / Docker / CC host (no GPU).

  python artifacts/factory/live_negative_checks.py   -> appends to artifacts/factory/live-negative-receipt.jsonl
"""
import json, os, sys, time, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from jiuwenswarm.factory.store import Store, ScopeDenied
from jiuwenswarm.factory.manager import Manager
from jiuwenswarm.ccv2 import ccv2

HOME = Path(os.environ.get('FACTORY_HOME', Path.home() / '.jiuwenswarm-factory'))
LOG = Path(__file__).with_name('live-negative-receipt.jsonl')
A1 = 'factory-aeaa9acc88d34a3ab1375154da98c385'
A2 = 'factory-d4b71bcce337406b96f627d469bec092'
OPS = 'operator-live-jobs-1'
A2_BUILD = '3216f10925b74aca8bfc8be140e65b7b'


def log(check, **kw):
    rec = dict(check=check, t=time.time(), **kw)
    with LOG.open('a') as f:
        f.write(json.dumps(rec, sort_keys=True) + '\n')
    print(json.dumps(rec, sort_keys=True))


s = Store(HOME)
# 1. Cross-task read without grant: operator task scope cannot read attempt-1 evidence.
try:
    s.scoped(OPS).read(A1, 'ea7c11f954974b1cb63ff5170e593266')
    log('cross_task_read_without_grant', result='UNEXPECTED_ALLOW')
except ScopeDenied as exc:
    log('cross_task_read_without_grant', result='ScopeDenied', message=str(exc)[:200])
except Exception as exc:
    log('cross_task_read_without_grant', result=type(exc).__name__, message=str(exc)[:200])

# 2. Wrong image for a build: present the om11 baseline image against attempt-2's build receipt.
m = Manager(s, HOME / 'lab-spool')
for label, ref in [('wrong_image_for_build', dict(tag='campaign/llamacpp:jetson-up1108-om11', id='sha256:2dcf9fe7e9ae051caf6607ee67db3dc5442f680480a62356ebbec8582cac2754')),
                   ('non_engine_base_image', dict(tag='nvcr.io/nvidia/l4t-cuda:12.6.11-runtime@sha256:49853e9fe2a0305efa51fcbb3426eea1bca658085f2d26bb40347711434849b1', id='sha256:49853e9fe2a0305efa51fcbb3426eea1bca658085f2d26bb40347711434849b1')),
                   ('right_tag_wrong_id', dict(tag='factory/llamacpp:d4b71bcc-thread-names-1', id='sha256:89ad6ac43df111090aab1ce8ace54009ae707550db39ed1b3f2614a84f0cd093'))]:
    try:
        r = m.admit(A2, ref, A2_BUILD)
        log(label, result='UNEXPECTED_ADMIT', admission=str(r)[:300])
    except Exception as exc:
        log(label, result=type(exc).__name__, code=getattr(exc, 'code', None), message=str(exc)[:240])

# 3. Capability call without its required grant through the real CC-v2 host.
with tempfile.TemporaryDirectory() as tmp:
    host = ccv2.Host(Path(tmp) / 'store', session_grants=['workspace.read'])
    release = host.prepare(ROOT / 'jiuwenswarm/factory/ccs/engine_inspector')
    try:
        receipt = host.call(release, 'verify_effective_config',
                            dict(image=dict(tag='campaign/llamacpp:jetson-up1108-om11'),
                                 env={'LLAMA_EXPERT_PREGATE': '1', 'LLAMA_EXPERT_PREGATE_K': '8'}))
        log('call_without_required_grant', result='receipt', state=receipt.get('state'),
            error=str(receipt.get('error'))[:240])
    except Exception as exc:
        log('call_without_required_grant', result=type(exc).__name__, code=getattr(exc, 'code', None),
            message=str(exc)[:240])
