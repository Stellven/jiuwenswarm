"""The factory planner: one self-contained TaskInput + full CC Library in, verified JSON TaskGraph out.

1. The host enumerates the full CC Library (``plan_catalog.prompt_view``) alongside eligible
   options (``plan_select``): hard filters, soft features, hardware risks, interference
   between builders and merge topologies (M1-M3).
2. The model makes minimal structural decisions directly in Plan IR (``plan_ir``):
   ``selected_capsules``, optional ``units`` grouping, ``preflight`` per hardware risk,
   ``merge`` option (when 2+ diff units), ``priority``, and autonomous ``steps``
   (step id, kind, objective, depends_on, bound CCs, optional limits/criteria/outputs).
3. The host deterministically compiles those steps into ``factory.node-contracts/1``
   and ``factory.plan/1`` (``plan_compile``), binding ``acceptance_criteria``, typed
   ports, verifiers, authority ceilings and limits.
4. Two internal verification layers prove the result, with up to 3 feedback rounds:
   * static checks: ``node_contract.problems``, ``planner.check_plan``, bridged M1 + M2 ``plan_checks``;
   * formal model checking: TLC explores every interleaving under ``tla/TaskGraphExec.tla``.

Only a graph that passes both layers and the ``init`` gate is emitted as verified JSON deliverables
(``contract.json``, ``plan.json``, ``graph.json``, ``verification.json``, ``task.json``).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid

from . import node_contract, plan_catalog, plan_checks, plan_compile, plan_ir, plan_select, tla_check, tla_graph
from . import requirements as req

PLANNER = plan_compile.PLANNER
ROUNDS = 3
TIMEOUT_S = 600
PLAN_ID = re.compile(r'^plan-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{6}$')

SYSTEM = """You are the planner of a software factory that optimizes inference engines.
The host has enumerated the full Capability Capsules (CC Library) catalog, eligible candidates,
hardware risks, interference and merge options. Autonomously choose the cohesive capsules,
design the TaskGraph step decomposition (steps, dependencies, bound CCs), and justify each choice;
the host compiles full contracts, proves static checks and internal TLC, and outputs standard JSON.
Reply with one JSON object (a factory.plan-ir/1) and nothing else."""

RULES = """How to decide (the host rejects decisions outside the offered options):
1. selected_capsules: non-empty list of {"capsule", "why"} picking the best cohesive set of capsules from selection.candidates to satisfy TaskInput.objective and TaskInput.acceptance_criteria (include every capsule in selection.must_include). Weigh name_match, acceptance type, slices and hardware. If no offered candidate can satisfy the task, reply with {"format": "factory.plan-ir/1", "unrealizable": {"why": "..."}} instead.
2. units (optional): by default each selected capsule is its own unit (selection.candidates[i].unit). Two builder capsules may share one unit only if they share an ontology slice.
3. preflight: one {"unit", "add", "why"} for every selected unit whose capsule has a hardware risk in selection.risks. add=true inserts an applicability inspect step (e.g. preflight_<unit>) before integration.
4. merge: {"option", "why"} choosing one of M1/M2/M3 when 2 or more code-diff units are selected; omit when 0 or 1 code-diff unit is selected. Read selection.interference: heavy shared files favour M2.
5. priority (optional): [[unit_a, unit_b], ...] to order one unit before another.
6. steps: non-empty ordered list of TaskGraph steps defining how the task executes end-to-end. Each step has {"id", "kind", "objective", "depends_on", "capsules"} (plus optional "limits", "criteria", "outputs", "workspace"):
   - kind must be one of inspect, investigate, integrate, merge, build, measure, decide, tune, accept, report, deliver.
   - capsules lists any CC Library capsule ids bound to that step (every capsule in selected_capsules must be bound to at least one step; helper CCs like factory.source_workbench, engine.precision_lab, analysis.* may also be bound directly).
   - Typical structure: inspect (inspect_engine) -> optional preflight_<unit> -> integrate_<unit> / tool build -> merge (combine) when >=2 diff units -> packaging build (build_candidate) -> optional measure/accept/tune -> terminal leaf deliver (kind="deliver", exactly one).
