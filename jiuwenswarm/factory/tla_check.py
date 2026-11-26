"""Model-check a planned task graph against the factory's execution model with TLC.

``tla/TaskGraphExec.tla`` states how the factory executes any task graph. For one
graph this module writes the constants (a ``Plan`` module plus TLC configurations),
runs TLC twice and turns any counterexample into one plain sentence:

* safety run (``Cooperative = FALSE``, nodes may fail any attempt): every invariant
  holds in every reachable state and a run halts only delivered or failed
  (``NoStuck``). With ``Termination`` (every step lowers a progress measure, a property
  of the model proven once in tests/factory/test_tla_check.py, not per plan), every
  execution ends delivered or with a reported failure;
* delivery run (``Cooperative = TRUE``, a node's last allowed attempt succeeds):
  additionally every execution halts delivered (``HaltsDelivered``).

Both are safety checks (invariants and one action property), so TLC explores them
with all workers and no liveness tableau.

The execution parameters (how many nodes run at once, attempts per node, which
resources a node holds) are the execution contract handed downstream with the graph;
the proof holds for a scheduler that keeps them.

TLC needs Java 11+ and ``tla2tools.jar`` (FACTORY_TLA2TOOLS, or
third_party/tlaplus/tla2tools.jar in the repository). Without them nothing is proven,
so callers refuse the graph.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

SPEC = Path(__file__).with_name('tla') / 'TaskGraphExec.tla'
REPO = Path(__file__).resolve().parents[2]
DEFAULT_JAR = REPO / 'third_party' / 'tlaplus' / 'tla2tools.jar'
MAX_PARALLEL = int(os.environ.get('FACTORY_PLANNER_MAX_PARALLEL', '4'))
ATTEMPTS = int(os.environ.get('FACTORY_PLANNER_ATTEMPTS', '2'))
TIMEOUT_S = int(os.environ.get('FACTORY_TLC_TIMEOUT_S', '300'))

INVARIANTS = ('TypeOK', 'DependencyOrder', 'ExclusiveResources', 'ParallelBound', 'AttemptBound',
              'NoStuck', 'DeliveredMeansAllDone')
RUNS = (('safety', False, INVARIANTS), ('delivery', True, INVARIANTS + ('HaltsDelivered',)))
MEANING = {
    'TypeOK': 'the execution reached a malformed state',
    'DependencyOrder': 'a step ran before one of its predecessors was done',
    'ExclusiveResources': 'two steps held the same resource at once',
    'ParallelBound': 'more steps ran at once than the scheduler allows',
    'AttemptBound': 'a step was attempted more often than its limit',
    'NoStuck': 'the run can get stuck: nothing is delivered, nothing has failed, and no step can start',
    'DeliveredMeansAllDone': 'the deliver step finished while another step was not done',
    'Termination': 'a step does not make progress, so an execution may never end',
    'HaltsDelivered': 'even when every step\'s last allowed attempt succeeds, the run can end without delivering',
}


class TlaUnavailable(RuntimeError):
    """TLC cannot run here: no Java or no tla2tools.jar."""


def tools():
    """(java, jar) or raise TlaUnavailable."""
    jar = Path(os.environ.get('FACTORY_TLA2TOOLS') or DEFAULT_JAR).expanduser()
    java = os.environ.get('FACTORY_JAVA') or shutil.which('java')
    if not java:
        raise TlaUnavailable('Java 11+ is required to run TLC (set FACTORY_JAVA or put java on PATH)')
    if not jar.is_file():
        raise TlaUnavailable(f'tla2tools.jar not found at {jar} (set FACTORY_TLA2TOOLS)')
    return java, jar


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def execution_model(document, *, max_parallel=None, attempts=None):
    """The execution contract for one graph: what the scheduler must keep for the proof to hold."""
    max_parallel = max_parallel or MAX_PARALLEL
    attempts = attempts or ATTEMPTS
    nodes = document['nodes']
    limits, exclusive = {}, {}
    for node in nodes:
        node_limits = node.get('node_limits') or {}
        # Build attempts are enforced per node by scheduler.charge; other work by this contract.
        limits[node['node_id']] = node_limits['build_attempts'] if node['kind'] == 'build' and 'build_attempts' in node_limits else attempts
        held = set()
        if (node.get('authority_ceiling') or {}).get('workspace') == 'write':
            held.add('checkout')
        if node['kind'] == 'build':
            held.add('builder')
        exclusive[node['node_id']] = sorted(held)
    return dict(max_parallel=max_parallel, default_attempts=attempts, limits=limits, exclusive=exclusive,
                deliver=next(n['node_id'] for n in nodes if n['kind'] == 'deliver'),
                preds={n['node_id']: sorted(n.get('predecessors', [])) for n in nodes})


def _set(values):
    return '{' + ', '.join(f'"{v}"' for v in values) + '}'


def _function(mapping, render):
    return '(' + ' @@ '.join(f'"{key}" :> {render(value)}' for key, value in mapping.items()) + ')'


def plan_module(model):
    """The Plan module: TaskGraphExec plus this graph's constants as definitions."""
    return '\n'.join([
        '---- MODULE Plan ----',
        'EXTENDS TaskGraphExec, TLC',
        f'PlanNodes == {_set(model["preds"])}',
        f'PlanPreds == {_function(model["preds"], _set)}',
        f'PlanDeliver == "{model["deliver"]}"',
        f'PlanLimit == {_function(model["limits"], str)}',
        f'PlanExclusive == {_function(model["exclusive"], _set)}',
        '====', ''])


