"""Self-contained ``graph.tla`` generator and zero-JVM pure-Python parser.

``render_graph_tla`` serializes a compiled single-solution TaskGraph (topology,
execution contract constants, complete per-node ``NodeSpec``, static ``ASSUME``
assertions, and the inlined ``TaskGraphExec`` state machine + safety/liveness
properties) into a single standalone ``---- MODULE Graph ----`` file that
``java -cp tla2tools.jar tlc2.TLC`` can verify in an otherwise empty directory.

``parse_taskgraph_tla`` parses that ``graph.tla`` file cleanly in pure Python
with no JVM/subprocess dependency and reconstructs ``node_contracts``, ``plan``,
``execution_model``, and task metadata for downstream consumers.
"""
from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from .tla_check import execution_model


def _tla_escape(text: str) -> str:
    out: list[str] = []
    for ch in str(text):
        if ch == '\\':
            out.append('\\\\')
        elif ch == '"':
            out.append('\\"')
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\t':
            out.append('\\t')
        elif ch == '\r':
            out.append('\\r')
        elif ch == '\f':
            out.append('\\f')
        elif ord(ch) < 32:
            out.append(' ')
        else:
            out.append(ch)
    return ''.join(out)


def _fmt_str(text: str) -> str:
    return f'"{_tla_escape(text)}"'


def _fmt_val(value: Any, indent: int = 0) -> str:
    pad = ' ' * indent
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return _fmt_str(value)
    if isinstance(value, set):
        items = sorted(value, key=lambda x: str(x))
        return '{' + ', '.join(_fmt_str(x) if isinstance(x, str) else _fmt_val(x) for x in items) + '}'
    if isinstance(value, (list, tuple)):
        if not value:
            return '<<>>'
        if all(not isinstance(x, (dict, list, tuple, set)) for x in value) and sum(len(str(x)) for x in value) < 72:
            return '<<' + ', '.join(_fmt_val(x) for x in value) + '>>'
        inner = ',\n'.join(' ' * (indent + 2) + _fmt_val(x, indent + 2) for x in value)
        return '<<\n' + inner + '\n' + pad + '>>'
    if isinstance(value, dict):
        if not value:
            return '[ ]'
        parts = []
        for k, v in value.items():
            parts.append(' ' * (indent + 2) + f'{k} |-> {_fmt_val(v, indent + 2)}')
        if len(parts) <= 3 and all('\n' not in p for p in parts) and sum(len(p) for p in parts) < 72:
            return '[' + ', '.join(p.strip() for p in parts) + ']'
        return '[\n' + ',\n'.join(parts) + '\n' + pad + ']'
    raise TypeError(f'Unsupported TLA+ literal type: {type(value).__name__}')


def _output_kind_map(document: dict) -> dict[tuple[str, str], str]:
    kinds: dict[tuple[str, str], str] = {}
    for node in document.get('nodes', []):
        nid = node['node_id']
        for out in node.get('outputs', []):
            kinds[(nid, out['name'])] = out['kind']
    return kinds


def _build_node_spec_record(node: dict, out_kinds: dict[tuple[str, str], str]) -> dict:
    inputs_list = []
    for inp in node.get('inputs', []):
        src = inp['from']
        if src.startswith('task:') or src.startswith('contract:'):
            ikind = 'evidence'
        else:
            prod, _, port = src.partition('.')
            ikind = out_kinds.get((prod, port), 'evidence')
        inputs_list.append({
            'name': inp['name'],
            'from': src,
            'kind': ikind,
            'required': bool(inp.get('required', True)),
        })

    outputs_list = []
    for out in node.get('outputs', []):
        outputs_list.append({
            'name': out['name'],
            'kind': out['kind'],
            'required': bool(out.get('required', True)),
            'criteria': list(out.get('criteria', [])),
        })

    verifiers_list = []
    for ver in node.get('verifiers', []):
        verifiers_list.append({
            'output': ver['output'],
            'verifier': ver.get('verifier') or '',
            'stage': ver.get('stage') or '',
            'review': bool(ver.get('review', False)),
        })

    auth = node.get('authority_ceiling') or {}
    limits = node.get('node_limits') or {}
    work = node.get('work') or {}
    return {
        'kind': node['kind'],
        'objective': node['objective'],
        'predecessors': list(node.get('predecessors', [])),
        'requirement_ids': list(node.get('requirement_ids', [])),
        'capability': work.get('capability') or '',
        'helpful_ccs': list(work.get('helpful_ccs', [])),
        'inputs': inputs_list,
        'outputs': outputs_list,
        'verifiers': verifiers_list,
        'authority': {
            'workspace': auth.get('workspace', 'none'),
            'effects': set(auth.get('effects', [])),
        },
        'node_limits': {
            k: int(limits[k]) for k in ('turns', 'build_attempts', 'gpu_launches', 'time_s') if k in limits
        },
        'evidence_obligations': list(node.get('evidence_obligations', [])),
        'hands_to': node.get('hands_to', 'lab_manager'),
    }


