"""Integration tests for benchmarks.ifbench and M2 factory lab protocol."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest
from jsonschema import Draft202012Validator

from benchmarks.ifbench.bundle import digest, verify
from benchmarks.ifbench.lab_adapter import run_command_adapter
from benchmarks.ifbench.requests import Capture, rates
from benchmarks.ifbench.run import checkpoint_files
from jiuwenswarm.factory import contract_v2
from jiuwenswarm.factory.lab_agent import CommandAdapter, LabAgent, serve
from jiuwenswarm.factory.lab_mailbox import Mailbox
from jiuwenswarm.factory.lab_manager import report_problems

REPO = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO / 'jiuwenswarm/factory/contracts/muse-nvfp4-spark-v2.json'
SAMPLE_REPORT_PATH = REPO / 'benchmarks/ifbench/examples/muse-nvfp4-baseline-lab-report-1.json'
SCHEMAS = REPO / 'jiuwenswarm/factory/schemas'


def _schema_validator(filename: str) -> Draft202012Validator:
    doc = json.loads((SCHEMAS / filename).read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(doc)
    return Draft202012Validator(doc, format_checker=Draft202012Validator.FORMAT_CHECKER)


def _sample_lab_task() -> dict:
    return {
        'schema': 'factory.lab-task/1',
        'lab_task_id': 'muse-nvfp4-baseline-20261126',
        'purpose': 'Validate Muse NVFP4 compact baseline report through M2 lab protocol.',
        'contract': {'id': 'muse-nvfp4-spark-v2'},
        'subjects': {
            'baseline_engine': {
                'kind': 'native_build',
                'identity': {
                    'executable_sha256': 'd166c0445434822fa880b5e212c4b8ac05d58b97695933c6ac523366d88981c7',
                },
            },
        },
        'arms': {'baseline': {'subject': 'baseline_engine'}},
        'tests': [
            {
                'id': 'perf_pp512_tg32',
                'arms': ['baseline'],
                'requests': ['pp512_tg32'],
                'measure': [
                    'engine_decode_tok_s',
                    'e2e_output_tok_s',
                    'client_ttft_ms',
                    'storage_read_prefill_gb',
                    'storage_read_decode_gb',
                ],
            },
            {
                'id': 'quality_gsm8k',
                'arms': ['baseline'],
                'requests': ['gsm8k_sample'],
                'measure': ['gsm8k_exact_match'],
                'check': 'gsm8k_gate',
            },
            {
                'id': 'quality_ruler',
                'arms': ['baseline'],
                'requests': ['ruler_sample'],
                'measure': ['ruler_match'],
                'check': 'ruler_gate',
            },
            {
                'id': 'stability_determinism',
                'arms': ['baseline'],
                'requests': ['infer_check_sample'],
                'measure': ['determinism_score'],
                'check': 'determinism_gate',
            },
            {'id': 'gate_truncation', 'arms': ['baseline'], 'check': 'zero_truncation_gate'},
            {
                'id': 'resources_memory_load',
                'arms': ['baseline'],
                'measure': [
                    'gpu_working_set_gib',
                    'host_anonymous_gib',
                    'mem_available_min_gib',
                    'cold_load_seconds',
                ],
                'check': 'memory_budget_gate',
            },
            {'id': 'stability_disconnect', 'arms': ['baseline'], 'check': 'disconnect_recovery_gate'},
        ],
        'deliverables': {'raw_samples': True, 'files': []},
    }


def _make_synthetic_bundle(root: Path) -> tuple[Path, Path]:
    bundle = root / 'bundle'
    (bundle / 'preflight').mkdir(parents=True)
    (bundle / 'handoff.json').write_text(json.dumps({'schema_version': 1, 'runs': []}), encoding='utf-8')
    (bundle / 'preflight' / 'final-baseline-selection.json').write_text(json.dumps({
        'validated': True,
        'benchmarks': {
            'gsm8k_sample': {'scores': {'gsm8k sample_len': 3, 'gsm8k exact_match,strict-match': 1.0}},
            'ruler_sample': {'scores': {'niah_single_2 selected_sample_match': 1.0, 'ruler_qa_hotpot selected_sample_match': 1.0}},
            'infer_check_sample': {'scores': {'determinism_score_mean': 1.0, 'prompts': 1, 'fully_identical_prompts': 1}},
        },
        'performance': {
            'aggregate_engine_decode_tok_s': 0.22887467211303728,
            'aggregate_e2e_output_tok_s': 0.06418469785813821,
            'requests': [
                {'engine_decode_tok_s': 0.2227, 'e2e_output_tok_s': 0.0640, 'first_nonempty_event_s': 387.1},
                {'engine_decode_tok_s': 0.2272, 'e2e_output_tok_s': 0.0634, 'first_nonempty_event_s': 386.2},
                {'engine_decode_tok_s': 0.2372, 'e2e_output_tok_s': 0.0653, 'first_nonempty_event_s': 376.6},
            ],
        },
    }), encoding='utf-8')
    rev4 = root / 'rev4'
    rev4.mkdir(parents=True)
    (rev4 / 'coverage-rev4.json').write_text(json.dumps({
        'L0.time_to_ready': {'status': 'ok', 'value': 283.5},
        'M.gpu_working_set': {'status': 'ok', 'value': 45.66},
        'M.host_memory': {'status': 'ok', 'value': {'anonymous': 0.22}},
        'M.mem_available_min': {'status': 'ok', 'value': 70.64},
        'L2.disconnect_recovery': {'status': 'ok', 'value': {'passed': True}},
    }), encoding='utf-8')
    (rev4 / 'rev4-summary.json').write_text(json.dumps({
        'L1.truncation_rate': {'status': 'ok', 'value': {'selected': {'total': {'requests': 7, 'length': 0, 'percent': 0.0}}}},
        'M.storage_read_split': {
            'status': 'ok',
            'value': {
                'prefill_read_GB_bounds': [1709.175566336, 1724.563214336],
                'decode_read_GB_bounds': [506.202349568, 522.807201792],
            },
        },
    }), encoding='utf-8')
    return bundle, rev4


def test_muse_nvfp4_contract_v2_is_valid_and_inputs_match():
    doc = json.loads(CONTRACT_PATH.read_text(encoding='utf-8'))
    assert doc['schema'] == 'factory.contract/2'
    assert contract_v2.problems(doc) == []
    binding = {
        'model': '/lab/Muse-Spark-Open-816B-A42B-NVFP4-lossless.gguf',
        'inputs': {name: str(REPO / spec['repo_path']) for name, spec in doc['inputs'].items()},
    }
    assert contract_v2.verify_inputs(doc, binding) == []
    resolved = contract_v2.resolve(doc, binding)
    assert resolved['argv'][:2] == ['-m', '/lab/Muse-Spark-Open-816B-A42B-NVFP4-lossless.gguf']


def test_muse_nvfp4_baseline_sample_report_passes_schema_and_contract():
    doc = json.loads(CONTRACT_PATH.read_text(encoding='utf-8'))
    csha = contract_v2.file_sha256(CONTRACT_PATH)
    sample = json.loads(SAMPLE_REPORT_PATH.read_text(encoding='utf-8'))
    _schema_validator('lab-report-1.schema.json').validate(sample)
    assert sample['contract'] == {'id': 'muse-nvfp4-spark-v2', 'sha256': csha}
    assert sample['outcome'] == 'completed'
    package = {
        'schema': 'factory.lab-package/1',
        'package_id': sample['package_id'],
        'lab_task': _sample_lab_task(),
        'contract': {'id': 'muse-nvfp4-spark-v2', 'sha256': csha, 'document': doc},
        'subjects': _sample_lab_task()['subjects'],
    }
    assert report_problems(sample, package) == []


def test_lab_adapter_cli_produces_valid_m2_report(tmp_path):
    doc = json.loads(CONTRACT_PATH.read_text(encoding='utf-8'))
    csha = contract_v2.file_sha256(CONTRACT_PATH)
    lab_task = _sample_lab_task()
    _schema_validator('lab-task-1.schema.json').validate(lab_task)

    package = {
        'schema': 'factory.lab-package/1',
        'package_id': 'pkg-ifbench-test-01',
        'lab_task': lab_task,
        'contract': {'id': 'muse-nvfp4-spark-v2', 'sha256': csha, 'document': doc},
        'subjects': lab_task['subjects'],
        'origin': {'task_id': 'task-ifbench-test', 'composed_at': '2026-11-27T00:00:00Z'},
    }
    pkg_path = tmp_path / 'package.json'
    pkg_path.write_text(json.dumps(package), encoding='utf-8')
    payloads_path = tmp_path / 'payloads.json'
    payloads_path.write_text('{}', encoding='utf-8')
    out_dir = tmp_path / 'out'
    bundle_dir, rev4_dir = _make_synthetic_bundle(tmp_path)

    proc = subprocess.run(
        [
            sys.executable,
            '-m',
            'benchmarks.ifbench.lab_adapter',
            str(pkg_path),
            str(out_dir),
            str(payloads_path),
            '--bundle',
            str(bundle_dir),
            '--rev4',
            str(rev4_dir),
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.returncode == 0
    body = json.loads((out_dir / 'report.json').read_text(encoding='utf-8'))
    attached = sorted(p for p in (out_dir / 'files').iterdir() if p.is_file())
    assert attached, 'expected summary attachment under output/files/'
    full_report = {
        'schema': 'factory.lab-report/1',
        'request_id': 'labreq-2026112600000001',
        'package_id': package['package_id'],
        'lab_task_id': lab_task['lab_task_id'],
        'contract': {'id': 'muse-nvfp4-spark-v2', 'sha256': csha},
        'lab': {'name': 'spark-ifbench-cmd', 'kind': 'command', 'version': '0.4.1'},
        **body,
        'files': [
            {
                'name': p.name,
                'sha256': digest(p),
                'size': p.stat().st_size,
                'media_type': 'application/json',
            }
            for p in attached
        ],
    }
    _schema_validator('lab-report-1.schema.json').validate(full_report)
    assert report_problems(full_report, package) == []
    assert full_report['outcome'] == 'completed'


@pytest.mark.skipif(sys.platform == 'win32', reason='lab_mailbox uses POSIX os.link')
def test_command_adapter_end_to_end_with_m2_lab_agent(tmp_path):
    doc = json.loads(CONTRACT_PATH.read_text(encoding='utf-8'))
    csha = contract_v2.file_sha256(CONTRACT_PATH)
    lab_task = _sample_lab_task()
    _schema_validator('lab-task-1.schema.json').validate(lab_task)

    mailbox = Mailbox(tmp_path / 'mailbox')
    package = {
        'schema': 'factory.lab-package/1',
        'package_id': 'pkg-ifbench-test-01',
        'lab_task': lab_task,
        'contract': {'id': 'muse-nvfp4-spark-v2', 'sha256': csha, 'document': doc},
        'subjects': lab_task['subjects'],
        'origin': {'task_id': 'task-ifbench-test', 'composed_at': '2026-11-27T00:00:00Z'},
    }
    request_id = 'labreq-2026112600000001'
    mailbox.open_request(request_id, package)
    bundle_dir, rev4_dir = _make_synthetic_bundle(tmp_path)

    cmd = (
        f'"{sys.executable}" -m benchmarks.ifbench.lab_adapter '
        f'{{package}} {{output}} {{payloads}} '
        f'--bundle "{bundle_dir}" --rev4 "{rev4_dir}"'
    )
    adapter = CommandAdapter(cmd, tmp_path / 'work')
    agent = LabAgent(mailbox, 'spark-ifbench-cmd', 'command', 'spark-gb10')
    serve(agent, adapter, once=True, log=lambda _: None)
    serve(agent, adapter, once=True, log=lambda _: None)

    thread = mailbox.thread(request_id)
    assert thread['state'] == 'reported', thread
    report_msg = mailbox.latest(request_id, 'report')
    assert report_msg is not None
    report_doc = report_msg['body']
    _schema_validator('lab-report-1.schema.json').validate(report_doc)
    assert report_problems(report_doc, package) == []
    assert report_doc['outcome'] == 'completed'


def test_ifbench_core_offline_invariants(tmp_path):
    # Rate calculation and Capture failure preservation
    r = rates(128, 200, 1, 101)
    assert r['e2e_output_tok_s'] == 0.64
    assert r['decode_tok_s_client_estimate'] == 1.27

    req_path = tmp_path / 'requests.jsonl'
    cap = Capture(req_path, '/v1/chat/completions', {'stream': True})
    cap.feed(b'data: {"choices":[{"delta":{"reasoning_content":"think"}}]}\n\n')
    cap.feed(b'data: {"choices":[{"delta":{"content":"ans"},"finish_reason":"stop"}],"usage":{"completion_tokens":8}}\n\n')
    cap.feed(b'data: [DONE]\n\n')
    cap.finish(200)
    row = json.loads(req_path.read_text(encoding='utf-8'))
    assert row['ok'] is True and row['output_tokens'] == 8 and row['reasoning'] == 'think' and row['text'] == 'ans'

    # Safetensors index escape protection
    ckpt = tmp_path / 'ckpt'
    ckpt.mkdir()
    shard = ckpt / 'a.safetensors'
    shard.write_bytes(b'123')
    idx = ckpt / 'model.safetensors.index.json'
    idx.write_text(json.dumps({'weight_map': {'l0': 'a.safetensors'}}), encoding='utf-8')
    assert checkpoint_files({'checkpoint': {'path': str(ckpt)}}) == [str(shard.resolve())]

    # Bundle tamper detection
    b = tmp_path / 'tamper-bundle'
    run_dir = b / 'runs' / 'r1'
    run_dir.mkdir(parents=True)
    for name, body in [
        ('manifest.json', {'run_id': 'r1'}),
        ('report.json', {'status': 'completed', 'comparable': True}),
        ('config.toml', None),
        ('telemetry.jsonl', None),
    ]:
        (run_dir / name).write_text(json.dumps(body) if body is not None else '', encoding='utf-8')
    (b / 'handoff.json').write_text(json.dumps({'schema_version': 1, 'runs': [{'run_id': 'r1'}]}), encoding='utf-8')
    hashes = {p.relative_to(b).as_posix(): digest(p) for p in sorted(b.rglob('*')) if p.is_file()}
    (b / 'checksums.json').write_text(json.dumps(hashes), encoding='utf-8')
    assert verify(b)['ok'] is True
    (run_dir / 'report.json').write_text('{"tampered": true}', encoding='utf-8')
    assert verify(b)['ok'] is False
