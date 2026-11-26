"""Deterministic Monte Carlo scheduler simulator aligned with ``scheduler.py``
and ``TaskGraphExec.tla`` execution semantics.

M1 Legacy (``max_attempts=1``), M2 Static-Only (JSON), and Formal TLA+ (``graph.tla``)
arms are all evaluated through this exact simulator under identical ``seed`` and ``trials``.
"""
from __future__ import annotations

import random
from typing import Any


def simulate_graph(
    document: dict,
    execution_model: dict,
    allowed_effects: set[str] | list[str],
    *,
    trials: int = 100,
    seed: int = 42,
    transient_fail_prob: float = 0.15,
) -> dict[str, Any]:
    """Run ``trials`` Monte Carlo executions of a graph under ``scheduler`` rules.

    Checks structural & runtime invariants on every step:
    - Dependency ordering (`Preds[n]` must be `"done"` before `n` starts)
    - Resource exclusivity (`Exclusive[n]` + detection of unguarded `"diff"` writers)
    - Authority compliance (`effects <= allowed_effects`)
    - Attempt bounds & liveness (`NoStuck`: halting without delivering)
    """
    nodes = {n['node_id']: n for n in document.get('nodes', [])}
    preds = {nid: list(execution_model['preds'].get(nid, [])) for nid in nodes}
    limits = {nid: int(execution_model['limits'].get(nid, 0)) for nid in nodes}
    exclusive = {nid: set(execution_model['exclusive'].get(nid, [])) for nid in nodes}
    deliver_id = execution_model.get('deliver')
    max_parallel = max(1, int(execution_model.get('max_parallel', 4)))
    allowed = set(allowed_effects)

    # Identify actual diff writers & dangling leaves to detect runtime hazards when B0 omits locks/edges
    diff_writers = {
        nid for nid, n in nodes.items()
        if any(o.get('kind') == 'diff' for o in n.get('outputs', []))
    }
    referenced_preds = {p for ps in preds.values() for p in ps}
    dangling_non_deliver = [nid for nid in nodes if nid != deliver_id and nid not in referenced_preds]

    delivered_count = 0
    stuck_count = 0
    violation_count = 0
    authority_violations = 0
    race_violations = 0
    dangling_failures = 0
    wasted_nodes_total = 0
    wasted_turns_total = 0
    failure_reasons: dict[str, int] = {}

    for t in range(trials):
        rng = random.Random(seed + t)
        st = {nid: 'waiting' for nid in nodes}
        att = {nid: 0 for nid in nodes}
        active: list[str] = []
        done_nodes_order: list[str] = []
        turns_spent = 0
        trial_violation = False
        trial_race = False
        trial_auth = False

        # Pre-check runtime dangling-leaf invariant (every node must feed deliver)
        if dangling_non_deliver:
            dangling_failures += 1

        max_ticks = len(nodes) * 20 + 50
        for _tick in range(max_ticks):
            held = {r for a in active for r in exclusive[a]}

            ready = [
                nid for nid in nodes
                if st[nid] == 'waiting'
                and all(st[p] == 'done' for p in preds[nid])
                and att[nid] < limits[nid]
                and not (exclusive[nid] & held)
            ]
            rng.shuffle(ready)
            while ready and len(active) < max_parallel:
                cand = ready.pop(0)
                if exclusive[cand] & {r for a in active for r in exclusive[a]}:
                    continue
                st[cand] = 'active'
                att[cand] += 1
                active.append(cand)
                turns_spent += int((nodes[cand].get('node_limits') or {}).get('turns', 10))

                # Runtime authority violation check (unauthorized effects or least-privilege violation)
                auth_cfg = nodes[cand].get('authority_ceiling') or {}
                node_eff = set(auth_cfg.get('effects', []))
                node_ws = auth_cfg.get('workspace', 'none')
                if not (node_eff <= allowed):
                    trial_auth = True
                    trial_violation = True
                if nodes[cand]['kind'] == 'deliver' and node_ws != 'none':
                    trial_auth = True
                    trial_violation = True
                if nodes[cand]['kind'] in {'inspect', 'investigate', 'build', 'measure'} and node_ws == 'write':
                    trial_auth = True
                    trial_violation = True

                # Physical resource collision check: concurrent diff/write checkout OR concurrent builders!
                active_writers = [
                    a for a in active
                    if a in diff_writers or (nodes[a].get('authority_ceiling') or {}).get('workspace') == 'write'
                ]
                active_builders = [a for a in active if nodes[a]['kind'] == 'build']
                if len(active_writers) >= 2 or len(active_builders) >= 2:
                    trial_race = True
                    trial_violation = True
                if cand in diff_writers and node_ws != 'write':
                    trial_race = True
                    trial_violation = True

            if not active:
                break

            # Advance one random active node to completion or transient check failure
            nxt = rng.choice(active)
            active.remove(nxt)
            fail_p = transient_fail_prob if nodes[nxt]['kind'] in {'integrate', 'build', 'measure'} else 0.0
            if att[nxt] < limits[nxt] and rng.random() < fail_p:
                st[nxt] = 'waiting'
            elif att[nxt] == limits[nxt] and rng.random() < (fail_p * 0.5 if limits[nxt] <= 1 else 0.0):
                st[nxt] = 'failed'
            else:
                st[nxt] = 'done'
                done_nodes_order.append(nxt)

        delivered = (
            deliver_id in st
            and st[deliver_id] == 'done'
            and all(v == 'done' for v in st.values())
            and not dangling_non_deliver
            and not trial_violation
        )
        failed = any(v == 'failed' for v in st.values())

        if trial_auth:
            authority_violations += 1
        if trial_race:
            race_violations += 1
        if trial_violation:
            violation_count += 1

        if delivered:
            delivered_count += 1
        else:
            # Stuck if not delivered cleanly (either waiting starved, failed, or contract violated)
            stuck_count += 1
            wasted_nodes_total += len(done_nodes_order)
            wasted_turns_total += turns_spent
            if trial_auth:
                reason = 'authority_exceeded'
            elif trial_race:
                reason = 'checkout_write_race'
            elif dangling_non_deliver:
                reason = 'dangling_unjoined_leaf'
            elif any(st[n] == 'waiting' and limits[n] == 0 for n in nodes):
                reason = 'zero_attempt_starvation'
            elif failed:
                reason = 'attempt_exhaustion_failure'
            else:
                reason = 'incomplete_graph_halt'
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1

    failed_runs = max(0, trials - delivered_count)
    return {
        'trials': trials,
        'seed': seed,
        'transient_fail_prob': transient_fail_prob,
        'delivered': delivered_count,
        'stuck_or_failed': stuck_count,
        'delivery_rate': round(delivered_count / trials, 4),
        'stuck_rate': round(stuck_count / trials, 4),
        'contract_violation_rate': round(violation_count / trials, 4),
        'authority_violations': authority_violations,
        'race_violations': race_violations,
        'dangling_failures': dangling_failures,
        'wasted_nodes_per_trial': round(wasted_nodes_total / trials, 2),
        'wasted_nodes_per_failure': round(wasted_nodes_total / failed_runs, 2) if failed_runs else 0.0,
        'wasted_turns_per_trial': round(wasted_turns_total / trials, 1),
        'wasted_turns_per_failure': round(wasted_turns_total / failed_runs, 1) if failed_runs else 0.0,
        'failure_reasons': failure_reasons,
    }