_GRAPH_TEMPLATE = r"""------------------------------- MODULE Graph -------------------------------
(***************************************************************************)
(* Self-contained deliverable TaskGraph and execution specification.       *)
(* Standalone TLC check:                                                   *)
(*   java -cp tla2tools.jar tlc2.TLC -config safety.cfg Graph.tla          *)
(* Zero-JVM Python parser: ``tla_graph.parse_taskgraph_tla``               *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets, Sequences, TLC

CONSTANT Cooperative

\* -- 1. Execution topology and contract constants -------------------------
TaskId == __TASK_ID__
Objective == __OBJECTIVE__
PlannerName == __PLANNER_NAME__
AllowedEffects == __ALLOWED_EFFECTS__

Nodes == __NODES__
Deliver == __DELIVER__
MaxParallel == __MAX_PARALLEL__

Preds == __PREDS__

Limit == __LIMIT__

Exclusive == __EXCLUSIVE__

\* -- 2. Full node contracts (constant operator; excluded from VARIABLES) --
NodeSpec == __NODE_SPEC__

\* -- 3. Static contract & safety assertions verified by TLC on load -------
ASSUME /\ Deliver \in Nodes
       /\ Preds \in [Nodes -> SUBSET Nodes]
       /\ Limit \in [Nodes -> Nat]
       /\ MaxParallel \in Nat \ {0}
       /\ Cooperative \in BOOLEAN
       /\ ~(\E m \in Nodes : Deliver \in Preds[m])
       /\ \A n \in Nodes : n = Deliver \/ (\E m \in Nodes : n \in Preds[m])
       /\ \A n \in Nodes : NodeSpec[n].authority.effects \subseteq AllowedEffects
       /\ \A n \in Nodes :
            (\E i \in 1..Len(NodeSpec[n].outputs) : NodeSpec[n].outputs[i].kind = "diff")
              => NodeSpec[n].authority.workspace = "write"
       /\ \A n \in Nodes : (NodeSpec[n].kind = "deliver") <=> (n = Deliver)
       /\ \A n \in Nodes : (NodeSpec[n].kind = "deliver") => NodeSpec[n].authority.workspace = "none"
       /\ \A n \in Nodes : (NodeSpec[n].kind \in {"inspect", "investigate", "build", "measure"}) => NodeSpec[n].authority.workspace # "write"

\* -- 4. Inlined execution state machine & temporal properties -------------
VARIABLES st, att
vars == <<st, att>>

Phases == {"waiting", "active", "done", "failed"}
Active == {n \in Nodes : st[n] = "active"}
Held == UNION {Exclusive[n] : n \in Active}

Init == /\ st = [n \in Nodes |-> "waiting"]
        /\ att = [n \in Nodes |-> 0]

CanStart(n) == /\ st[n] = "waiting"
               /\ \A p \in Preds[n] : st[p] = "done"
               /\ att[n] < Limit[n]
               /\ Cardinality(Active) < MaxParallel
               /\ Exclusive[n] \cap Held = {}

Start(n) == /\ CanStart(n)
            /\ st' = [st EXCEPT ![n] = "active"]
            /\ att' = [att EXCEPT ![n] = @ + 1]

Succeed(n) == /\ st[n] = "active"
              /\ st' = [st EXCEPT ![n] = "done"]
              /\ UNCHANGED att

SendBack(n) == /\ st[n] = "active"
               /\ ~Cooperative \/ att[n] < Limit[n]
               /\ st' = [st EXCEPT ![n] = IF att[n] < Limit[n] THEN "waiting" ELSE "failed"]
               /\ UNCHANGED att

Step == \E n \in Nodes : Start(n) \/ Succeed(n) \/ SendBack(n)

Delivered == st[Deliver] = "done"
Failed == \E n \in Nodes : st[n] = "failed"
CanStep == Active # {} \/ \E n \in Nodes : CanStart(n)
Halt == ~CanStep /\ UNCHANGED vars

Next == Step \/ Halt
Spec == Init /\ [][Next]_vars

PhaseWeight(p) == CASE p = "waiting" -> 1 [] p = "active" -> 2 [] OTHER -> 0
RECURSIVE SumOver(_, _)
SumOver(f, S) == IF S = {} THEN 0 ELSE LET x == CHOOSE y \in S : TRUE IN f[x] + SumOver(f, S \ {x})
Rank == SumOver([n \in Nodes |-> 2 * (Limit[n] - att[n]) + PhaseWeight(st[n])], Nodes)

TypeOK == /\ st \in [Nodes -> Phases]
          /\ att \in [Nodes -> Nat]

DependencyOrder == \A n \in Nodes :
    st[n] \in {"active", "done"} => \A p \in Preds[n] : st[p] = "done"

ExclusiveResources == \A m, n \in Active : m # n =>
    LET rm == Exclusive[m] \cup (IF NodeSpec[m].authority.workspace = "write" THEN {"checkout"} ELSE {}) \cup (IF NodeSpec[m].kind = "build" THEN {"builder"} ELSE {})
        rn == Exclusive[n] \cup (IF NodeSpec[n].authority.workspace = "write" THEN {"checkout"} ELSE {}) \cup (IF NodeSpec[n].kind = "build" THEN {"builder"} ELSE {})
    IN rm \cap rn = {}

ParallelBound == Cardinality(Active) <= MaxParallel

AttemptBound == \A n \in Nodes : att[n] <= Limit[n]

NoStuck == ~CanStep => (Delivered \/ Failed)

DeliveredMeansAllDone == Delivered => \A n \in Nodes : st[n] = "done"

HaltsDelivered == ~CanStep => Delivered

Termination == [][Rank' < Rank]_vars

=============================================================================
"""


