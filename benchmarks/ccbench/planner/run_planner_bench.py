"""Plan-only benchmark. The sole model-call boundary is run --execute."""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from contextlib import contextmanager
from collections import Counter, defaultdict
from pathlib import Path
from library import ROOT, build_library, canonical, declared_payload, undeclared_view
import roots
import modelbench
from plan_integrity import DEFECTS, score_raw

MODELS = ('gpt-6-luna', 'gpt-6.1-sol')
OUTPUT_BUDGET = 'Output budget: at most 24000 characters. Do not use any tools, read files, execute commands, access networks, or delegate. Plan only; nothing in the proposed plan is executed.'


@contextmanager
def fresh_empty_directory(parent, prefix='empty-'):
    # tempfile on Windows creates a 0700 ACL that this managed workspace
    # cannot reopen. Inherit the workspace ACL with ordinary mkdir instead.
    parent = Path(parent).resolve()
    cwd = parent / (prefix + uuid.uuid4().hex)
    cwd.mkdir()
    try:
        yield str(cwd)
    finally:
        resolved = cwd.resolve()
        if not resolved.is_relative_to(parent) or resolved == parent:
            raise RuntimeError('Refusing cleanup outside the intended temporary root')
        shutil.rmtree(resolved)


def load_tasks(ids=None):
    # tasks.json and expected.json are inputs that live beside this file (ROOT); every output goes under --out.
    tasks = json.loads((ROOT / 'tasks.json').read_text('utf-8'))
    if ids:
        unknown = sorted(set(ids) - {t['id'] for t in tasks})
        if unknown:
            raise SystemExit('unknown task id(s): %s; known: %s' % (', '.join(unknown), ', '.join(t['id'] for t in tasks)))
        tasks = [t for t in tasks if t['id'] in set(ids)]
    return tasks


def task_text(task):
    # Identical bytes in both conditions, including actual supplied input text.
    return canonical(task)


SKILL_DETAILS = ('names', 'full')
SKILLPACK = ROOT.parent / 'planbench' / 'skillpack'


def skillpack_files(library=None):
    """[(relative path, text)] of the skillpack file behind each library capability, in library order, once each.

    Mapping (the one planbench/generate_skillpack.py used to write the pack): a capability `utility.calculate` is the
    tool file `tools/utility_calculate.py`; a capability whose pack entry is a skill folder is
    `skills/<name with . and _ turned into ->/SKILL.md` (for example `research.paper_summary` ->
    `skills/research-paper-summary/SKILL.md`). The pack's index SKILL.md and the planning skill are not included: the
    planner already has its own instructions. A capability with no file stops the run; it is never skipped silently.
    """
    names = []
    for item in undeclared_view(library):
        if item['name'] not in names:
            names.append(item['name'])
    out = []
    for name in names:
        tool = SKILLPACK / 'tools' / (name.replace('.', '_') + '.py')
        skill = SKILLPACK / 'skills' / (name.replace('.', '-').replace('_', '-') + '/SKILL.md')
        path = tool if tool.is_file() else skill
        if not path.is_file():
            raise SystemExit('no skillpack file for capability %s (looked for %s and %s)' % (name, tool, skill))
        out.append((path.relative_to(SKILLPACK).as_posix(), path.read_bytes().decode('utf-8').replace('\r\n', '\n')))
    return out


def full_skill_text(library=None):
    parts = ['\nFull text of each skill and tool file (the code and SKILL.md behind the listed names):']
    for rel, text in skillpack_files(library):
        parts.append('--- file: %s ---\n%s' % (rel, text.rstrip('\n')))
    return '\n'.join(parts) + '\n'


