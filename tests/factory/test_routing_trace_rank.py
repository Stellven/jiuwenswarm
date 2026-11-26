"""analysis.expert_routing_profile rank_trace, run the way a release runs it: from a copy of the capsule
directory alone (a release bundle holds only that capsule's files), on a synthetic MCT1 trace and pack."""
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CAPSULE = ROOT / 'jiuwenswarm/factory/ccs/routing_profile_analysis'
sys.path.insert(0, str(ROOT / 'jiuwenswarm/factory/ccs/weight_pack_compiler/tests'))
import wpc_gguf_fixture as fx  # noqa: E402


def trace(path, records, n_layer=fx.N_LAYER, n_used=2):
    """MCT1 as llama-moe-cache.cpp writes it: header, one group of every layer, then lookup records."""
    out = b'MCT1' + struct.pack('<III', n_layer, n_used, 1)
    out += struct.pack('<III', 0, fx.N_EXPERT, n_layer) + b''.join(struct.pack('<I', il) for il in range(n_layer))
    out += struct.pack('<ddQQQ', 1.0, 1.0, 0, 0, 32) + struct.pack('<I', 3) + struct.pack('<QQQ', 1, 1, 1)
    for il, ids in records:
        out += struct.pack('<iii', il, n_used, len(ids)) + struct.pack(f'<{len(ids)}i', *ids)
    Path(path).write_bytes(out)


def call(bundle, inputs):
    done = subprocess.run([sys.executable, str(bundle / 'run.py')], input=json.dumps(dict(capability='rank_trace', inputs=inputs)),
                          capture_output=True, text=True, cwd=bundle)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_rank_trace_runs_from_the_capsule_alone(tmp_path):
    bundle = tmp_path / 'bundle'
    shutil.copytree(CAPSULE, bundle, ignore=shutil.ignore_patterns('__pycache__'))
    pack = tmp_path / 'pack.gguf'
    rows = fx.layout(expert_type='iq2_xxs')
    fx.write_gguf(pack, [(n, s, t, d) for _, n, s, t, d in rows],
                  {'general.architecture': 'muse-spark', 'general.alignment': 32,
                   'muse-spark.block_count': fx.N_LAYER, 'muse-spark.expert_count': fx.N_EXPERT})
    records = [(il, [0, 1, 1, 2]) for il in range(fx.N_LAYER)] + [(il, [3, 1]) for il in range(fx.N_LAYER)]
    trace(tmp_path / 'trace.mct', records)
    out = tmp_path / 'profile.json'
    reply = call(bundle, dict(trace=str(tmp_path / 'trace.mct'), pack=str(pack), profile_out=str(out), prompt_set_sha256='ab' * 32))
    assert reply['outcome'] == 'ok', reply
    checks = {c['name']: c['status'] for c in reply['outputs']['checks']}
    assert all(v == 'pass' for v in checks.values()), checks
    doc = json.loads(out.read_text())
    assert doc['format'] == 'spark-expert-residency-nominations/1' and doc['n_expert'] == fx.N_EXPERT
    assert doc['layers'][0]['expert_ids'][0] == 1  # most hits first
    assert out.stat().st_mode & 0o777 == 0o400


def test_capsule_python_imports_nothing_from_sibling_capsules():
    for path in CAPSULE.glob('*.py'):
        text = path.read_text(encoding='utf-8')
        assert "parents[1] / '" not in text and 'weight_pack_compiler' not in text.replace('weights.build_weight_pack_compiler', ''), path.name