def standalone_config(cooperative, invariants=INVARIANTS, properties=()):
    lines = ['SPECIFICATION Spec', 'CONSTANTS',
             f'    Cooperative = {"TRUE" if cooperative else "FALSE"}',
             'INVARIANTS', *('    ' + name for name in invariants),
             *(['PROPERTIES', *('    ' + name for name in properties)] if properties else []), '']
    return '\n'.join(lines)


def config(model, cooperative, invariants=INVARIANTS, properties=()):
    lines = ['SPECIFICATION Spec', 'CONSTANTS',
             '    Nodes <- PlanNodes', '    Preds <- PlanPreds', '    Deliver <- PlanDeliver',
             '    Limit <- PlanLimit', '    Exclusive <- PlanExclusive',
             f'    MaxParallel = {model["max_parallel"]}', f'    Cooperative = {"TRUE" if cooperative else "FALSE"}',
             'INVARIANTS', *('    ' + name for name in invariants),
             *(['PROPERTIES', *('    ' + name for name in properties)] if properties else []), '']
    return '\n'.join(lines)


_STATE = re.compile(r'^State (\d+): <([^>]*)>')
_ENTRY = re.compile(r'(\w+) \|-> ("[a-z]+"|\d+)')


def _variables(block):
    """{'st': {node: phase}, 'att': {node: n}} from one printed TLC state."""
    values = {}
    for name in ('st', 'att'):
        # Node maps print as records: [a |-> "waiting", b |-> 1]; values never contain brackets.
        match = re.search(r'/\\ ' + name + r' = (\[[^\]]*\])', block)
        if match:
            values[name] = {k: v.strip('"') if v.startswith('"') else int(v) for k, v in _ENTRY.findall(match.group(1))}
    return values


def parse_trace(output):
    """Printed error trace -> [{'state': n, 'action': name, 'st': {...}, 'att': {...}}]."""
    states, current = [], None
    for line in output.splitlines():
        match = _STATE.match(line)
        if match:
            current = dict(state=int(match.group(1)), action=match.group(2).split(' ')[0], text='')
            states.append(current)
        elif line.startswith('Back to state') and current is not None:
            states.append(dict(state=-1, action='loop', text=line))
            current = None
        elif current is not None:
            current['text'] += line + '\n'
    for state in states:
        state.update(_variables(state.pop('text', '')))
    return states