7. criteria (optional): {"<step id>": ["sentence", ...]} appended to that step's derived criteria.
8. limits (optional): {"<step id>": {"turns": n, "build_attempts": n, "time_s": n}}; only tighter than defaults in selection.defaults.
The host compiles your steps into node contracts, runs static checks and internal 2-pass TLC; any problem comes back to you."""


def _sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode('utf-8')).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False) + '\n',
                         encoding='utf-8')
    temporary.replace(path)


def build_prompt(task_input, selection, feedback=None, *, catalog=None):
    offered = dict(selection, defaults=plan_compile.DEFAULT_LIMITS)
    cc_view = plan_catalog.prompt_view(catalog or plan_catalog.load())
    parts = [RULES,
             '## Plan IR format\n' + plan_ir.__doc__.split('\n\n', 2)[2],
             '## TaskInput\n' + json.dumps(task_input, indent=1, ensure_ascii=False),
             '## Options the host offers (selection)\n' + json.dumps(offered, indent=1, ensure_ascii=False),
             '## Full CC Library (Capability Capsules)\n' + cc_view]
    if feedback:
        parts.append('## Your previous decisions were rejected\nFix every problem below and reply with the complete corrected Plan IR.\n'
                     + '\n'.join('- ' + p for p in feedback['problems'])
                     + ('\n\nYour previous reply:\n' + feedback['reply'][:20000] if feedback.get('reply') else ''))
    return '\n\n'.join(parts)


def parse_reply(text):
    """(ir, problem): the JSON object of a reply, or why there is none."""
    body = text.strip()
    fenced = re.search(r'```(?:json)?\s*(.*?)```', body, re.S)
    if fenced:
        body = fenced.group(1).strip()
    start, end = body.find('{'), body.rfind('}')
    if start < 0 or end < start:
        return None, 'the reply contains no JSON object'
    try:
        value = json.loads(body[start:end + 1])
    except ValueError as exc:
        return None, f'the reply is not valid JSON ({exc.msg} at character {exc.pos})'
    if not isinstance(value, dict) or value.get('format') != plan_ir.FORMAT:
        return None, f'the reply must be one object with "format": "{plan_ir.FORMAT}"'
    return value, None


def evaluate(ir, task_input, selection, catalog, tla_dir):
    """(layer, problems, warnings, verification, compiled) of one Plan IR."""
    try:
        document, plan, derivation = plan_compile.compile_plan(ir, selection, task_input, catalog=catalog)
    except plan_compile.CompileError as exc:
        return 'ir', exc.problems, [], None, None
    compiled = dict(node_contracts=document, plan=plan, derivation=derivation)
    problems, warnings = plan_checks.run(document, plan, task_input, catalog)
    if problems:
        return 'static', problems, warnings, None, compiled
    graph_tla = tla_graph.render_graph_tla(document, task_input, plan)
    compiled['graph_tla'] = graph_tla
    verification = tla_check.check_graph_tla(graph_tla, tla_dir)
    return ('tla' if verification['problems'] else 'passed'), verification['problems'], warnings, verification, compiled


def graph_preview(task_id, target_path, plan=None):
    """The factory.taskgraph/1 the factory seeds at init, through the same gate init uses."""
    from .planner import plan_for_task
    from .taskgraph import _node, _view
    task_stub = dict(task_id=task_id, contract_id=str(target_path))
    planner, nodes = plan_for_task(task_stub, plan)
    seeded = {n['node_id']: _node(n, 0) for n in nodes}
    return dict(_view(task_id, 0, seeded, []), planner=planner)


async def codex_invoke(prompt, system):
    """One governed, tool-free turn through the Codex subscription runtime."""
    from jiuwenswarm.server.runtime.codex_subscription.service import get_service
    result = await get_service().invoke_governed(prompt, system=system, timeout_s=TIMEOUT_S)
    return dict(text=result['text'], identity=result.get('identity'), usage=result.get('usage'))


def new_plan_id():
    return time.strftime('plan-%Y%m%dT%H%M%SZ-', time.gmtime()) + uuid.uuid4().hex[:6]


class PlanningRun:
    """One planning run in its directory. ``status.json`` is rewritten on every step."""

    def __init__(self, directory):
        self.directory = Path(directory)
        self.status = dict(state='pending', round=0, rounds=ROUNDS, created=time.time())

    def update(self, **changes):
        self.status.update(changes, updated=time.time())
        _write(self.directory / 'status.json', self.status)

    def round_dir(self, number):
        return self.directory / 'rounds' / str(number)


def _verification_summary(verification):
    if verification is None:
        return None
    return dict(passed=verification['passed'], runs=verification['runs'], execution_model=verification['execution_model'])


async def synthesize(task_input, directory, *, invoke=None, rounds=ROUNDS):
    """Plan one self-contained ``task_input`` into ``directory``. Returns the final status."""
    invoke = invoke or codex_invoke
    run = PlanningRun(directory)
    run.directory.mkdir(parents=True, exist_ok=True)
    _write(run.directory / 'requirements.json', task_input)
    found = req.problems(task_input)
    if found:
        run.update(state='rejected', error='Invalid TaskInput', problems=found, finished=time.time())
        return run.status
    try:
        _, jar = tla_check.tools()
    except tla_check.TlaUnavailable as exc:
        run.update(state='failed', error=f'TLC unavailable: {exc}', finished=time.time())
        return run.status
    catalog = plan_catalog.load()
    selection = plan_select.context(task_input, catalog)
    _write(run.directory / 'selection.json', selection)
    tid = req.input_id(task_input)
    if selection['unrealizable']:
        run.update(state='rejected', error='unrealizable_requirement: ' + '; '.join(selection['unrealizable']),
                   finished=time.time())
        return run.status
    record = dict(format='factory.plan-record/1', planner=PLANNER,
                  task_input=dict(id=tid, sha256=_sha(_canonical(task_input))),
                  catalog_sha256=catalog['sha256'], selection_sha256=_sha(_canonical(selection)),
                  tla=dict(spec_sha256=_sha(tla_check.SPEC.read_bytes()), tla2tools_sha256=_sha(Path(jar).read_bytes())),
                  rounds=[])
    run.update(state='running', requirements_id=tid, started=time.time())
    feedback = None
    for number in range(1, rounds + 1):
        prompt = build_prompt(task_input, selection, feedback, catalog=catalog)
        folder = run.round_dir(number)
        _write(folder / 'prompt.txt', prompt)
        run.update(round=number, phase='model')
        entry = dict(round=number, prompt_sha256=_sha(prompt), started=time.time())
        try:
            reply = await invoke(prompt, SYSTEM)
        except Exception as exc:
            reason = str(exc) or type(exc).__name__
            entry.update(finished=time.time(), error=reason)
            record['rounds'].append(entry)
            _write(folder / 'result.json', dict(error=reason))
            _write(run.directory / 'plan-record.json', record)
            run.update(state='failed', phase=None, error=f'Model call failed: {reason}', finished=time.time())
            return run.status
        _write(folder / 'reply.txt', reply['text'])
        record.setdefault('model', reply.get('identity'))
        ir, problem = parse_reply(reply['text'])
        if not problem and isinstance(ir, dict) and 'unrealizable' in ir:
            ir_problems = plan_ir.problems(ir, selection, catalog=catalog)
            if ir_problems:
                layer, problems, warnings, verification, compiled = 'ir', ir_problems, [], None, None
            else:
                reason = ir['unrealizable']['why']
                entry.update(finished=time.time(), reply_sha256=_sha(reply['text']), layer='unrealizable', problems=[reason])
                record['rounds'].append(entry)
                record['outcome'] = 'rejected'
                _write(folder / 'ir.json', ir)
                _write(folder / 'result.json', dict(layer='unrealizable', problems=[reason], warnings=[], nodes=0, verification=None))
                _write(run.directory / 'plan-record.json', record)
                run.update(state='rejected', phase=None, error=f'unrealizable_requirement: {reason}', finished=time.time())
                return run.status
        elif problem:
            layer, problems, warnings, verification, compiled = 'parse', [problem], [], None, None
        else:
            run.update(phase='checking')
            try:
                layer, problems, warnings, verification, compiled = await asyncio.to_thread(
                    evaluate, ir, task_input, selection, catalog, folder / 'tla')
            except tla_check.TlaUnavailable as exc:
                run.update(state='failed', phase=None, error=f'TLC unavailable: {exc}', finished=time.time())
                return run.status
        result = dict(layer=layer, problems=problems, warnings=warnings,
                      nodes=len(compiled['node_contracts']['nodes']) if compiled else 0,
                      verification=_verification_summary(verification))
        entry.update(finished=time.time(), reply_sha256=_sha(reply['text']), usage=reply.get('usage'),
                     layer=layer, problems=problems, warnings=warnings, verification=result['verification'])
        record['rounds'].append(entry)
        _write(folder / 'result.json', result)
        if ir is not None:
            _write(folder / 'ir.json', ir)
        _write(run.directory / 'plan-record.json', record)
        if not problems:
            try:
                return _accept(run, task_input, ir, compiled, warnings, record, verification)
            except ValueError as exc:
                problems = [f'jiuwenswarm-factory init would refuse this graph: {exc}']
                entry.update(layer='init', problems=problems)
                _write(folder / 'result.json', dict(result, layer='init', problems=problems))
                _write(run.directory / 'plan-record.json', record)
        feedback = dict(problems=problems, reply=reply['text'])
        run.update(last_problems=problems)
    run.update(state='failed', phase=None, error=f'No plan passed the checks in {rounds} rounds', finished=time.time())
    record['outcome'] = 'failed'
    _write(run.directory / 'plan-record.json', record)
    return run.status


def _task_bundle(task_input, compiled, contract_path, plan_path):
    """Build a downstream ``task.json`` envelope pointing at verified ``contract.json`` + ``plan.json``."""
    first_cap = next(
        ((n.get('work') or {}).get('capability', '')
         for n in compiled['node_contracts']['nodes']
         if (n.get('work') or {}).get('capability')),
        'factory.custom',
    )
    comp_cc = first_cap.rsplit('.', 1)[0] if '.' in first_cap else first_cap
    engine = (task_input.get('subject') or {}).get('engine') or {}
    return dict(
        task_id=req.input_id(task_input),
        objective=task_input['objective'],
        constraints=dict(owned_checkout_only=True),
        allowed_effects=list(task_input['constraints']['allowed_effects']),
        target=task_input['target']['profile'],
        budget=dict(task_input['constraints']['budget']),
        contract_id=str(contract_path.resolve()),
        plan=plan_path.name,
        initial_run_config=dict(env={}),
        component_cc=comp_cc,
        source=dict(
            subpath=engine.get('name') or 'llama.cpp',
            pre_integration_commit=engine.get('revision') or 'HEAD',
        ),
    )


def _accept(run, task_input, ir, compiled, warnings, record, verification):
    base_contract = req.contract_of(task_input)
    contract = dict(
        base_contract,
        extensions=dict(
            base_contract.get('extensions') or {},
            **{node_contract.EXTENSION: compiled['node_contracts']},
        ),
    )
    contract_path = run.directory / 'contract.json'
    plan_path = run.directory / 'plan.json'
    graph_path = run.directory / 'graph.json'
    verification_path = run.directory / 'verification.json'
    task_path = run.directory / 'task.json'

    _write(contract_path, contract)
    _write(plan_path, compiled['plan'])
    try:
        graph = graph_preview(run.directory.name, contract_path.resolve(), compiled['plan'])
    except ValueError:
        contract_path.unlink(missing_ok=True)
        plan_path.unlink(missing_ok=True)
        raise

    exec_model = dict(
        verification['execution_model'],
        proven=[
            dict(run=r['run'], checked=r['checked'], distinct_states=r['distinct_states'])
            for r in verification.get('runs', [])
        ],
    )
    if verification.get('spec_sha256'):
        exec_model['spec_sha256'] = verification['spec_sha256']
    graph['execution_model'] = exec_model
    graph['verification'] = dict(
        static_checks=dict(passed=True, warnings=list(warnings)),
        tlc=dict(
            passed=bool(verification.get('passed', True)),
            runs=exec_model['proven'],
            spec_sha256=verification.get('spec_sha256'),
        ),
    )
    _write(graph_path, graph)
    _write(verification_path, verification)
    _write(task_path, _task_bundle(task_input, compiled, contract_path, plan_path))
    _write(run.directory / 'ir.json', ir)
    _write(run.directory / 'derivation.json', compiled['derivation'])

    outputs = {
        name: _sha((run.directory / name).read_bytes())
        for name in ('contract.json', 'plan.json', 'graph.json', 'verification.json', 'task.json')
    }
    record.update(
        outcome='accepted',
        steps=[n['node_id'] for n in compiled['node_contracts']['nodes']],
        warnings=warnings,
        nodes=len(compiled['node_contracts']['nodes']),
        outputs=outputs,
    )
    _write(run.directory / 'plan-record.json', record)
    run.update(state='succeeded', phase=None, warnings=warnings, nodes=record['nodes'], finished=time.time())
    return run.status


def replay(directory):
    """Re-check every recorded reply: same verdicts and, for accepted runs, identical verified outputs."""
    directory = Path(directory)
    task_input = json.loads((directory / 'requirements.json').read_text(encoding='utf-8'))
    catalog = plan_catalog.load()
    selection = plan_select.context(task_input, catalog)
    verdicts = []
    for folder in sorted((directory / 'rounds').iterdir(), key=lambda p: int(p.name)):
        if not (folder / 'reply.txt').is_file():
            continue
        ir, problem = parse_reply((folder / 'reply.txt').read_text(encoding='utf-8'))
        compiled = None
        if problem:
            problems = [problem]
        elif isinstance(ir, dict) and 'unrealizable' in ir:
            ir_problems = plan_ir.problems(ir, selection, catalog=catalog)
            problems = ir_problems or [ir['unrealizable']['why']]
        else:
            _, problems, _, _, compiled = evaluate(ir, task_input, selection, catalog,
                                                   directory / 'replay' / folder.name)
        recorded = json.loads((folder / 'result.json').read_text(encoding='utf-8')).get('problems')
        verdicts.append(dict(round=int(folder.name), same=problems == recorded, passed=not problems))
        if not problems and compiled and (directory / 'contract.json').is_file() and (directory / 'plan.json').is_file():
            saved_contract = json.loads((directory / 'contract.json').read_text(encoding='utf-8'))
            saved_plan = json.loads((directory / 'plan.json').read_text(encoding='utf-8'))
            verdicts[-1]['same_graph'] = (
                node_contract.from_contract(saved_contract) == compiled['node_contracts']
                and saved_plan == compiled['plan']
            )
    return verdicts


def runs(root):
    """Planning runs under ``root``, newest first, with their status."""
    root = Path(root)
    found = []
    if root.is_dir():
        for folder in root.iterdir():
            if PLAN_ID.fullmatch(folder.name) and (folder / 'status.json').is_file():
                try:
                    found.append(dict(id=folder.name, **json.loads((folder / 'status.json').read_text(encoding='utf-8'))))
                except ValueError:
                    continue
    return sorted(found, key=lambda r: r.get('created', 0), reverse=True)


def default_root():
    if os.environ.get('FACTORY_PLANNER_ROOT'):
        return Path(os.environ['FACTORY_PLANNER_ROOT']).expanduser().resolve()
    from jiuwenswarm.common.utils import get_user_workspace_dir
    return Path(get_user_workspace_dir()).resolve() / 'factory-planner'


def main_synthesize(requirements_path, out_root=None, home=None):
    """CLI: plan through the factory's Codex sign-in (``jiuwenswarm-factory login``)."""
    from .controller import configure_agent, factory_home
    configure_agent({'task_id': 'planner', 'allowed_effects': []}, home=home or factory_home())
    task_input = json.loads(Path(requirements_path).read_text(encoding='utf-8'))
    root = Path(out_root).resolve() if out_root else Path(home or factory_home()).resolve() / 'planner'
    directory = root / new_plan_id()

    async def go():
        from jiuwenswarm.server.runtime.codex_subscription.service import get_service
        try:
            return await synthesize(task_input, directory)
        finally:
            await get_service().transport.close()
    status = asyncio.run(go())
    return directory, status