def make_prompt(task, condition, library=None, skill_detail='names'):
    lib = library or build_library()
    if condition == 'A':
        framing = lib['instructions'] + '\nDeclared planner payload:\n' + canonical(declared_payload(task, lib))
        request = 'Return exactly the pinned plan-proposal JSON, or the bounded INFEASIBLE: reply required by the planner instructions. Use suggested_checks for named output acceptance checks; retain the pinned schema.'
    elif condition == 'B':
        framing = 'You are a research planner. Choose a plan using this skill library:\n' + canonical(undeclared_view(lib))
        if skill_detail == 'full':
            framing += full_skill_text(lib)
        elif skill_detail != 'names':
            raise ValueError(skill_detail)
        request = '''Return exactly one structured JSON object {"nodes":[{"id":"unique_id","capability":"skill name","inputs":[{"name":"input name","source":"external:<supplied key> or <node>.<output>"}],"outputs":["output names"],"acceptance_criteria":["criterion naming an output port/field or check id"],"depends_on":["node ids"],"limits":{"time_s":0,"model_calls":0,"memory_mb":0},"covers":["Brief requirement, deliverable and evidence obligation IDs"]}]}. Include explicit input bindings, output names, dependencies, bounded limits and acceptance criteria for every node. Cover every mandatory Brief obligation. If required capability, input or budget is unavailable, return one line INFEASIBLE: naming the actual missing capability/input or exceeded ceiling, at most 300 characters. Invent no resources or permissions.'''
    else:
        raise ValueError(condition)
    return OUTPUT_BUDGET + '\n' + framing + '\n<task>\n' + task_text(task) + '\n</task>\n' + request + '\n' + OUTPUT_BUDGET


def digest(prompt):
    raw = prompt.encode('utf-8')
    return dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), characters=len(prompt))


def dry_plan(ids=None, out=None, skill_detail='names'):
    lib = build_library()
    records = []
    for task in load_tasks(ids):
        for cond in ('A', 'B'):
            records.append(dict(task=task['id'], condition=cond, **digest(make_prompt(task, cond, lib, skill_detail))))
    print(json.dumps(records, indent=2))
    if out:
        Path(out).mkdir(parents=True, exist_ok=True)
        write_json(Path(out) / 'dry-run.json', records)
    return records


def write_json(path, value):
    Path(path).write_bytes((json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))


def invoke_once(command, prompt, env):
    """One CLI invocation, no retries; timeout includes CLI startup and generation."""
    start = time.monotonic()
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding='utf-8', errors='replace', env=env)
    timed_out = False
    try:
        stdout, stderr = proc.communicate(prompt, timeout=300)
    except subprocess.TimeoutExpired:
        timed_out = True
        if os.name == 'nt':
            # Terminate the CLI tree, including a possible codex.cmd/node wrapper.
            subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True, timeout=10)
        proc.kill()
        stdout, stderr = proc.communicate(timeout=10)
    return dict(elapsed_s=time.monotonic() - start, returncode=proc.returncode, timed_out=timed_out,
        stdout_tail=stdout[-12000:], stderr_tail=stderr[-12000:],
        tokens_used=re.findall(r'tokens used\s*[:\r\n ]+([\d,]+)', stdout + '\n' + stderr, flags=re.I),
        # input/output stay None unless codex prints them; the total is never split by guesswork
        input_tokens=modelbench.parse_usage(stdout + '\n' + stderr)['input'],
        output_tokens=modelbench.parse_usage(stdout + '\n' + stderr)['output'])