def render_graph_tla(
    document: dict,
    task_input: dict | None = None,
    plan: dict | None = None,
    *,
    max_parallel: int | None = None,
    attempts: int | None = None,
    exclusive_override: dict[str, list[str]] | None = None,
) -> str:
    """Serialize a verified TaskGraph into a single self-contained ``Graph.tla`` module."""
    model = execution_model(document, max_parallel=max_parallel, attempts=attempts)
    if plan and isinstance(plan.get('nodes'), list):
        plan_deps = {pn['node_id']: list(pn.get('depends_on') or []) for pn in plan['nodes']}
        for nid in model['preds']:
            if nid in plan_deps:
                model['preds'][nid] = sorted(set(model['preds'][nid]) | set(plan_deps[nid]))
    if exclusive_override is not None:
        for nid, ex in exclusive_override.items():
            if nid in model['exclusive']:
                model['exclusive'][nid] = sorted(ex)
    nodes = list(document.get('nodes', []))
    out_kinds = _output_kind_map(document)
    ti = task_input or {}
    task_id = str(ti.get('task_id') or ti.get('requirements_id') or 'task')
    objective = str(ti.get('objective') or 'Compiled inference engine task graph')
    allowed_effects = set((ti.get('constraints') or {}).get('allowed_effects') or ['workspace.read', 'workspace.write', 'process.exec'])
    if not ti:
        for n in nodes:
            allowed_effects.update((n.get('authority_ceiling') or {}).get('effects') or [])
    planner_name = (plan or {}).get('planner') or 'factory.ai_planner'

    node_ids = [n['node_id'] for n in nodes]

    def _fn(mapping, render_val):
        entries = [f'    {_fmt_str(nid)} :> {render_val(mapping[nid])}' for nid in node_ids]
        return '(\n' + '\n @@\n'.join(entries) + '\n)'

    spec_map = {n['node_id']: _build_node_spec_record(n, out_kinds) for n in nodes}
    nodespec_entries = [f'    {_fmt_str(nid)} :> {_fmt_val(spec_map[nid], 4)}' for nid in node_ids]

    text = _GRAPH_TEMPLATE
    for marker, val in (
        ('__TASK_ID__', _fmt_str(task_id)),
        ('__OBJECTIVE__', _fmt_str(objective)),
        ('__PLANNER_NAME__', _fmt_str(planner_name)),
        ('__ALLOWED_EFFECTS__', _fmt_val(allowed_effects)),
        ('__NODES__', _fmt_val(set(node_ids))),
        ('__DELIVER__', _fmt_str(model['deliver'])),
        ('__MAX_PARALLEL__', str(int(model['max_parallel']))),
        ('__PREDS__', _fn(model['preds'], lambda ps: _fmt_val(set(ps)))),
        ('__LIMIT__', _fn(model['limits'], lambda lim: str(int(lim)))),
        ('__EXCLUSIVE__', _fn(model['exclusive'], lambda ex: _fmt_val(set(ex)))),
        ('__NODE_SPEC__', '(\n' + '\n @@\n'.join(nodespec_entries) + '\n)'),
    ):
        text = text.replace(marker, val, 1)
    return text


