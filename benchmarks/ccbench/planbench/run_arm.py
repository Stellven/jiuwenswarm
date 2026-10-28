"""Run one arm of the plan benchmark over some tasks. Real model calls need --execute; --stub needs no model.

  python -B planbench/run_arm.py run  --arm cc|skill --label LABEL --out DIR [--tasks a,b,c] [--stub VARIANT | --execute]
  python -B planbench/run_arm.py score --label LABEL --out DIR   (model-free; see score.py)

Arms
  cc     AI4R research.planner worker (NativePlanner on JiuwenSwarm, in process through cclib's Harness)
         with the CC library snapshot, then the real planner_checks, verifier and gate. --cc-planner direct
         swaps in cclib's DirectPlanner (the labelled fallback). Model calls go through the codex exec
         transport (gpt-6.1-sol, medium effort), one at a time, no retries.
  skill  native JiuwenSwarm (nativetask/run_native_task.py, Docker) given the same request and the same
         capabilities as ordinary tool files and skill folders (planbench/skillpack). --skill-transport
         codex is the labelled fallback: one tool-free codex exec turn with the same pack text in the prompt.

Every attempt is kept under DIR/runs/LABEL/ARM/TASK/. Nothing is overwritten and nothing is retried. Nothing is written
beside the source: scratch stores, staging and the native ledger live under DIR too.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import roots  # noqa: E402

REPO = roots.code_root()
for p in (str(HERE), str(ROOT), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)
import prompts
import stubs

MODEL = 'gpt-6.1-sol'
PYTHON = sys.executable
SKILLPACK = HERE / 'skillpack'
RUN_NATIVE = ROOT / 'nativetask' / 'run_native_task.py'
CODEX_COMMAND = None        # tests substitute a fake CLI here (list of argv prefix); never set for real runs


def jload(path):
    return json.loads(Path(path).read_text('utf-8'))


def dump(path, value):
    Path(path).write_bytes((json.dumps(value, indent=1, ensure_ascii=False, sort_keys=True, default=str) + '\n').encode('utf-8'))


def load_tasks(ids=None):
    tasks = jload(HERE / 'tasks.json')
    if ids:
        by = {t['id']: t for t in tasks}
        unknown = [i for i in ids if i not in by]
        if unknown:
            raise SystemExit('unknown task ids: %s' % unknown)
        tasks = [by[i] for i in ids]
    return tasks


def planner_library():
    spec = importlib.util.spec_from_file_location('planner_library', ROOT / 'planner' / 'library.py')
    mod = sys.modules.get('planner_library') or importlib.util.module_from_spec(spec)
    if 'planner_library' not in sys.modules:
        sys.modules['planner_library'] = mod
        spec.loader.exec_module(mod)
    return mod.build_library()


# ------------------------------------------------------------------------------------------------
# harness pieces that keep every write inside planbench/
# ------------------------------------------------------------------------------------------------

def _harness_classes():
    from cclib.harness import Harness, CodexModel, ScriptedModel, transport_text
    from jiuwenswarm.research.state import SQLiteRunStore

    class PBHarness(Harness):
        """cclib's Harness with its scratch store under planbench/.scratch (cclib writes under cclib/)."""
        def __init__(self, base):
            self.variant = None
            self.directory = Path(base) / ('store-' + uuid.uuid4().hex)
            for name in ('state', 'artifacts/sha256', 'inputs'):
                os.makedirs(self.directory / name, exist_ok=True)
            for n in range(256):
                os.makedirs(self.directory / 'artifacts' / 'sha256' / ('%02x' % n), exist_ok=True)
            self.store = SQLiteRunStore(self.directory)

    class PBCodex(CodexModel):
        """codex exec transport with medium reasoning effort; evidence kept under the run directory."""
        def __init__(self, model_name, evidence, execute=False):
            super().__init__(model_name, execute=execute)
            self.evidence = Path(evidence)
            self.command = list(CODEX_COMMAND) if CODEX_COMMAND else [roots.require_codex()]

        async def __call__(self, prompt, system=None):
            text = transport_text(prompt, system)
            d = self.evidence / ('call-%02d' % (len(self.records) + 1))
            (d / 'empty').mkdir(parents=True, exist_ok=False)
            reply = d / 'reply.txt'
            (d / 'prompt.txt').write_bytes(text.encode('utf-8'))
            argv = self.command + ['exec', '--skip-git-repo-check', '-m', self.model_name, '-c', 'model_reasoning_effort="medium"',
                                   '-s', 'read-only', '--ephemeral', '-C', str(d / 'empty'), '-o', str(reply), '-']
            rec = dict(argv=argv, directory=str(d), tokens=None, raw_reply=None, returncode=None,
                       prompt_sha256=hashlib.sha256(text.encode('utf-8')).hexdigest())
            self.records.append(rec)
            started = time.monotonic()
            proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    cwd=str(d / 'empty'), env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8'))
            try:
                out, err = await asyncio.to_thread(proc.communicate, text.encode('utf-8'), timeout=300)
            except subprocess.TimeoutExpired:
                if os.name == 'nt':
                    await asyncio.to_thread(subprocess.run, ['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True, timeout=10)
                else:
                    proc.kill()
                out, err = await asyncio.to_thread(proc.communicate, timeout=10)
                rec['error'] = 'timeout'
            rec['elapsed_s'] = time.monotonic() - started
            rec['returncode'] = proc.returncode
            (d / 'stdout.txt').write_bytes(out)
            (d / 'stderr.txt').write_bytes(err)
            log = (out + b'\n' + err).decode('utf-8', 'replace')
            counts = re.findall(r'(?im)tokens used\s*[:=]?\s*([\d,]+)', log)
            if counts:
                rec['tokens'] = int(counts[-1].replace(',', ''))
            if reply.exists():
                rec['raw_reply'] = reply.read_bytes().decode('utf-8')
            if rec.get('error') or proc.returncode or rec['raw_reply'] is None:
                from jiuwenswarm.research.contracts import ResearchError
                raise ResearchError('model_process_failed', 'codex exec failed (%s); evidence %s' % (rec.get('error') or proc.returncode, d))
            return rec['raw_reply']

    return PBHarness, PBCodex, ScriptedModel


def verifier_ok(prompt, system):
    """Scripted semantic-review reply used only in --stub runs (structural PASS on every criterion)."""
    criteria = json.loads(system.split('Criteria for this output:\n', 1)[1])
    return {'findings': [{'criterion_id': c['criterion_id'], 'outcome': 'PASS', 'reason': 'stub review'} for c in criteria],
            'uncertainties': [], 'limitations': [], 'required_correction': None}


# ------------------------------------------------------------------------------------------------
# CC arm
# ------------------------------------------------------------------------------------------------

async def run_cc(task, gold, out, args, lib):
    import copy
    import cclib.harness as H
    PBHarness, PBCodex, ScriptedModel = _harness_classes()
    scratch = Path(args.out) / '.scratch'
    scratch.mkdir(parents=True, exist_ok=True)
    h = PBHarness(scratch)
    patched = None
    try:
        snap, policy = lib['library_snapshot'], lib['plan_policy']
        inputs = {'brief': task['brief'], 'library_snapshot': snap, 'resource_inventory': task['resource_inventory'], 'plan_policy': policy}
        refs = {k: h.capture(v) for k, v in inputs.items()}
        catalog = copy.deepcopy(lib['capsule_contracts'])
        catalog['library_snapshot_ref'] = refs['library_snapshot']
        for c in catalog['capsules']:
            c['declaration_ref'] = h.capture(c['declaration'])
        inputs['capsule_contracts'] = catalog
        refs['capsule_contracts'] = h.capture(catalog)
        if args.stub:
            plan = stubs.neutral(task, gold, args.stub)
            reply = stubs.to_cc_reply(plan, task, refs, lib)
            def respond(prompt, system):
                # worker generations (first, and the bounded repair) get the stub plan; reviews get a structural PASS
                return verifier_ok(prompt, system) if system and 'Criteria for this output:' in system else reply
            model = ScriptedModel([respond] * 8)
            label = 'stub (%s), planner=%s' % (args.stub, args.cc_planner)
        else:
            model = PBCodex(args.model, out / 'codex', execute=True)
            label = 'real model, planner=%s' % args.cc_planner
        if args.cc_planner == 'native':
            from jiuwenswarm.research.native import NativePlanner
            patched = H.DirectPlanner
            H.DirectPlanner = NativePlanner          # run_stage copies the worker's globals with this name
        started = time.monotonic()
        result = await h.run_stage('planner', inputs, args.model, model=model, input_refs=refs)
        elapsed = time.monotonic() - started
    finally:
        if patched is not None:
            H.DirectPlanner = patched
        h.close()
    worker_calls = [c for c in result['calls'] if c['role'] == 'worker']
    raw = worker_calls[-1]['raw_reply'] if worker_calls and worker_calls[-1].get('raw_reply') is not None else ''
    tokens = [c.get('tokens') for c in result['calls']]
    rec = dict(arm='cc', task=task['id'], label=label, status=result['status'], delivered=result['status'] == 'advance',
               reasons=result['reasons'][:20], reply=raw, replies=[c.get('raw_reply') for c in worker_calls],
               check_results=[{k: r.get(k) for k in ('check_id', 'outcome', 'reason')} for r in result['check_results']],
               model_calls=len(result['calls']), tokens=sum(tokens) if tokens and all(t is not None for t in tokens) else None,
               tokens_known=sum(t is not None for t in tokens), elapsed_s=elapsed,
               calls=[{k: c.get(k) for k in ('role', 'tokens', 'error', 'directory', 'elapsed_s', 'returncode')} for c in result['calls']])
    return rec


# ------------------------------------------------------------------------------------------------
# skill arm
# ------------------------------------------------------------------------------------------------

def pack_text():
    parts = [(SKILLPACK / 'skills' / 'plan-research-workflow' / 'SKILL.md').read_text('utf-8'),
             (SKILLPACK / 'SKILL.md').read_text('utf-8')]
    for p in sorted((SKILLPACK / 'tools').glob('*.py')):
        parts.append('File tools/%s:\n%s' % (p.name, p.read_text('utf-8')))
    for p in sorted((SKILLPACK / 'skills').glob('*/SKILL.md')):
        if p.parent.name != 'plan-research-workflow':
            parts.append('File skills/%s/SKILL.md:\n%s' % (p.parent.name, p.read_text('utf-8')))
    return '\n\n'.join(parts)


def skill_codex_prompt(task):
    return ('You have these skills and tools.\n\n' + pack_text() + '\n\n--- Task ---\n' + prompts.request_with_format(task))


async def run_skill_codex(task, gold, out, args):
    _, PBCodex, _ = _harness_classes()
    prompt = skill_codex_prompt(task)
    (out / 'prompt.txt').write_bytes(prompt.encode('utf-8'))
    if args.stub:
        plan = stubs.neutral(task, gold, args.stub)
        reply, calls, tokens, label = stubs.to_skill_reply(plan), [], None, 'stub (%s), transport=codex' % args.stub
    else:
        model = PBCodex(args.model, out / 'codex', execute=True)
        started = time.monotonic()
        try:
            reply = await model(prompt)
        except Exception as exc:
            return dict(arm='skill', task=task['id'], status='failed', delivered=False, error=str(exc), reply='', model_calls=1,
                        tokens=model.records[-1].get('tokens') if model.records else None, label='skill via codex exec (fallback)')
        calls, tokens = model.records, model.records[-1].get('tokens')
        label = 'skill via codex exec, tool-free single turn (fallback, not native JiuwenSwarm)'
    return dict(arm='skill', task=task['id'], status='completed', delivered=True, reply=reply, model_calls=len(calls) if calls else (0 if args.stub else 1),
                tokens=tokens, label=label, prompt_sha256=hashlib.sha256(prompt.encode('utf-8')).hexdigest())


def native_out(args):
    return Path(args.out) / 'nativetask'


def native_ledger(args):
    # An initialized value_schedule ledger. Create one with:  run_native_task.py init-ledger --out <DIR>/nativetask
    return args.ledger or native_out(args) / 'ledger.sqlite3'


def native_command(task, out, args, attempt, execute):
    stage = out / 'staging'
    (stage / 'inputs').mkdir(parents=True, exist_ok=True)
    (stage / 'task.txt').write_bytes(prompts.request_with_format(task).encode('utf-8'))
    (stage / 'inputs' / 'NOTE.txt').write_bytes(b'No input files. The supplied inputs are written in the task text.\n')
    cmd = [PYTHON, '-B', str(RUN_NATIVE), 'run' if execute else 'plan', '--task-file', str(stage / 'task.txt'), '--inputs-dir', str(stage / 'inputs'),
           '--skill-dir', str(SKILLPACK), '--ledger', str(native_ledger(args)), '--out', str(native_out(args)), '--attempt-id', attempt, '--binary', args.binary or roots.codex_bin() or 'codex',
           '--model', args.model, '--wall-s', '600', '--max-calls', '80']
    if execute:
        cmd.append('--execute')
    return cmd


async def run_skill_native(task, gold, out, args):
    attempt = re.sub(r'[^A-Za-z0-9_-]', '-', 'pb-%s-%s' % (args.label, task['id']))[:95]
    cmd = native_command(task, out, args, attempt, execute=True)
    started = time.monotonic()
    env = dict(os.environ, PYTHONPATH=str(REPO), PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1', MSYS_NO_PATHCONV='1')
    proc = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, env=env, timeout=1500)
    (out / 'native.stdout').write_bytes(proc.stdout)
    (out / 'native.stderr').write_bytes(proc.stderr)
    session = native_out(args) / 'sessions' / attempt
    final = session / 'final-message.txt'
    reply = final.read_text('utf-8') if final.exists() else ''
    usage = jload(session / 'usage.json') if (session / 'usage.json').exists() else []
    toks = [(u.get('usage') or {}) for u in usage]
    tokens = sum((t.get('input_tokens') or 0) + (t.get('output_tokens') or 0) for t in toks) if toks else None
    return dict(arm='skill', task=task['id'], status='completed' if reply else 'failed', delivered=bool(reply), reply=reply, returncode=proc.returncode,
                model_calls=len(usage), tokens=tokens, elapsed_s=time.monotonic() - started, session=str(session),
                label='skill via native JiuwenSwarm (nativetask), skills+tool files', error=None if reply else 'no final message; see native.stderr')


# ------------------------------------------------------------------------------------------------

async def run_all(args, lib):
    tasks = load_tasks(args.tasks.split(',') if args.tasks else None)
    gold = jload(HERE / 'referee' / 'gold.json')
    base = Path(args.out) / 'runs' / args.label / args.arm
    for task in tasks:
        out = base / task['id']
        if out.exists():
            raise SystemExit('refusing to overwrite %s' % out)
        out.mkdir(parents=True)
        (out / 'request.txt').write_bytes((prompts.request_with_format(task) if args.arm == 'skill' else task['request']).encode('utf-8'))
        if args.arm == 'cc':
            rec = await run_cc(task, gold, out, args, lib)
        elif args.skill_transport == 'native' and not args.stub:
            rec = await run_skill_native(task, gold, out, args)
        else:
            rec = await run_skill_codex(task, gold, out, args)
        rec.update(model=args.model, stub=args.stub, effort='medium')
        (out / 'reply.txt').write_bytes((rec.get('reply') or '').encode('utf-8'))
        dump(out / 'record.json', rec)
        print('%s %s: status=%s delivered=%s calls=%s tokens=%s' % (args.arm, task['id'], rec.get('status'), rec.get('delivered'), rec.get('model_calls'), rec.get('tokens')), flush=True)


def dry(args):
    tasks = load_tasks(args.tasks.split(',') if args.tasks else None)
    for t in tasks:
        text = prompts.request_with_format(t) if args.arm == 'skill' else t['request']
        line = {'arm': args.arm, 'task': t['id'], 'request_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(), 'request_bytes': len(text.encode('utf-8'))}
        if args.arm == 'skill' and args.skill_transport == 'codex':
            line['prompt_sha256'] = hashlib.sha256(skill_codex_prompt(t).encode('utf-8')).hexdigest()
        if args.arm == 'skill' and args.skill_transport == 'native':
            out = Path(args.out) / '.scratch' / ('dry-' + t['id'])
            line['command'] = native_command(t, out, args, 'DRY', execute=False)
        print(json.dumps(line))
    print('dry run: no model call was made. Add --execute for a real run or --stub VARIANT for a scripted one.')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--arm', choices=('cc', 'skill'), required=True)
    r.add_argument('--label', required=True)
    r.add_argument('--tasks', help='comma-separated task ids (default: all 12)')
    r.add_argument('--model', default=MODEL, choices=(MODEL, 'gpt-6-luna'))
    r.add_argument('--stub', choices=stubs.VARIANTS, help='scripted replies, no model')
    r.add_argument('--execute', action='store_true', help='real model calls')
    r.add_argument('--cc-planner', choices=('native', 'direct'), default='native')
    r.add_argument('--skill-transport', choices=('native', 'codex'), default='native')
    r.add_argument('--ledger', type=Path, default=None, help='native skill arm only; default <out>/nativetask/ledger.sqlite3 (must be initialized)')
    r.add_argument('--binary', default=None, help='codex executable for the native skill arm (default: AI4R_CODEX_BIN, then PATH)')
    r.add_argument('--out', type=Path, required=True, help='every output (runs, scratch, staging, native ledger) is written under this directory')
    s = sub.add_parser('score')
    s.add_argument('--label', required=True)
    s.add_argument('--out', type=Path, required=True, help='the --out used for run')
    args = ap.parse_args(argv)
    if args.cmd == 'score':
        import score
        return score.main(args.label, args.out)
    if args.stub and args.execute:
        raise SystemExit('--stub and --execute are exclusive')
    if not args.stub and not args.execute:
        return dry(args)
    lib = planner_library() if args.arm == 'cc' else None     # builds with its own event loop
    asyncio.run(run_all(args, lib))


if __name__ == '__main__':
    main()