def blocked(state, model):
    """Why each waiting node of a final state cannot start, in the model's own terms."""
    st, att = state.get('st', {}), state.get('att', {})
    active = [n for n, p in st.items() if p == 'active']
    held = {r for n in active for r in model['exclusive'].get(n, [])}
    reasons = []
    for node, phase in st.items():
        if phase != 'waiting':
            continue
        unfinished = [p for p in model['preds'].get(node, []) if st.get(p) != 'done']
        if unfinished:
            continue  # waiting on others is a consequence, not a cause
        limit = model['limits'].get(node)
        if att.get(node, 0) >= limit:
            reasons.append(f'{node} cannot start: it has used {att.get(node, 0)} of {limit} allowed attempts'
                           + (' (its attempt limit is 0)' if limit == 0 else ''))
        elif set(model['exclusive'].get(node, [])) & held:
            reasons.append(f'{node} cannot start: {", ".join(sorted(set(model["exclusive"][node]) & held))} is held')
        elif len(active) >= model['max_parallel']:
            reasons.append(f'{node} cannot start: {model["max_parallel"]} steps are already running')
    return reasons


def describe(trace, limit=8):
    """A trace as plain steps: which node moved, from what to what."""
    steps, previous = [], None
    for state in trace:
        if state['action'] == 'loop':
            steps.append('then the same states repeat forever')
            continue
        st = state.get('st', {})
        if previous is not None:
            for node, phase in st.items():
                before = previous.get('st', {}).get(node)
                if before != phase:
                    attempt = state.get('att', {}).get(node)
                    steps.append(f'{node} {before}→{phase}' + (f' (attempt {attempt})' if phase == 'active' else ''))
        previous = state
    if trace and trace[-1].get('st'):
        waiting = sorted(n for n, p in trace[-1]['st'].items() if p == 'waiting')
        done = sorted(n for n, p in trace[-1]['st'].items() if p == 'done')
        tail = f'final: done [{", ".join(done)}], waiting [{", ".join(waiting)}]'
    else:
        tail = ''
    shown = steps if len(steps) <= limit else ['…'] + steps[-limit:]
    return '; '.join(shown + ([tail] if tail else []))


def _stats(output):
    generated = re.search(r'([\d,]+) states generated, ([\d,]+) distinct states found', output)
    depth = re.search(r'depth of the complete state graph search is (\d+)', output)
    return dict(states_generated=int(generated.group(1).replace(',', '')) if generated else None,
                distinct_states=int(generated.group(2).replace(',', '')) if generated else None,
                depth=int(depth.group(1)) if depth else None)


def _violation(output, model):
    invariant = re.search(r'Invariant (\w+) is violated', output)
    if invariant:
        name, kind = invariant.group(1), 'invariant'
    elif 'Action property' in output or 'Temporal properties were violated' in output:
        name, kind = 'Termination', 'property'
    elif 'Deadlock reached' in output:
        name, kind = 'NoStuck', 'deadlock'
    elif re.search(r'The assumption on line|Assumption .* is false|AssumptionFailure', output):
        return dict(property='Assumption', kind='assumption', trace=[],
                    sentence='TLC ASSUME check failed: static graph contract assertion is false.', causes=[])
    else:
        return None
    trace = parse_trace(output)
    sentence = f'TLC {name}: {MEANING.get(name, name)}.'
    causes = blocked(trace[-1], model) if trace and trace[-1].get('st') else []
    if causes:
        sentence += ' ' + '; '.join(causes) + '.'
    sentence += f' Counterexample ({len([s for s in trace if s["state"] > 0])} states): {describe(trace)}'
    return dict(property=name, kind=kind, trace=trace, sentence=sentence, causes=causes)


