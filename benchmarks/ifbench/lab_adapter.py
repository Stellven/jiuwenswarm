"""M2 Lab Agent command adapter for ifbench.

Bridges ``jiuwenswarm.factory.lab_agent`` (``--adapter command``) to ``ifbench``:

    jiuwenswarm-factory lab-agent serve --adapter command \\
        --command "python -m benchmarks.ifbench.lab_adapter {package} {output} {payloads}"

Reads a ``factory.lab-package/1`` JSON document, runs ``ifbench`` (or ingests a
pre-collected verified ``ifbench`` bundle via ``--bundle`` / ``IFBENCH_BUNDLE``),
and writes ``{output}/report.json`` (body for ``factory.lab-report/1``; identity
fields are filled in by ``LabAgent.report``) plus attachments under
``{output}/files/``.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import sys
from typing import Any

from . import __version__


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def _extract_bundle_metrics(bundle_dir: Path, rev4_dir: Path | None = None) -> dict[str, Any]:
    """Extract canonical metrics and check verdicts from a verified ifbench bundle."""
    bundle_dir = Path(bundle_dir)
    handoff = _read_json(bundle_dir / 'handoff.json')
    selection_path = bundle_dir / 'preflight' / 'final-baseline-selection.json'
    selection = _read_json(selection_path) if selection_path.is_file() else {}

    coverage_path = (rev4_dir / 'coverage-rev4.json') if (rev4_dir and (rev4_dir / 'coverage-rev4.json').is_file()) else (bundle_dir / 'coverage.json')
    coverage = _read_json(coverage_path) if coverage_path.is_file() else {}

    rev4_summary_path = (rev4_dir / 'rev4-summary.json') if rev4_dir else None
    rev4_summary = _read_json(rev4_summary_path) if (rev4_summary_path and rev4_summary_path.is_file()) else {}

    metrics: dict[str, dict[str, Any]] = {}
    checks: dict[str, dict[str, str]] = {}

    perf = selection.get('performance') or {}
    reqs = perf.get('requests') or []
    if reqs:
        decode_samples = [float(r['engine_decode_tok_s']) for r in reqs if r.get('engine_decode_tok_s') is not None]
        e2e_samples = [float(r['e2e_output_tok_s']) for r in reqs if r.get('e2e_output_tok_s') is not None]
        ttft_samples = [float(r['first_nonempty_event_s']) * 1000.0 for r in reqs if r.get('first_nonempty_event_s') is not None]
        if decode_samples:
            metrics['engine_decode_tok_s'] = {
                'value': float(perf.get('aggregate_engine_decode_tok_s', statistics.mean(decode_samples))),
                'samples': decode_samples,
                'statistic': 'mean',
                'request': 'pp512_tg32',
            }
        if e2e_samples:
            metrics['e2e_output_tok_s'] = {
                'value': float(perf.get('aggregate_e2e_output_tok_s', statistics.mean(e2e_samples))),
                'samples': e2e_samples,
                'statistic': 'mean',
                'request': 'pp512_tg32',
            }
        if ttft_samples:
            metrics['client_ttft_ms'] = {
                'value': float(statistics.mean(ttft_samples)),
                'samples': ttft_samples,
                'statistic': 'mean',
                'request': 'pp512_tg32',
            }

    benches = selection.get('benchmarks') or {}
    gsm = (benches.get('gsm8k_sample') or {}).get('scores') or {}
    if 'gsm8k exact_match,strict-match' in gsm:
        val = float(gsm['gsm8k exact_match,strict-match'])
        metrics['gsm8k_exact_match'] = {'value': val, 'samples': [val], 'statistic': 'single', 'request': 'gsm8k_sample'}
        checks['gsm8k_gate'] = {
            'verdict': 'pass' if val >= 1.0 else 'fail',
            'detail': f'GSM8K strict exact match = {val:.4f} (sample_len={gsm.get("gsm8k sample_len")})',
        }

    ruler = (benches.get('ruler_sample') or {}).get('scores') or {}
    ruler_scores = [float(v) for k, v in ruler.items() if k.endswith('selected_sample_match')]
    if ruler_scores:
        mean_r = float(statistics.mean(ruler_scores))
        metrics['ruler_match'] = {'value': mean_r, 'samples': ruler_scores, 'statistic': 'mean', 'request': 'ruler_sample'}
        checks['ruler_gate'] = {
            'verdict': 'pass' if all(s >= 1.0 for s in ruler_scores) else 'fail',
            'detail': f'RULER match = {mean_r:.4f} across {len(ruler_scores)} tasks',
        }

    infer = (benches.get('infer_check_sample') or {}).get('scores') or {}
    if 'determinism_score_mean' in infer:
        det = float(infer['determinism_score_mean'])
        metrics['determinism_score'] = {'value': det, 'samples': [det], 'statistic': 'single', 'request': 'infer_check_sample'}
        checks['determinism_gate'] = {
            'verdict': 'pass' if det >= 1.0 else 'fail',
            'detail': f'infer-check determinism = {det:.4f} (identical={infer.get("fully_identical_prompts")}/{infer.get("prompts")})',
        }

    gpu_ws = (coverage.get('M.gpu_working_set') or {}).get('value')
    if isinstance(gpu_ws, (int, float)):
        metrics['gpu_working_set_gib'] = {'value': float(gpu_ws), 'samples': [float(gpu_ws)], 'statistic': 'single'}

    host_mem = (coverage.get('M.host_memory') or {}).get('value')
    if isinstance(host_mem, dict) and isinstance(host_mem.get('anonymous'), (int, float)):
        anon = float(host_mem['anonymous'])
        metrics['host_anonymous_gib'] = {'value': anon, 'samples': [anon], 'statistic': 'single'}

    mem_min = (coverage.get('M.mem_available_min') or {}).get('value')
    if isinstance(mem_min, (int, float)):
        metrics['mem_available_min_gib'] = {'value': float(mem_min), 'samples': [float(mem_min)], 'statistic': 'min'}

    ttr = (coverage.get('L0.time_to_ready') or {}).get('value')
    if isinstance(ttr, (int, float)):
        metrics['cold_load_seconds'] = {'value': float(ttr), 'samples': [float(ttr)], 'statistic': 'single'}

    if isinstance(gpu_ws, (int, float)) and isinstance(mem_min, (int, float)):
        ok_mem = float(gpu_ws) <= 64.0 and float(mem_min) >= 8.0
        checks['memory_budget_gate'] = {
            'verdict': 'pass' if ok_mem else 'fail',
            'detail': f'gpu_working_set={gpu_ws} GiB, mem_available_min={mem_min} GiB',
        }

    trunc = (rev4_summary.get('L1.truncation_rate') or {}).get('value')
    if isinstance(trunc, dict):
        selected_total = (trunc.get('selected') or {}).get('total') or {}
        if selected_total.get('percent') is not None:
            pct = float(selected_total['percent'])
            checks['zero_truncation_gate'] = {
                'verdict': 'pass' if pct == 0.0 else 'fail',
                'detail': f'selected formal truncation={selected_total.get("length", 0)}/{selected_total.get("requests", 0)} ({pct:.2f}%)',
            }

    disc = coverage.get('L2.disconnect_recovery') or {}
    if disc.get('status') == 'ok':
        checks['disconnect_recovery_gate'] = {
            'verdict': 'pass',
            'detail': 'L2.disconnect_recovery passed (slot returned idle, anonymous memory delta within tolerance)',
        }

    storage = (rev4_summary.get('M.storage_read_split') or {}).get('value') or {}
    pf_bounds = storage.get('prefill_read_GB_bounds')
    dc_bounds = storage.get('decode_read_GB_bounds')
    if isinstance(pf_bounds, list) and len(pf_bounds) == 2:
        metrics['storage_read_prefill_gb'] = {
            'value': float(pf_bounds[1]),
            'samples': [float(pf_bounds[0]), float(pf_bounds[1])],
            'statistic': 'max',
            'request': 'pp512_tg32',
        }
    if isinstance(dc_bounds, list) and len(dc_bounds) == 2:
        metrics['storage_read_decode_gb'] = {
            'value': float(dc_bounds[1]),
            'samples': [float(dc_bounds[0]), float(dc_bounds[1])],
            'statistic': 'max',
            'request': 'pp512_tg32',
        }

    return {
        'handoff': handoff,
        'selection': selection,
        'metrics': metrics,
        'checks': checks,
    }


def build_lab_report(
    package: dict[str, Any],
    extracted: dict[str, Any],
    *,
    runner_label: str = f'ifbench/{__version__}',
    deviations: list[str] | None = None,
    limits: list[str] | None = None,
) -> dict[str, Any]:
    """Build a ``factory.lab-report/1`` body matching the sealed ``package``."""
    lab_task = package['lab_task']
    contract_doc = package['contract']['document']
    contract_metrics = (contract_doc.get('measurement') or {}).get('metrics') or {}
    available_metrics = extracted.get('metrics') or {}
    available_checks = extracted.get('checks') or {}
    want_samples = bool((lab_task.get('deliverables') or {}).get('raw_samples'))

    results: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    not_run: list[dict[str, Any]] = []

    for test in lab_task.get('tests', []):
        test_id = test['id']
        arms = list(test.get('arms') or [])
        test_requests = test.get('requests')
        missing_parts: list[str] = []

        for metric_name in test.get('measure') or []:
            if metric_name not in available_metrics:
                missing_parts.append(f'metric:{metric_name}')
                continue
            unit = (contract_metrics.get(metric_name) or {}).get('unit', '')
            sample_data = available_metrics[metric_name]
            for arm in arms:
                row: dict[str, Any] = {
                    'test_id': test_id,
                    'arm': arm,
                    'metric': metric_name,
                    'unit': unit,
                    'value': sample_data['value'],
                }
                if sample_data.get('statistic'):
                    row['statistic'] = sample_data['statistic']
                if sample_data.get('samples') and (want_samples or len(sample_data['samples']) > 1):
                    row['samples'] = list(sample_data['samples'])
                elif want_samples:
                    row['samples'] = [sample_data['value']]
                req = sample_data.get('request')
                if req and (test_requests is None or req in test_requests):
                    row['request'] = req
                results.append(row)

        check_name = test.get('check')
        if check_name:
            if check_name not in available_checks:
                missing_parts.append(f'check:{check_name}')
            else:
                verdict_info = available_checks[check_name]
                for arm in (arms or [None]):
                    entry: dict[str, Any] = {
                        'test_id': test_id,
                        'check': check_name,
                        'verdict': verdict_info['verdict'],
                    }
                    if arm is not None:
                        entry['arm'] = arm
                    if verdict_info.get('detail'):
                        entry['detail'] = verdict_info['detail']
                    checks.append(entry)

        if missing_parts:
            not_run.append({
                'test_id': test_id,
                'reason': 'Not available in bundle: ' + ', '.join(missing_parts),
            })

    has_not_run = bool(not_run) or any(c['verdict'] == 'not_run' for c in checks)
    outcome = 'partial' if has_not_run else 'completed'

    report: dict[str, Any] = {
        'outcome': outcome,
        'summary': (
            f'ifbench {__version__} lab report: {len(results)} metric result(s), '
            f'{sum(1 for c in checks if c["verdict"] == "pass")}/{len(checks)} check(s) passed, '
            f'{len(not_run)} test(s) not run.'
        ),
        'setup': {
            'profile': (contract_doc.get('target') or {}).get('profile', 'spark-gb10'),
            'runner': runner_label,
            'deviations': list(deviations or []),
        },
        'results': results,
        'checks': checks,
        'not_run': not_run,
        'limits': list(limits or [
            'Compact text-only baseline sample; does not cover full benchmark suites or multimodal workloads.',
            'Native llama.cpp lacks T3 counters (L3.step_phase_split, L4.expert_selection, M.expert_tier_share, L5.fastpath_fallback_rate).',
        ]),
    }

    wanted_sections = (lab_task.get('deliverables') or {}).get('sections') or []
    if wanted_sections:
        report['sections'] = {
            sec: f'Provided by ifbench {__version__} adapter for section {sec}.'
            for sec in wanted_sections
        }
    return report


def run_command_adapter(
    package_path: Path,
    output_dir: Path,
    payloads_path: Path | None = None,
    *,
    bundle_dir: Path | None = None,
    rev4_dir: Path | None = None,
    config_path: Path | None = None,
    set_name: str = 'smoke',
) -> dict[str, Any]:
    """Execute the CommandAdapter contract: read package, write report.json + files/."""
    package = _read_json(package_path)
    out = Path(output_dir)
    files_dir = out / 'files'
    files_dir.mkdir(parents=True, exist_ok=True)

    if bundle_dir is None and config_path is not None:
        from .bundle import pack
        from .run import run as run_ifbench
        run_root = out / 'ifbench-runs'
        run_root.mkdir(parents=True, exist_ok=True)
        run_ifbench(str(config_path), set_name, str(run_root))
        run_dirs = sorted(p for p in run_root.iterdir() if p.is_dir() and not p.name.startswith('.'))
        packed = pack([str(p) for p in run_dirs], str(out / 'ifbench-bundle'), scope='lab-agent command run')
        bundle_dir = Path(packed['bundle'])

    if bundle_dir is None:
        raise ValueError('Provide --bundle / IFBENCH_BUNDLE or --config / IFBENCH_CONFIG')

    extracted = _extract_bundle_metrics(bundle_dir, rev4_dir=rev4_dir)
    report = build_lab_report(package, extracted)

    # Write requested deliverable files (or default summary attachment)
    summary_payload = {
        'ifbench_version': __version__,
        'metrics': extracted['metrics'],
        'checks': extracted['checks'],
    }
    wanted_files = (package['lab_task'].get('deliverables') or {}).get('files') or []
    if wanted_files:
        for item in wanted_files:
            name = item['name']
            (files_dir / name).write_text(json.dumps(summary_payload, indent=2) + '\n', encoding='utf-8')
    else:
        (files_dir / 'ifbench_summary.json').write_text(json.dumps(summary_payload, indent=2) + '\n', encoding='utf-8')

    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='python -m benchmarks.ifbench.lab_adapter',
        description='M2 LabAgent CommandAdapter bridge for ifbench.',
    )
    parser.add_argument('package', type=Path, help='Path to sealed factory.lab-package/1 JSON')
    parser.add_argument('output', type=Path, help='Output directory for report.json and files/')
    parser.add_argument('payloads', type=Path, nargs='?', help='Optional payloads.json from LabAgent')
    parser.add_argument('--bundle', type=Path, default=Path(os.environ['IFBENCH_BUNDLE']) if os.environ.get('IFBENCH_BUNDLE') else None,
                        help='Pre-collected verified ifbench bundle directory')
    parser.add_argument('--rev4', type=Path, default=Path(os.environ['IFBENCH_REV4_DIR']) if os.environ.get('IFBENCH_REV4_DIR') else None,
                        help='Optional rev4 offline supplement directory')
    parser.add_argument('--config', type=Path, default=Path(os.environ['IFBENCH_CONFIG']) if os.environ.get('IFBENCH_CONFIG') else None,
                        help='ifbench TOML config for live execution mode')
    parser.add_argument('--set', dest='set_name', default=os.environ.get('IFBENCH_SET', 'smoke'),
                        help='ifbench config set name for live execution mode')
    args = parser.parse_args(argv)
    run_command_adapter(
        args.package,
        args.output,
        args.payloads,
        bundle_dir=args.bundle,
        rev4_dir=args.rev4,
        config_path=args.config,
        set_name=args.set_name,
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
