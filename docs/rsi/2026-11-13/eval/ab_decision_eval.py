#!/usr/bin/env python3
"""Offline evaluation of factory.methodology_ab decisions on recorded Satay A/B experiments.

Fallback RSI target. No lab, GPU or model. About 20-60 s on Satay (bootstrap simulation).

  python3 -I eval/ab_decision_eval.py                                   # frozen gate + AB.md 1.0.0 policy
  python3 -I eval/ab_decision_eval.py --policy examples/power_aware_policy.py:decide
  python3 -I eval/ab_decision_eval.py --gate my_gate.py:evaluate --policy my_policy.py:decide

Data: fixtures/abba.json, 22 recorded ABBA sets (10-13 Nov). Split by time:
  TRAIN      = sets recorded before 2026-11-12T00:00Z (J-OM8 .. J-OM11): fit any noise model here.
  VALIDATION = everything later (J-OM12, factory lab runs, J-OM13, J-ASK1): never tune on these.

Part 1, operating characteristics: the gate's false-improvement rate (true effect 0) and power
at effects of 8% and 12%, by rounds. Simulated by resampling within-arm residuals, separately
from TRAIN and VALIDATION noise, so you can see whether a rule transfers.

Part 2, decisions: for every VALIDATION comparison, the gate verdict and the policy's ACTION.
Each action is judged against what the evidence available at that moment justifies (the rubric
below). It is not judged against a single preferred answer:
  keep                 justified only if the gate says improved. Keeping a component labelled
                       harmful is a HARD failure (exit 1).
  reject               a negative claim (revert as "does not help"). Justified if the gate says
                       regressed, or the design had >= 0.8 power at the minimum effect of interest.
                       Otherwise it is an UNJUSTIFIED NEGATIVE CLAIM.
  inconclusive         no claim either way (revert or keep_dormant without a negative claim).
                       Justified when null and underpowered. On a regressed verdict it is a
                       MISSED CLEAR DECISION.
  replicate:<rounds>   justified if null, the planned design reaches >= 0.8 power, and its lab
                       minutes fit the stated budget. Otherwise it is WASTED LAB TIME.
Power for each decision uses only noise recorded BEFORE that experiment (expanding window), so
the judgement reflects the evidence available at the time, not hindsight noise.
Labels (harmful / beneficial / neutral / unknown) come from LATER and pooled evidence and are
used only for the hard keep check and for reporting; they are hindsight, not ground truth.
"""
import argparse, importlib.util, json, math, os, random, runpy, statistics, sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
SPLIT = datetime(2026, 11, 12, tzinfo=timezone.utc).timestamp()
MEI = 0.08               # minimum effect of interest (fraction less time per token)
MIN_PER_RUN = {32: 1.8, 64: 3.0}   # recorded quick / bare contract engine-run minutes on Satay

# Hindsight labels by arm/component name; source in comment.
LABELS = {
    'expert_fill': 'beneficial', 'fill': 'beneficial', 'fill_random': 'beneficial', 'fr': 'beneficial',
    'frd': 'beneficial', 'frd16': 'beneficial',     # frd16 improved in J-OM8b, J-OM9, J-OM10, J-OM10b, spool-f19094c8
    'expert_pregate': 'beneficial', 'pg8': 'beneficial', 'pg8b': 'beneficial', 'pg10': 'beneficial',
    'factory': 'beneficial', 'factory_t4': 'beneficial',   # J-OM13
    'mmap_advice': 'harmful', 'router_prefetch': 'harmful', 'pg16': 'harmful',  # repeated 0.47-0.64 ratios
    'thread_names': 'neutral',                      # observability only, measure: none
}


def load(spec, default):
    if spec in (None, 'frozen', 'v1'):
        return default
    path, _, name = spec.partition(':')
    s = importlib.util.spec_from_file_location(Path(path).stem, path)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return getattr(m, name)


def frozen_gate():
    root = Path(os.environ.get('SIMINFENG_ROOT', '~/projects/siminfeng')).expanduser()
    return runpy.run_path(str(root / 'cc/abrun/gate.py'))['evaluate']


def policy_v1(c):
    """AB.md 1.0.0, step 9: keep only on gate improved; otherwise revert with the null/regression as reason."""
    return 'keep' if c['verdict'] == 'improved' else 'reject'


def residuals(sets):
    out = []
    for s in sets:
        for xs in s['inputs'].values():
            xs = [x for x in xs if isinstance(x, (int, float))]
            if len(xs) >= 2:
                m = statistics.mean(xs); k = math.sqrt(len(xs) / (len(xs) - 1))
                out += [(x / m - 1) * k for x in xs]
    return out