# ---------------------------------------------------------------------------
# Zero-JVM pure-Python parser for Graph.tla
# ---------------------------------------------------------------------------

class TlaParseError(ValueError):
    pass


_TOKEN_RE = re.compile(
    r'\s*(?:'
    r'(\\\*[^\n]*)'               # line comment
    r'|(\(\*[\s\S]*?\*\))'        # block comment
    r'|("([^"\\]|\\.)*")'         # quoted string
    r'|(<<|>>|\|->|:>|@@|==)'     # multi-char operators
    r'|([\{\}\[\]\(\),])'         # single delimiters
    r'|([0-9]+)'                  # integer
    r'|([A-Za-z_][A-Za-z0-9_]*)'  # identifier
    r')'
)


def _tokenize(expr: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos = 0
    n = len(expr)
    while pos < n:
        # Skip whitespace cleanly first
        while pos < n and expr[pos].isspace():
            pos += 1
        if pos >= n:
            break
        m = _TOKEN_RE.match(expr, pos)
        if not m or m.end() == pos:
            raise TlaParseError(f'Unexpected TLA+ token near {expr[pos:pos + 32]!r}')
        pos = m.end()
        if m.group(1) or m.group(2):
            continue
        if m.group(3):
            tokens.append(('STR', m.group(3)))
        elif m.group(5):
            tokens.append(('OP', m.group(5)))
        elif m.group(6):
            tokens.append(('DELIM', m.group(6)))
        elif m.group(7):
            tokens.append(('INT', m.group(7)))
        elif m.group(8):
            tokens.append(('ID', m.group(8)))
    return tokens


def _decode_str(raw: str) -> str:
    inner = raw[1:-1]
    out: list[str] = []
    i = 0
    n = len(inner)
    while i < n:
        ch = inner[i]
        if ch == '\\' and i + 1 < n:
            nxt = inner[i + 1]
            if nxt == 'n':
                out.append('\n')
            elif nxt == 't':
                out.append('\t')
            elif nxt == 'r':
                out.append('\r')
            elif nxt == 'f':
                out.append('\f')
            elif nxt == '"':
                out.append('"')
            elif nxt == '\\':
                out.append('\\')
            else:
                out.append(nxt)
            i += 2
        else:
            out.append(ch)
            i += 1
    return ''.join(out)


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]]):
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset: int = 0) -> tuple[str, str] | None:
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else None

    def pop(self) -> tuple[str, str]:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, kind: str, val: str | None = None) -> tuple[str, str]:
        tok = self.peek()
        if tok is None or tok[0] != kind or (val is not None and tok[1] != val):
            raise TlaParseError(f'Expected ({kind}, {val}), got {tok}')
        return self.pop()

    def parse_expr(self) -> Any:
        left = self.parse_atom()
        # Handle function literal `k :> v` chained by `@@`
        if self.peek() == ('OP', ':>'):
            self.pop()
            val = self.parse_atom()
            mapping = {left: val}
            while self.peek() == ('OP', '@@'):
                self.pop()
                k2 = self.parse_atom()
                self.expect('OP', ':>')
                v2 = self.parse_atom()
                mapping[k2] = v2
            return mapping
        return left

    def parse_atom(self) -> Any:
        tok = self.peek()
        if tok is None:
            raise TlaParseError('Unexpected end of TLA+ expression')
        kind, val = tok
        if kind == 'STR':
            self.pop()
            return _decode_str(val)
        if kind == 'INT':
            self.pop()
            return int(val)
        if kind == 'ID':
            self.pop()
            if val == 'TRUE':
                return True
            if val == 'FALSE':
                return False
            raise TlaParseError(f'Unsupported identifier literal {val!r}')
        if (kind, val) == ('DELIM', '('):
            self.pop()
            inner = self.parse_expr()
            self.expect('DELIM', ')')
            return inner
        if (kind, val) == ('DELIM', '{'):
            self.pop()
            items: list[Any] = []
            while self.peek() != ('DELIM', '}'):
                items.append(self.parse_expr())
                if self.peek() == ('DELIM', ','):
                    self.pop()
                elif self.peek() != ('DELIM', '}'):
                    raise TlaParseError(f'Malformed set literal near {self.peek()}')
            self.expect('DELIM', '}')
            return set(items) if all(isinstance(x, (str, int, bool)) for x in items) else items
        if (kind, val) == ('OP', '<<'):
            self.pop()
            items = []
            while self.peek() != ('OP', '>>'):
                items.append(self.parse_expr())
                if self.peek() == ('DELIM', ','):
                    self.pop()
                elif self.peek() != ('OP', '>>'):
                    raise TlaParseError(f'Malformed tuple literal near {self.peek()}')
            self.expect('OP', '>>')
            return items
        if (kind, val) == ('DELIM', '['):
            self.pop()
            rec: dict[str, Any] = {}
            while self.peek() != ('DELIM', ']'):
                k_tok = self.expect('ID')
                self.expect('OP', '|->')
                v = self.parse_expr()
                rec[k_tok[1]] = v
                if self.peek() == ('DELIM', ','):
                    self.pop()
                elif self.peek() != ('DELIM', ']'):
                    raise TlaParseError(f'Malformed record literal near {self.peek()}')
            self.expect('DELIM', ']')
            return rec
        raise TlaParseError(f'Unexpected token {tok}')


