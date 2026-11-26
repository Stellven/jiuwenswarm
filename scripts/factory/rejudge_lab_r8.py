"""Rejudge a completed R8 rerun from its recorded process samples. No engine is started."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.factory import lab_v4_fast as lab
from scripts.factory import lab_v4_quiet as quiet


def correct_sample(sample, runner_pid, original, amended):
    if sample['phase'] not in ('during', 'end') or not sample.get('cpu'):
        return
    cpu = sample['cpu']
    tree = {runner_pid}
    while children := {p['pid'] for p in sample['processes'] if p['ppid'] in tree} - tree:
        tree.update(children)
    cpu['runner_tree'] = sorted(tree)
    original_cpu_reasons = quiet.cpu_issues(cpu, original)
    reasons = [reason for reason in sample['reasons'] if reason not in original_cpu_reasons]
    reasons.extend(quiet.cpu_issues(cpu, amended))
    sample['launch_reasons'], sample['launch_ok'] = sample['reasons'], sample['ok']
    sample['reasons'], sample['ok'] = reasons, not reasons


def main(source, output, runner_pid, attribution):
    if source.resolve() == output.resolve():
        raise ValueError('Output must be separate from the original campaign')
    raw = source.read_bytes()
    report = json.loads(raw)
    original = report['quiet_policy']
    if original != quiet.policy(quiet.REVISED):
        raise ValueError('Unexpected launch protocol')
    expected = {(a, s, t) for a in ('B', 'P') for s in ('p512', 'p2048') for t in ('cold', 'warm')}
    if len(report['rows']) != 8 or {(r['arm'], r['request'], r['state']) for r in report['rows']} != expected:
        raise ValueError('Incomplete or duplicate campaign cells')
    amended = dict(original, min_cpu_window_s=0.5, exempt_runner_tree=True,
                   cpu_scope='Percent of one core per foreign process; exclude the lab runner, its tree and the measured server tree. Ignore CPU intervals shorter than 0.5 seconds.')
    for row in report['rows']:
        evidence = row['quiet']
        recorded = dict(status=evidence['status'], reasons=evidence['reasons'])
        # Preserve non-monitor exclusions (e.g. an incomplete request) independently.
        launch_issues = quiet.evidence_issues(evidence['samples'], original)
        other = [reason for reason in recorded['reasons'] if reason not in launch_issues]
        for sample in evidence['samples']:
            correct_sample(sample, runner_pid, original, amended)
        reasons = list(dict.fromkeys(other + quiet.evidence_issues(evidence['samples'], amended)))
        status = 'excluded' if reasons else 'accepted'
        row['launch_verdict'] = recorded
        row['corrected_verdict'] = dict(status=status, reasons=reasons)
        evidence.update(status=status, reasons=reasons)
    report['launch_quiet_policy'] = original
    report['quiet_policy'] = amended
    report['adjudication'] = dict(original_file='launch-verdicts.json', original_sha256=hashlib.sha256(raw).hexdigest(),
                                  runner_pid=runner_pid, basis='Owner amendment 2026-11-26 16:12 ET; native recorded samples only.')
    report['process_attribution'] = json.loads(attribution.read_text())
    lab.aggregate(report, lab.baseline(report['baseline']['path']))
    lab.save(output, report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--runner-pid', required=True, type=int)
    parser.add_argument('--attribution', required=True, type=Path)
    args = parser.parse_args()
    main(args.source, args.output, args.runner_pid, args.attribution)
