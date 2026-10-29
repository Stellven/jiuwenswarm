"""Small offline runtime regression lane. No provider calls or deployment.

Use the actual code paths with scripted transports before paid benchmark runs.
Existing packet/oracle validation remains a separate check.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
CHECKS = {
    'release': [
        'tests/unit_tests/research/test_capsule_assets.py::CapsuleAssetsTests::test_complete_source_assets_separate_checks_and_no_auto_admission',
        'tests/test_screening_release_m1_5.py::ScreeningReleaseTests::test_repaired_release_passes_real_library_check_association_validation',
        'tests/unit_tests/research/test_typed_planner.py::test_catalog_includes_exact_complete_contracts_and_detects_tampering',
    ],
    'carriers': [
        'tests/test_value_core_complex.py::test_real_requirements_worker_with_scripted_reply_is_not_a_measured_node',
        'tests/unit_tests/research/test_metric_contract.py::test_hypothesis_uses_the_real_restricted_capsule_artifact_interface',
        'tests/unit_tests/research/test_planner_pipeline.py::test_planner_through_independent_gate_and_freeze[valid]',
        'tests/unit_tests/research/test_gate.py::test_evidence_aware_verifier_gets_host_projection_only_for_explicit_v2_profile',
        'tests/unit_tests/research/test_delivery_content.py::DeliveryContentTests::test_exact_negative_science_delivery',
        'tests/unit_tests/research/test_delivery_content.py::DeliveryContentTests::test_frozen_original_stale_closure_remains_rejected',
        'tests/unit_tests/research/test_science.py::ScienceTests::test_payload_incomplete_and_range',
        'tests/unit_tests/research/test_builder_execute_public_data.py',
    ],
    'bridge': ['tests/unit_tests/research/test_bridge.py'],
}
PINNED_FILES = [
    'jiuwenswarm/research/capsules/builder_agent.py',
    'jiuwenswarm/research/capsules/assets.py',
    'jiuwenswarm/research/resources/capsules/capsule_catalog.json',
    'jiuwenswarm/research_assets/catalog.json',
    'jiuwenswarm/research/bridge.py',
]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layer', choices=['all', *CHECKS], default='all')
    parser.add_argument('--output', type=Path, required=True, help='New immutable result directory')
    args = parser.parse_args(argv)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    tests = [node for layer, nodes in CHECKS.items() if args.layer in ('all', layer) for node in nodes]
    command = [sys.executable, '-B', '-m', 'pytest', '--noconftest', '-o', 'addopts=',
               '-p', 'no:cacheprovider', '-q', '--junitxml=' + str(output / 'junit.xml'), *tests]
    before_pins = {name: hashlib.sha256((REPO / name).read_bytes()).hexdigest() for name in PINNED_FILES}
    started = datetime.now(timezone.utc).isoformat()
    clock = time.monotonic()
    try:
        result = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired as error:
        def text(value):
            return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''
        result = subprocess.CompletedProcess(command, 124, text(error.stdout),
            text(error.stderr) + '\nOffline preflight exceeded 180 seconds; no model retry was issued.\n')
    elapsed = time.monotonic() - clock
    (output / 'stdout.txt').write_text(result.stdout, encoding='utf-8')
    (output / 'stderr.txt').write_text(result.stderr, encoding='utf-8')
    cases = []
    if (output / 'junit.xml').exists():
        for item in ET.parse(output / 'junit.xml').iter('testcase'):
            failure = item.find('failure')
            error = item.find('error')
            skipped = item.find('skipped')
            cases.append({'name': item.get('classname', '') + '::' + item.get('name', ''),
                          'outcome': 'failed' if failure is not None or error is not None else 'skipped' if skipped is not None else 'passed',
                          'seconds': float(item.get('time', '0'))})
    pins = {name: hashlib.sha256((REPO / name).read_bytes()).hexdigest() for name in PINNED_FILES}
    record = {'schema': 'cc-cheap-runtime-preflight:1', 'started_at_utc': started,
              'command': command, 'layer': args.layer, 'selected_tests': tests,
              'exit_code': result.returncode, 'elapsed_seconds': elapsed,
              'passed': sum(c['outcome'] == 'passed' for c in cases),
              'failed': sum(c['outcome'] == 'failed' for c in cases),
              'skipped': sum(c['outcome'] == 'skipped' for c in cases), 'tests': cases,
              'source_pins_before': before_pins, 'source_pins': pins,
              'source_changed_during_check': before_pins != pins, 'model_calls': 0, 'deployment_changed': False,
              'status': 'passed' if result.returncode == 0 and cases and all(c['outcome'] == 'passed' for c in cases) and before_pins == pins else 'blocked',
              'scope': 'Actual release/runtime paths with scripted transports and synthetic fixtures; not model quality, endpoint latency, live permissions or full-case qualification.'}
    (output / 'result.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: record[key] for key in ('status', 'passed', 'failed', 'skipped', 'elapsed_seconds', 'model_calls')}))
    return 0 if record['status'] == 'passed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