def p_improved(gate, res, delta, rounds, n=1500, seed=7):
    rng = random.Random(seed); hits = 0
    for _ in range(n):
        base = [900 * (1 + rng.choice(res)) for _ in range(2 * rounds)]
        cand = [900 / (1 + delta) * (1 + rng.choice(res)) for _ in range(2 * rounds)]
        arms = dict(base=[dict(eval_ms_per_token=x) for x in base], candidate=[dict(eval_ms_per_token=x) for x in cand])
        hits += gate(arms, metric='eval_ms_per_token', direction='lower')['comparisons']['candidate']['verdict'] == 'improved'
    return hits / n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gate'); ap.add_argument('--policy')
    ap.add_argument('--budget-min', type=float, default=30, help='lab minutes a policy may request per decision')
    ap.add_argument('--fixture', default=str(HERE / 'fixtures/abba.json'))
    a = ap.parse_args()
    gate = load(a.gate, frozen_gate()); policy = load(a.policy, policy_v1)
    sets = json.load(open(a.fixture))['sets']
    train = [s for s in sets if s['mtime'] < SPLIT]; val = [s for s in sets if s['mtime'] >= SPLIT]
    r_train, r_val = residuals(train), residuals(val)
    print(f'TRAIN {len(train)} sets / {len(r_train)} residuals (sd {statistics.pstdev(r_train):.3f}); '
          f'VALIDATION {len(val)} sets / {len(r_val)} residuals (sd {statistics.pstdev(r_val):.3f})')
    print('\nPart 1: P(gate says improved). Effect 0 = false-improvement rate.')
    print('rounds  noise  effect0  effect8%  effect12%')
    power = {}
    for k in (1, 2, 4):
        for label, res in (('train', r_train), ('val', r_val)):
            row = [p_improved(gate, res, d, k) for d in (0.0, 0.08, 0.12)]
            power[(k, label)] = row
            print(f'{k:>6}  {label:>5}  {row[0]:7.3f}  {row[1]:8.3f}  {row[2]:9.3f}')
    worst_fp = max(v[0] for v in power.values())

    def prior_power(s):
        # Noise known at decision time: every set recorded before this one (expanding window).
        prior = residuals([t for t in sets if t['mtime'] < s['mtime']])
        cache = {}
        def power_at(rounds, effect=MEI):
            if (rounds, effect) not in cache:
                cache[(rounds, effect)] = p_improved(gate, prior, effect, rounds, n=600)
            return cache[(rounds, effect)]
        return power_at

    print('\nPart 2: decisions on VALIDATION comparisons')
    tally = dict(keep_harmful=0, unjustified_negative=0, missed_clear=0, wasted_lab=0, lab_minutes=0.0, justified=0)
    for s in val:
        power_at = prior_power(s)
        base = [dict(eval_ms_per_token=x) for x in s['inputs']['base']]
        for arm in s['inputs']:
            if arm == 'base':
                continue
            g = gate(dict(base=base, candidate=[dict(eval_ms_per_token=x) for x in s['inputs'][arm]]),
                     metric='eval_ms_per_token', direction='lower')['comparisons']['candidate']
            name = s.get('component') if arm == 'candidate' else arm
            rounds = max(1, len(s['inputs']['base']) // 2)
            ctx = dict(set=s['id'], arm=name, verdict=g['verdict'], ratio=g.get('ratio'), rounds=rounds,
                       n_predict=s.get('n_predict'), minutes_per_run=MIN_PER_RUN.get(s.get('n_predict'), 3.0),
                       budget_min=a.budget_min, mei=MEI, power_at=power_at)
            action = policy(ctx)
            label = LABELS.get(name, 'unknown')
            if name == 'thread_names':   # observability component, measure: none -> not a speed decision
                print(f"{s['id']:15} {name:15} skipped: observability acceptance, not scored as performance")
                continue
            judged = 'justified'
            pw = power_at(rounds)
            if action == 'keep':
                if g['verdict'] != 'improved':
                    judged = 'UNJUSTIFIED KEEP'
                if label == 'harmful':
                    tally['keep_harmful'] += 1; judged = 'HARD FAIL: keeps harmful'
            elif action == 'reject':
                if g['verdict'] == 'null' and pw < 0.8:
                    tally['unjustified_negative'] += 1; judged = f'unjustified negative claim (power {pw:.2f})'
            elif action == 'inconclusive':
                if g['verdict'] == 'regressed':
                    tally['missed_clear'] += 1; judged = 'missed clear decision'
            elif action.startswith('replicate:'):
                k = int(action.split(':')[1]); minutes = 4 * k * ctx['minutes_per_run']
                tally['lab_minutes'] += minutes
                pk = power_at(k)
                if g['verdict'] != 'null' or pk < 0.8 or minutes > a.budget_min:
                    tally['wasted_lab'] += 1; judged = f'wasted lab time (power {pk:.2f}, {minutes:.0f} min)'
            tally['justified'] += judged == 'justified'
            print(f"{s['id']:15} {str(name):15} ratio={g.get('ratio') or 0:6.3f} {g['verdict']:9} -> {action:14} [{label}] {judged}")
    print('\nSummary', json.dumps(dict(worst_false_improvement_rate=round(worst_fp, 3), **tally)))
    sys.exit(1 if tally['keep_harmful'] or worst_fp > 0.05 else 0)


if __name__ == '__main__':
    main()