def run_tlc(directory, cfg_name, *, module='Plan.tla', timeout=None):
    java, jar = tools()
    started = time.time()
    try:
        result = subprocess.run(
            [java, '-XX:+UseParallelGC', '-cp', str(jar), 'tlc2.TLC', '-workers', 'auto', '-cleanup',
             '-metadir', str(directory / ('states-' + cfg_name)), '-config', cfg_name + '.cfg', module],
            cwd=directory, capture_output=True, text=True, timeout=timeout or TIMEOUT_S, check=False)
        output, timed_out = result.stdout + result.stderr, False
    except subprocess.TimeoutExpired as exc:
        parts = [p.decode('utf-8', 'replace') if isinstance(p, bytes) else (p or '') for p in (exc.stdout, exc.stderr)]
        output, timed_out = ''.join(parts), True
    (directory / (cfg_name + '.out')).write_text(output, encoding='utf-8')
    return output, timed_out, round(time.time() - started, 2)


def _execute_tlc_runs(directory, model, module_name, cfg_builder, *, java, jar, spec_sha, timeout=None):
    runs, problems = [], []
    for name, cooperative, invariants in RUNS:
        (directory / (name + '.cfg')).write_text(cfg_builder(cooperative, invariants), encoding='utf-8')
        output, timed_out, seconds = run_tlc(directory, name, module=module_name, timeout=timeout)
        entry = dict(run=name, seconds=seconds, **_stats(output), checked=list(invariants) + ['Termination'])
        if timed_out:
            entry.update(passed=False, error='timeout')
            problems.append(f'TLC could not finish the {name} check within {timeout or TIMEOUT_S}s; '
                            'the graph allows too many interleavings: order more steps or split the work')
        elif 'Model checking completed. No error has been found.' in output:
            entry['passed'] = True
        else:
            violation = _violation(output, model)
            if violation is None:
                tail = '\n'.join(output.strip().splitlines()[-20:])
                raise RuntimeError(f'TLC failed without a verdict on the {name} check:\n{tail}')
            entry.update(passed=False, violation={k: violation[k] for k in ('property', 'kind', 'sentence')})
            problems.append(violation['sentence'])
        runs.append(entry)
        if problems:
            break
    return dict(passed=not problems, problems=problems, runs=runs, execution_model=model,
                spec_sha256=spec_sha, tla2tools_sha256=_sha(jar), java=java)


def check_graph_tla(tla_source_or_path, directory, *, max_parallel=None, attempts=None, timeout=None):
    """Model-check one standalone ``Graph.tla`` (source text or path) with zero external TLA files."""
    from .tla_graph import parse_taskgraph_tla
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    java, jar = tools()
    if isinstance(tla_source_or_path, Path) or (
        isinstance(tla_source_or_path, str) and '\n' not in tla_source_or_path and '---- MODULE' not in tla_source_or_path
    ):
        text = Path(tla_source_or_path).read_text(encoding='utf-8')
    else:
        text = str(tla_source_or_path)
    parsed = parse_taskgraph_tla(text)
    model = dict(parsed['execution_model'])
    if max_parallel is not None or attempts is not None:
        model = execution_model(parsed['node_contracts'], max_parallel=max_parallel, attempts=attempts)
    graph_file = directory / 'Graph.tla'
    graph_file.write_text(text, encoding='utf-8')
    return _execute_tlc_runs(
        directory,
        model,
        'Graph.tla',
        lambda coop, invs: standalone_config(coop, invs),
        java=java,
        jar=jar,
        spec_sha=_sha(graph_file),
        timeout=timeout,
    )


def check(document, directory, *, max_parallel=None, attempts=None, timeout=None):
    """Model-check one node-contracts document. Returns problems (sentences) and the evidence."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    java, jar = tools()
    model = execution_model(document, max_parallel=max_parallel, attempts=attempts)
    shutil.copyfile(SPEC, directory / SPEC.name)
    (directory / 'Plan.tla').write_text(plan_module(model), encoding='utf-8')
    return _execute_tlc_runs(
        directory,
        model,
        'Plan.tla',
        lambda coop, invs: config(model, coop, invs),
        java=java,
        jar=jar,
        spec_sha=_sha(SPEC),
        timeout=timeout,
    )