def run(args):
    if not args.execute:
        raise SystemExit('Model calls require explicit run --execute. Use plan for an offline dry run.')
    if args.repeats < 1:
        raise SystemExit('--repeats must be positive')
    cli = roots.require_codex()
    outdir = Path(args.out)
    base = outdir / 'runs' / args.model
    resume = getattr(args, 'resume', False)
    if base.exists() and not resume:
        raise SystemExit('Run directory already exists; preserve it or move it before starting a new batch (or pass --resume to add the missing units).')
    base.mkdir(parents=True, exist_ok=resume)
    lib = build_library()
    tasks = load_tasks(getattr(args, 'task', None))
    skill_detail = getattr(args, 'skill_detail', 'names')
    manifest = dict(library=lib, tasks=tasks, expected=json.loads((ROOT / 'expected.json').read_text('utf-8')), repeats=args.repeats, model=args.model, skill_detail=skill_detail)
    if resume and (base / 'manifest.json').exists():
        # Same library, model, repeats and skill detail, or the units would not be comparable. The manifest then lists every task that has run.
        old = json.loads((base / 'manifest.json').read_text('utf-8'))
        for key in ('library', 'repeats', 'model', 'skill_detail'):
            if old.get(key, 'names' if key == 'skill_detail' else None) != manifest[key]:
                raise SystemExit('--resume refused: %s differs from the existing run in %s' % (key, base))
        seen = {x['id'] for x in tasks}
        manifest['tasks'] = [x for x in load_tasks() if x['id'] in seen or x['id'] in {y['id'] for y in old['tasks']}]
    # Freeze scorer inputs, including hidden labels, outside every model CWD.
    write_json(base / 'manifest.json', manifest)
    temp_root = outdir / '.tmp'
    temp_root.mkdir(exist_ok=True)
    for task in tasks:
        for repeat in range(1, args.repeats + 1):
            # Counterbalance the first condition to reduce order confounding.
            for cond in (('A', 'B') if repeat % 2 else ('B', 'A')):
                out = base / task['id'] / f'{cond}-r{repeat}'
                if resume and (out / 'run.json').exists():
                    print(f'{args.model} {task["id"]} {cond}-r{repeat}: skip (done)', flush=True)
                    continue
                if out.exists():
                    raise SystemExit('%s exists without run.json (interrupted); move it away to redo that unit' % out)
                out.mkdir(parents=True)
                prompt = make_prompt(task, cond, lib, skill_detail)
                (out / 'prompt.txt').write_bytes(prompt.encode('utf-8'))
                raw_path = out / 'reply.txt'
                env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
                metadata = dict(task=task['id'], condition=cond, repeat=repeat, model=args.model, skill_detail=skill_detail, prompt=digest(prompt))
                with fresh_empty_directory(temp_root) as cwd:
                    command = [cli, 'exec', '--skip-git-repo-check', '-m', args.model, '-s', 'read-only', '--ephemeral', '-C', cwd, '-o', str(raw_path), '-']
                    metadata.update(command=command, cwd_initially_empty=not any(Path(cwd).iterdir()))
                    started = time.monotonic()
                    try:
                        metadata.update(invoke_once(command, prompt, env))
                    except (OSError, subprocess.SubprocessError) as exc:
                        metadata.update(error=str(exc), elapsed_s=time.monotonic() - started)
                if not raw_path.exists():
                    raw_path.write_bytes(b'')
                metadata['raw_reply_sha256'] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
                write_json(out / 'run.json', metadata)
                print(f'{args.model} {task["id"]} {cond}-r{repeat}: recorded', flush=True)


def aggregate(rows):
    summary = {}
    for cond in ('A', 'B'):
        group = [r for r in rows if r['condition'] == cond]
        count = len(group)
        ac_total = sum(r['score']['acceptance_total'] for r in group)
        repeat_sets = defaultdict(list)
        for r in group:
            # Invalid JSON has no meaningful capability set; retain a unique
            # failure marker instead of crediting stable empty graphs.
            if 'parse_error' not in r['score']:
                repeat_sets[r['task']].append(tuple(r['score']['capability_set']))
        stability = []
        for tid in {r['task'] for r in group}:
            all_repeats = [r for r in group if r['task'] == tid]
            if len(all_repeats) > 1:
                sets = repeat_sets[tid]
                stability.append(max(Counter(sets).values(), default=0) / len(all_repeats))
        rejected = [r for r in group if not r['expected_feasible']]
        summary[cond] = dict(plans=count,
            validity_rate=sum(r['score']['valid'] for r in group) / count if count else None,
            defects_per_plan={d: sum(r['score']['counts'][d] for r in group) / count if count else None for d in DEFECTS},
            infeasible_handling_accuracy=sum(r['score']['infeasible_handling_correct'] for r in rejected) / len(rejected) if rejected else None,
            overall_feasibility_decision_accuracy=sum(r['score']['infeasible_handling_correct'] for r in group) / count if count else None,
            acceptance_machine_checkable_fraction=sum(r['score']['machine_checkable'] for r in group) / ac_total if ac_total else None,
            run_to_run_stability=sum(stability) / len(stability) if stability else None)
    return summary


