"""Compatibility policy for captured capability profiles; core Planner owns synthesis."""
from .contracts import ResearchError

POLICY_ID = 'ai4r_capability_dag_v1'
PLANNER = 'research.planner'


def capability_plan_policy():
    return {'schema_version': '1.0.0', 'id': POLICY_ID, 'max_nodes': 12,
            'allowed_effect_classes': ['pure', 'read_only', 'idempotent', 'compensable'],
            'allow_network': True, 'required_stages': [],
            'aggregate_limits': {'time_s': 10800, 'model_calls': 80, 'memory_mb': 16384},
            'max_attempts_per_node': 1}


def is_capability_policy(policy):
    if not isinstance(policy, dict) or policy.get('id') != POLICY_ID:
        return False
    if policy != capability_plan_policy():
        raise ResearchError('capability_policy', 'Capability DAG policy differs from its protected version')
    return True


def layout_issues(source):
    nodes = source['nodes']
    generalists = [n for n in nodes if n['cc']['cc_name'] == 'research.generalist']
    issues = []
    if len(generalists) > 2:
        issues.append('At most two Generalist assignments are permitted')
    # Scientific outputs retain the scientific release path. Generic work may
    # terminate at any typed, checked leaf covering all deliverables.
    scientific = {'research.' + s for s in ('hypothesis', 'builder', 'benchmark', 'evaluation')}
    if any(n['cc']['cc_name'] in scientific for n in nodes):
        leaves = [n for n in nodes if not any(n['node_id'] in m['predecessors'] for m in nodes)]
        if len(leaves) != 1 or leaves[0]['cc']['cc_name'] != 'research.delivery':
            issues.append('Scientific work requires the scientific Delivery leaf')
        by_id = {n['node_id']: n for n in nodes}
        seen = set()
        pending = list(leaves[0]['predecessors']) if len(leaves) == 1 else []
        while pending:
            key = pending.pop()
            if key in seen or key not in by_id:
                continue
            seen.add(key)
            pending.extend(by_id[key]['predecessors'])
        if sum(by_id[k]['cc']['cc_name'] == 'research.evaluation' for k in seen) != 1:
            issues.append('Scientific delivery requires exactly one Scientific Evaluation ancestor')
    return issues


INSTRUCTIONS = """Choose a finite acyclic graph from all exact selectable catalog declarations.
There is no prescribed capsule order: compatible typed ports and predecessor
edges determine dependencies. One checked leaf covers every deliverable.
Scientific experiment work retains Scientific Evaluation and scientific Delivery.
Prefer specialists; research.generalist, when admitted, is a low-trust fallback
for an uncovered task, with at most two assignments. Its frozen node objective
is an intended outcome, never permission or executable code. Read each supplied
capsule declaration for purpose, ports, operating preconditions and guarantees.
Do not assume an unlisted capsule, synthesize artifact Refs, invent operation
settings or convert types implicitly. Missing capabilities/resources means
INFEASIBLE. All mandatory checks, effects, budgets and independent gates remain.
One host-requested correction may use public deterministic diagnostics against
the unchanged inputs. No live graph mutation or automatic capsule admission.
Passing conformance checks does not certify Generalist output as science."""
