"""Offline Spark builder admission: no compiler, model, Docker or network."""
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory import ab, components, contract, taskgraph
from jiuwenswarm.factory.builder import Builder
from jiuwenswarm.factory.controller import Controller  # registers additive task input columns
from jiuwenswarm.factory.manager import Manager

CCS = Path(__file__).resolve().parents[2] / 'jiuwenswarm/factory/ccs'
NAMES = ['observability_event_recorder', 'weight_placement_planner', 'expert_weight_cache',
         'expert_demand_predictor', 'batch_layout_mapper']


@pytest.mark.parametrize('name', NAMES)
def test_builder_specs_use_capsule_ontology_and_have_no_product_patch(name, tmp_path):
    declaration = yaml.safe_load((CCS / name / 'cc.yaml').read_text())
    material = components.load(declaration['id'])
    assert material['kind'] == 'builder_spec'
    assert not {'patch', 'sha256'} & material['change'].keys()
    assert declaration['version'] == '1.1.2'
    ontology = yaml.safe_load((CCS / name / 'ONTOLOGY.yaml').read_text())
    assert set(material.get('quantities', [])) <= ontology['quantities'].keys()
    host = Host(tmp_path / 'ccstore')
    release = host.seal(CCS / name)
    assert components.load(declaration['id'], host=host, release=release) == material
    with pytest.raises(ValueError, match='different|ambiguous'):
        components.load('expert_fill', host=host, release=release)


def test_selected_binding_does_not_fall_back_to_unselected_builder(tmp_path):
    host = Host(tmp_path / 'ccstore')
    release = host.seal(CCS / 'observability_event_recorder')
    token = components.SELECTED_BINDING.set((host, {'components': [
        {'release': release, 'material': 'runtime_event_recorder'}]}))
    try:
        assert components.load('observability.build_runtime_event_recorder')['kind'] == 'builder_spec'
        with pytest.raises(ValueError, match='not selected'):
            components.load('engine.build_expert_weight_cache')
    finally:
        components.SELECTED_BINDING.reset(token)


def test_builder_spec_cannot_be_used_as_patch_bearing_ab(store, monkeypatch):
    monkeypatch.setattr(contract, 'load_for_task', lambda *args: {'reference': {'stdout_sha256': 'a' * 64}})
    with pytest.raises(ValueError, match='patch-bearing component'):
        ab.submit(Manager(store, store.home / 'spool'), 't', {}, {}, {}, {}, 1, 'spec',
                  'observability.build_runtime_event_recorder')


def test_external_capped_contract_cannot_launch_factory_lab(store, monkeypatch):
    monkeypatch.setattr(contract, 'load_for_task', lambda *args: dict(external_execution_only=True))
    manager = Manager(store, store.home / 'spool')
    monkeypatch.setattr(manager, '_admission', lambda *args: {})
    with pytest.raises(ValueError, match='external bin/capped'):
        manager.submit_run('t', 'admission', 'star-deepseek-v1', {}, 'run')
    with pytest.raises(ValueError, match='external bin/capped'):
        ab.submit(manager, 't', {}, {}, {}, {}, 1, 'run', 'unused')


def test_spark_native_delivery_rejects_other_targets_and_builds(store):
    builder = Builder(store)
    for request in ({'target': 'jetson-orin', 'delivery': 'native', 'build_target': 'llama-server'},
                    {'target': 'spark-gb10', 'delivery': 'native', 'build_target': 'strata-dsv41'}):
        with pytest.raises(ValueError, match='Native delivery requires'):
            builder._request(request)


def test_star_task_initial_graph_replays_with_capsule_slice(store):
    for name in NAMES:
        folder = CCS.parent / 'tasks'
        value = json.loads((folder / ('star-spark-' + name + '.json')).read_text())
        assert value['target'] == 'spark-gb10'
        assert 'gpu.use' not in value['allowed_effects']
        assert value['constraints']['build_request']['delivery'] == 'native'
        task = store.create_task(value)
        graph = taskgraph.seed_plan(store, task)
        assert all(n['capability'] is None for n in graph['nodes'] if n['kind'] == 'measure')
        assert graph == taskgraph.from_records(store.dump(task['task_id']))