def score(model, out):
    out = Path(out)
    base = out / 'runs' / model
    manifest_path = base / 'manifest.json'
    if not manifest_path.exists():
        raise SystemExit('No frozen run manifest found for ' + model)
    manifest = json.loads(manifest_path.read_text('utf-8'))
    tasks = {t['id']: t for t in manifest['tasks']}
    rows = []
    for path in sorted(base.glob('*/*/reply.txt')):
        task = tasks[path.parent.parent.name]
        condition, repeat = path.parent.name.split('-r')
        expected = manifest['expected'][task['id']]
        scored = score_raw(path.read_text('utf-8-sig'), condition, task, expected, manifest['library'])
        rows.append(dict(task=task['id'], condition=condition, repeat=int(repeat), expected_feasible=expected['feasible'],
                         raw_reply=str(path.relative_to(out)), score=scored))
    summary = aggregate(rows)
    scores = out / 'scores'
    scores.mkdir(exist_ok=True)
    write_json(scores / (model + '.json'), dict(model=model, plans=rows, aggregate=summary))
    metrics = ['plans', 'validity_rate', 'infeasible_handling_accuracy', 'acceptance_machine_checkable_fraction', 'run_to_run_stability']
    table = ['| Metric | A declared | B undeclared |', '|---|---:|---:|']
    for metric in metrics:
        table.append(f'| {metric} | {summary["A"][metric]} | {summary["B"][metric]} |')
    for d in DEFECTS:
        table.append(f'| defects/plan: {d} | {summary["A"]["defects_per_plan"][d]} | {summary["B"]["defects_per_plan"][d]} |')
    text = '\n'.join(table) + '\n'
    (scores / (model + '.md')).write_bytes(text.encode('utf-8'))
    print(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    planner = sub.add_parser('plan', help='offline dry run: prompt digests and sizes only')
    planner.add_argument('--task', action='append', metavar='ID', help='only this task id (repeatable)')
    planner.add_argument('--out', type=Path, help='also write dry-run.json here')
    planner.add_argument('--skill-detail', choices=SKILL_DETAILS, default='names', help='arm B: names (default) or full skillpack file text')
    runner = sub.add_parser('run')
    runner.add_argument('--model', choices=MODELS, required=True)
    runner.add_argument('--repeats', type=int, default=1)
    runner.add_argument('--task', action='append', metavar='ID', help='only this task id (repeatable); default all 12')
    runner.add_argument('--out', type=Path, required=True, help='directory for runs/ and the temporary workspaces')
    runner.add_argument('--skill-detail', choices=SKILL_DETAILS, default='names', help='arm B: names (default) or full skillpack file text')
    runner.add_argument('--resume', action='store_true', help='keep an existing run directory and run only the units that have no run.json')
    runner.add_argument('--execute', action='store_true')
    scorer = sub.add_parser('score')
    scorer.add_argument('--model', choices=MODELS, required=True)
    scorer.add_argument('--out', type=Path, required=True, help='the --out used for run; scores/ is written here')
    args = parser.parse_args(argv)
    if args.command == 'plan':
        dry_plan(args.task, args.out, args.skill_detail)
    elif args.command == 'run':
        run(args)
    else:
        score(args.model, args.out)


if __name__ == '__main__':
    main()
