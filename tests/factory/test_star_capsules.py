"""Offline Spark builder admission: no compiler, model, Docker or network."""
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory import ab, components, contract, taskgraph
from jiuwenswarm.factory.builder import Builder
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
