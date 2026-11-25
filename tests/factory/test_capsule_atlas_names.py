"""The atlas naming table covers every capsule and follows the atlas naming rules."""
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jiuwenswarm.gateway.channel_manager.web.capsule_catalog import ATLAS_NAMES, CCS
from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService, attach_factory_routes

NAMES = json.loads((CCS / ATLAS_NAMES).read_text(encoding='utf-8'))
ENTRIES = NAMES['capsules']
KINDS = {'builder', 'tool', 'analysis', 'factory'}
# Handoff table "Atlas CC IDs and capsule directories" of the 20261120 atlas edition.
ATLAS_MAP = {
    'expert_weight_cache': ('engine.build_expert_weight_cache', 'Expert weight cache builder', 'builder'),
    'weight_placement_planner': ('placement.build_weight_placement_planner', 'Weight placement planner builder', 'builder'),
    'expert_demand_predictor': ('routing.build_expert_demand_predictor', 'Expert demand predictor builder', 'builder'),
    'batch_layout_mapper': ('batch.build_batch_layout_builder', 'Batch layout mapper builder', 'builder'),
    'observability_event_recorder': ('observability.build_runtime_event_recorder', 'Runtime event recorder builder', 'builder'),
    'builder': ('factory.image_builder', 'Image assembler', 'factory'),
    'lab_client': ('tool.capped_lab_runner', 'Capped lab runner', 'tool'),
    'cache_size_pareto': ('tool.moe_cache_size_tuner', 'MoE cache size tuner', 'tool'),
    'routing_profile_analysis': ('analysis.expert_routing_profile', 'Expert routing profile analysis', 'analysis'),
    'request_fault_io_analysis': ('analysis.request_fault_io', 'Request fault and I/O analysis', 'analysis'),
    'quant_kernel_profile': ('analysis.quant_kernel_profile', 'Quantized kernel profile analysis', 'analysis'),
    'spark_gap_analysis': ('analysis.engine_gap', 'Engine gap analysis', 'analysis'),
    'weight_pack_compiler': ('weights.pack_compiler.builder', 'Pack compiler', 'tool'),
    'muse_nvfp4_reader': ('weights.checkpoint_reader.builder', 'Muse NVFP4 reader builder', 'builder'),
    'expert_scale_wiring': ('weights.format_toolkit.builder', 'Expert scale wiring builder', 'builder'),
    'prefill_batch_sizing': (None, 'Prefill batch sizing', 'tool'),
    'expert_fill': (None, 'Expert fill builder', 'builder'),
}


def capsule_directories():
    return {path.parent.relative_to(CCS).as_posix() for path in CCS.rglob('cc.yaml')
            if not any(part.startswith('.') for part in path.relative_to(CCS).parts)}


def test_every_capsule_directory_has_exactly_one_atlas_name():
    directories = capsule_directories()
    assert len(directories) >= 60
    assert sorted(directories - set(ENTRIES)) == [], 'capsules without an atlas name'
    assert sorted(set(ENTRIES) - directories) == [], 'atlas names for missing capsules'


def test_names_follow_the_atlas_rules():
    assert set(NAMES['kinds']) == KINDS
    titles = [entry['title'] for entry in ENTRIES.values()]
    assert len(titles) == len(set(titles)), 'titles must be unique'
    for directory, entry in ENTRIES.items():
        title, kind = entry['title'], entry['kind']
        assert kind in KINDS, directory
        assert title and title[0].isupper() and not title.endswith(' CC'), directory
        if kind == 'builder':
            # "<Component> builder": name the component, never the action.
            assert title.endswith(' builder'), directory
            assert entry['component'] and entry['target'], directory
            assert entry['component'].lower() in title.lower(), directory
        else:
            assert not title.lower().endswith('builder'), f'{directory}: "builder" is reserved for builder CCs'
        if kind == 'analysis':
            assert title.endswith(' analysis'), directory
        assert entry['summary'], directory


def test_atlas_capsule_map_is_used_verbatim():
    for directory, (atlas_id, title, kind) in ATLAS_MAP.items():
        entry = ENTRIES[directory]
        assert (entry['atlas_cc_id'], entry['title'], entry['kind']) == (atlas_id, title, kind)
    assert 'Image builder' in ENTRIES['builder']['former_names']
    mapped = {name for name, entry in ENTRIES.items() if entry['atlas_cc_id']}
    assert mapped == set(ATLAS_MAP)


def test_catalog_and_detail_expose_atlas_names_and_kind_legend():
    app = FastAPI()
    attach_factory_routes(app, service=FactoryHttpService(roots=[]))
    api = TestClient(app)
    catalog = api.get('/api/factory/capsules', params={'usage': False}).json()
    assert set(catalog['kinds']) == KINDS
    rows = {row['name']: row for row in catalog['capsules']}
    cache = rows['expert_weight_cache']
    assert cache['cc_title'] == 'Expert weight cache builder' and cache['cc_kind'] == 'builder'
    assert cache['cc_component'] == 'Expert weight cache' and cache['cc_target'] == 'llama.cpp'
    assert rows['lab_client']['cc_kind'] == 'tool'
    assert rows['expert_fill']['cc_title'] == 'Expert fill builder'
    assert all(row['cc_title'] and row['cc_kind'] in KINDS for row in catalog['capsules'])
    detail = api.get('/api/factory/capsules/factory.builder').json()
    assert detail['name'] == 'builder' and detail['cc_title'] == 'Image assembler'
    assert detail['atlas_cc_id'] == 'factory.image_builder' and detail['cc_kind'] == 'factory'