def _parse_tla_value(expr: str) -> Any:
    parser = _Parser(_tokenize(expr))
    val = parser.parse_expr()
    if parser.peek() is not None:
        raise TlaParseError(f'Trailing TLA+ tokens starting at {parser.peek()}')
    return val


_TARGET_CONSTANTS = (
    'TaskId',
    'Objective',
    'PlannerName',
    'AllowedEffects',
    'Nodes',
    'Deliver',
    'MaxParallel',
    'Preds',
    'Limit',
    'Exclusive',
    'NodeSpec',
)


def _extract_definitions(source: str) -> dict[str, str]:
    """Slice top-level constant operator RHS bodies cleanly from Graph.tla."""
    # Stop scanning definitions before ASSUME or VARIABLES
    stop_match = re.search(r'^\s*(?:ASSUME|VARIABLES)\b', source, re.MULTILINE)
    header = source[:stop_match.start()] if stop_match else source
    def_re = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*==', re.MULTILINE)
    matches = list(def_re.finditer(header))
    defs: dict[str, str] = {}
    for idx, m in enumerate(matches):
        name = m.group(1)
        if name not in _TARGET_CONSTANTS:
            continue
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(header)
        defs[name] = header[start:end].strip()
    return defs


def parse_taskgraph_tla(path_or_source: str | Path) -> dict[str, Any]:
    """Parse ``graph.tla`` in pure Python (no JVM) into structured task & node contracts.

    Returns a dictionary containing:
      - ``task_id``, ``objective``, ``planner``, ``allowed_effects``
      - ``node_contracts`` (valid ``factory.node-contracts/1`` document)
      - ``plan`` (valid ``factory.plan/1`` document)
      - ``node_specs`` (full ``NodeSpec`` records keyed by ``node_id``, incl. input ``kind``)
      - ``execution_model`` (``nodes``, ``preds``, ``deliver``, ``limits``, ``exclusive``, ``max_parallel``)
    """
    if isinstance(path_or_source, Path) or (
        isinstance(path_or_source, str) and '\n' not in path_or_source and '---- MODULE' not in path_or_source
    ):
        text = Path(path_or_source).read_text(encoding='utf-8')
    else:
        text = str(path_or_source)

    defs = _extract_definitions(text)
    missing = [k for k in ('Nodes', 'Preds', 'Deliver', 'Limit', 'Exclusive', 'MaxParallel', 'NodeSpec') if k not in defs]
    if missing:
        raise TlaParseError(f'Graph.tla missing required definitions: {missing}')

    parsed = {k: _parse_tla_value(v) for k, v in defs.items()}
    nodes_set = set(parsed['Nodes'])
    preds_map = {k: sorted(v) for k, v in parsed['Preds'].items()}
    limit_map = {k: int(v) for k, v in parsed['Limit'].items()}
    excl_map = {k: sorted(v) for k, v in parsed['Exclusive'].items()}
    raw_specs = parsed['NodeSpec']
    planner_name = parsed.get('PlannerName') or 'factory.ai_planner'
    task_id = parsed.get('TaskId') or 'task'
    objective = parsed.get('Objective') or ''
    allowed_effects = sorted(parsed.get('AllowedEffects') or [])

    # Preserve topological/declaration order from NodeSpec keys
    ordered_ids = [nid for nid in raw_specs.keys() if nid in nodes_set]
    for nid in sorted(nodes_set):
        if nid not in ordered_ids:
            ordered_ids.append(nid)

    nc_nodes: list[dict] = []
    plan_nodes: list[dict] = []
    for nid in ordered_ids:
        spec = raw_specs[nid]
        nc_inputs = [
            {
                'name': inp['name'],
                'from': inp['from'],
                **({'required': inp['required']} if inp.get('required') is False else {}),
            }
            for inp in spec.get('inputs', [])
        ]
        nc_outputs = [
            {
                'name': out['name'],
                'kind': out['kind'],
                **({'required': out['required']} if out.get('required') is False else {}),
                **({'criteria': list(out['criteria'])} if out.get('criteria') else {}),
            }
            for out in spec.get('outputs', [])
        ]
        nc_verifiers = []
        for ver in spec.get('verifiers', []):
            ventry: dict[str, Any] = {'output': ver['output']}
            if ver.get('verifier'):
                ventry['verifier'] = ver['verifier']
            if ver.get('stage'):
                ventry['stage'] = ver['stage']
            if ver.get('review'):
                ventry['review'] = True
            nc_verifiers.append(ventry)

        auth = spec.get('authority') or {}
        limits = spec.get('node_limits') or {}
        work: dict[str, Any] = {}
        if spec.get('helpful_ccs'):
            work['helpful_ccs'] = list(spec['helpful_ccs'])
        if spec.get('capability'):
            work['capability'] = spec['capability']

        nc_entry: dict[str, Any] = {
            'node_id': nid,
            'kind': spec['kind'],
            'objective': spec['objective'],
            'inputs': nc_inputs,
            'outputs': nc_outputs,
            'verifiers': nc_verifiers,
            'authority_ceiling': {
                'effects': sorted(auth.get('effects') or []),
                'workspace': auth.get('workspace', 'none'),
            },
            'node_limits': {k: int(v) for k, v in limits.items()},
            'hands_to': spec.get('hands_to', 'lab_manager'),
        }
        pred_list = list(spec.get('predecessors') or preds_map.get(nid, []))
        plan_dep_list = list(preds_map.get(nid, [])) or list(pred_list)
        if pred_list:
            nc_entry['predecessors'] = pred_list
        if spec.get('requirement_ids'):
            nc_entry['requirement_ids'] = list(spec['requirement_ids'])
        if spec.get('evidence_obligations'):
            nc_entry['evidence_obligations'] = list(spec['evidence_obligations'])
        if work:
            nc_entry['work'] = work
        nc_nodes.append(nc_entry)
        plan_nodes.append({
            'node_id': nid,
            'node_contract': nid,
            'depends_on': plan_dep_list if set(plan_dep_list) != set(pred_list) else list(pred_list),
        })

    return {
        'task_id': task_id,
        'objective': objective,
        'planner': planner_name,
        'allowed_effects': allowed_effects,
        'nodes': copy.deepcopy(nc_nodes),
        'node_contracts': {'format': 'factory.node-contracts/1', 'nodes': nc_nodes},
        'plan': {'format': 'factory.plan/1', 'planner': planner_name, 'nodes': plan_nodes},
        'node_specs': copy.deepcopy(raw_specs),
        'execution_model': {
            'nodes': ordered_ids,
            'preds': preds_map,
            'deliver': parsed['Deliver'],
            'limits': limit_map,
            'exclusive': excl_map,
            'max_parallel': int(parsed['MaxParallel']),
            'default_attempts': max(limit_map.values()) if limit_map else 2,
        },
    }


def load_taskgraph(path: str | Path) -> dict[str, Any]:
    """Load and parse a ``graph.tla`` file in pure Python (zero JVM dependency)."""
    return parse_taskgraph_tla(Path(path))