def test_star_transport_identity_matches_retained_migration(tmp_path):
    migration = json.loads((CCS / 'star-transport-migration.json').read_text())
    host = Host(tmp_path / 'ccstore')
    for row in migration['releases']:
        assert host.seal((CCS / row['path']).parent) == row['new_release']


@pytest.mark.parametrize('invalid', [None, 'outside', 'digest'])
def test_native_worker_retains_executable_receipt_and_rejects_drift(store, monkeypatch, tmp_path, invalid):
    import subprocess
    from jiuwenswarm.factory import build_job

    worker_root = Path(build_job.__file__).parent
    request = dict(target='spark-gb10', delivery='native', build_target='llama-server',
                   source={'path': str(tmp_path / 'source'), 'commit': 'a' * 40},
                   dependency={'path': str(tmp_path / 'dependency'), 'commit': 'b' * 40},
                   tag='factory/llamacpp:fixture', native_cmake_cache=str(tmp_path / 'CMakeCache.txt'), native_cmake_cache_sha256='c' * 64,
                   engine_sha256=hashlib.sha256((worker_root / 'spark_engine.py').read_bytes()).hexdigest(),
                   recipe_sha256=hashlib.sha256((worker_root.parents[1] / 'deploy/spark/Runtime.Dockerfile').read_bytes()).hexdigest(),
                   worker_sha256=hashlib.sha256(Path(build_job.__file__).read_bytes()).hexdigest(),
                   lifecycle_sha256=hashlib.sha256((worker_root / 'lab_lifecycle.py').read_bytes()).hexdigest())
    attempt = store.create_attempt('t', dict(kind='build', request=request, idem_key='native', fingerprint='native'))
    monkeypatch.setattr('jiuwenswarm.factory.execution_binding.verify_task', lambda *args: None)
    def fake_compile(argv, **kwargs):
        assert argv[argv.index('--delivery') + 1] == 'native'
        out = Path(argv[argv.index('--out') + 1]); out.mkdir(parents=True)
        executable = (tmp_path if invalid == 'outside' else out) / 'llama-server'
        executable.write_bytes(b'executable-fixture')
        digest = hashlib.sha256(executable.read_bytes()).hexdigest()
        record = dict(status='success', delivery='native', executable=dict(path=str(executable),
                      sha256='0' * 64 if invalid == 'digest' else digest, size=executable.stat().st_size))
        (out / 'build-record.json').write_text(json.dumps(record))
        return subprocess.CompletedProcess(argv, 0)
    monkeypatch.setattr(build_job.subprocess, 'run', fake_compile)
    result = build_job.run(store, 't', attempt['attempt_id'], request)
    receipt = json.loads(store.artifact_bytes('t', attempt['attempt_id'] + ':receipt'))
    assert receipt['delivery'] == 'native' and receipt['image_id'] is None
    observation = store.read('t', attempt['attempt_id'] + ':build-result')
    if invalid:
        assert result == 1 and observation['error']['code'] == 'NATIVE_BUILD_RECORD_INVALID'
    else:
        assert result == 0 and observation['values']['status'] == 'success'
        assert receipt['executable']['sha256'] == observation['values']['executable']['sha256']


def test_native_recipe_retains_stock_cpu_gpu_and_generator(tmp_path):
    from jiuwenswarm.factory.spark_engine import native_recipe
    cache = tmp_path / 'CMakeCache.txt'
    cache.write_text('CMAKE_GENERATOR:INTERNAL=Unix Makefiles\nCMAKE_BUILD_TYPE:STRING=Release\nCMAKE_CUDA_ARCHITECTURES:STRING=121\nGGML_CUDA:BOOL=ON\nGGML_NATIVE:BOOL=ON\nGGML_OPENMP:BOOL=ON\nGGML_CPU_ARM_ARCH:STRING=\nGGML_CUDA_FA_ALL_QUANTS:BOOL=OFF\nCMAKE_HOME_DIRECTORY:INTERNAL=/reference/source\n')
    generator, flags = native_recipe(cache)
    assert generator == 'Unix Makefiles'
    assert set(['-DGGML_NATIVE=ON', '-DGGML_OPENMP=ON', '-DGGML_CPU_ARM_ARCH=', '-DGGML_CUDA_FA_ALL_QUANTS=OFF']) <= set(flags)
    assert not any('CMAKE_HOME_DIRECTORY' in flag for flag in flags)
