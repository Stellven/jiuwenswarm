"""External checkouts, packs, models and run directories switch through config.py variables."""
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.factory import benchmark_data as bd
from jiuwenswarm.factory import spark_engine
from jiuwenswarm.factory.config import SOURCE_DEFAULTS, expand_sources, source

ROOT = Path(__file__).resolve().parents[2] / 'jiuwenswarm/factory'
TASKS = [*ROOT.glob('tasks/*.json'), *ROOT.glob('ccs/*/tasks/*.json')]
HELPERS = ['batch_layout_mapper/helpers/parity.py', 'expert_demand_predictor/helpers/parity_template.py',
           'observability_event_recorder/helpers/parity.py', 'weight_placement_planner/helpers/parity.py']


def test_task_files_name_no_personal_host_paths():
    assert TASKS
    for path in TASKS:
        text = path.read_text(encoding='utf-8')
        assert '/home/' not in text and '/Users/' not in text, path


def test_every_task_reference_resolves_to_a_defined_source():
    for path in TASKS:
        resolved = json.dumps(expand_sources(json.loads(path.read_text(encoding='utf-8'))))
        assert '${FACTORY_' not in resolved, path


def test_expansion_prefers_environment_then_defaults(monkeypatch):
    for key in SOURCE_DEFAULTS:
        monkeypatch.delenv(key, raising=False)
    task = {'a': ['${FACTORY_LLAMA_SOURCE}', 7], 'b': {'m': '${FACTORY_MODELS}/q/x.gguf'}, 'c': '$HOME ${OTHER}'}
    value = expand_sources(task)
    assert value['a'] == [str(Path(SOURCE_DEFAULTS['FACTORY_LLAMA_SOURCE']).expanduser()), 7]
    assert value['b']['m'] == str(Path('~/models').expanduser()) + '/q/x.gguf'
    assert value['c'] == '$HOME ${OTHER}'
    monkeypatch.setenv('FACTORY_MODELS', '/srv/models')
    assert expand_sources('${FACTORY_MODELS}/x.gguf') == '/srv/models/x.gguf'
    with pytest.raises(ValueError, match='FACTORY_NOT_A_SOURCE'):
        expand_sources('${FACTORY_NOT_A_SOURCE}/x')
    with pytest.raises(ValueError, match='FACTORY_OVERLAP_WATCH_RUN'):
        source('FACTORY_OVERLAP_WATCH_RUN')


def test_init_task_stores_resolved_paths(tmp_path, monkeypatch):
    from jiuwenswarm.factory.controller import Controller
    monkeypatch.setenv('FACTORY_LLAMA_SOURCE', str(tmp_path / 'stock'))
    monkeypatch.setenv('FACTORY_LLAMA_CMAKE_CACHE', str(tmp_path / 'CMakeCache.txt'))
    template = json.loads((ROOT / 'tasks/star-spark-expert_weight_cache.json').read_text(encoding='utf-8'))
    template['constraints'].pop('local_commits')  # no owned checkout in this fixture
    task_file = tmp_path / 'task.json'
    task_file.write_text(json.dumps(template), encoding='utf-8')
    controller = Controller(home=tmp_path / 'home')
    try:
        stored = controller.store.get_task(controller.init_task(task_file))
    finally:
        controller.store.close()
    build = stored['constraints']['build_request']
    assert build['dependency']['path'] == str(tmp_path / 'stock')
    assert build['native_cmake_cache'] == str(tmp_path / 'CMakeCache.txt')
    assert stored['resources']['source']['copy_from'] == str(tmp_path / 'stock')


def write_tables(directory):
    directory.mkdir(parents=True)
    for name, value in [('vocab.json', {'A': 0}), ('token_type.json', [1]), ('tokenizer.json', {'special_ids': {}})]:
        (directory / name).write_text(json.dumps(value))
    return {str(p): bd.digest(p.read_bytes()) for p in directory.iterdir()}


def test_decoder_reads_a_moved_pack_and_still_checks_digests(tmp_path, monkeypatch):
    monkeypatch.delenv('FACTORY_STRATA_PACK', raising=False)
    files = write_tables(tmp_path / 'recorded/tokenizer')
    files[str(tmp_path / 'recorded-source/strata_tokenizer.py')] = '0' * 64  # recorded, absent here
    moved = tmp_path / 'moved'
    (tmp_path / 'recorded').rename(moved)
    with pytest.raises(OSError):
        bd.load_decoder(tmp_path, files)
    assert bd.load_decoder(tmp_path, files, pack=moved).decode([0]) == 'A'
    monkeypatch.setenv('FACTORY_STRATA_PACK', str(moved))
    monkeypatch.setattr(bd, 'PACK', moved)
    assert bd.load_decoder(tmp_path, files).decode([0]) == 'A'
    (moved / 'tokenizer/vocab.json').write_text('{"B": 0}')
    with pytest.raises(ValueError, match='changed'):
        bd.load_decoder(tmp_path, files)


def test_strata_source_tree_is_configurable(tmp_path, monkeypatch):
    monkeypatch.delenv('FACTORY_STRATA_SOURCE', raising=False)
    assert bd.strata_source(tmp_path) == tmp_path / 'sources/strata-deepseek'
    monkeypatch.setenv('FACTORY_STRATA_SOURCE', str(tmp_path / 'strata'))
    assert bd.strata_source(tmp_path) == tmp_path / 'strata'


@pytest.fixture
def overlap_host(monkeypatch):
    original = Path.read_text

    def read_text(self, *args, **kwargs):
        if str(self) == '/proc/self/cgroup':
            return '0::/system.slice/spark-owner-c2-cpu.service\n'
        if self.name == 'memory.max' and 'spark-owner-c2-cpu.service' in str(self):
            return str(4 * 1024**3)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read_text)
    monkeypatch.setattr(spark_engine.os, 'sched_getaffinity', lambda pid: set(range(12, 20)), raising=False)
    monkeypatch.setattr(spark_engine.os, 'getpriority', lambda *a: 19, raising=False)
    monkeypatch.setattr(spark_engine.subprocess, 'check_output', lambda *a, **k: 'idle')
    monkeypatch.setenv('SPARK_OWNER_BUILD', 'placement-tier')
    monkeypatch.delenv('FACTORY_OVERLAP_WATCH_RUN', raising=False)
    return SimpleNamespace(delivery='native', build_target='llama-server', tag='factory/llamacpp:star-placement-tier-x')


def test_owner_overlap_watch_run_comes_from_the_environment(tmp_path, monkeypatch, overlap_host):
    headroom = 64 * 1024**2
    assert spark_engine.owner_native_overlap(overlap_host, '', headroom)['observed_scope'] is None
    with pytest.raises(ValueError, match='FACTORY_OVERLAP_WATCH_RUN'):
        spark_engine.owner_native_overlap(overlap_host, '4242, 100 MiB', headroom)
    (tmp_path / 'start.json').write_text(json.dumps({'arm': 'A+', 'cpus': '0-7'}))
    (tmp_path / 'scope.json').write_text(json.dumps({'pid': 4242}))
    monkeypatch.setenv('FACTORY_OVERLAP_WATCH_RUN', str(tmp_path))
    result = spark_engine.owner_native_overlap(overlap_host, '4242, 100 MiB', headroom)
    assert result['observed_scope'] == str(tmp_path)
    with pytest.raises(ValueError, match=r'capped A\+60'):
        spark_engine.owner_native_overlap(overlap_host, '7, 100 MiB', headroom)


def test_parity_helpers_take_the_wrapper_from_factory_one_shot(tmp_path):
    for relative in HELPERS:
        text = (ROOT / 'ccs' / relative).read_text(encoding='utf-8')
        assert 'FACTORY_ONE_SHOT' in text and 'Path.home()' not in text, relative
    helper = ROOT / 'ccs/expert_demand_predictor/helpers/parity_template.py'
    env = {'FACTORY_ONE_SHOT': str(tmp_path / 'wrapper.sh'), 'PATH': '/usr/bin:/bin'}
    out = subprocess.run([sys.executable, str(helper), 'plan', 's', 'c', 'm', 'o'], env=env,
                         capture_output=True, text=True, check=True).stdout
    assert out.count(str(tmp_path / 'wrapper.sh')) == 3
    out = subprocess.run([sys.executable, str(helper), 'plan', '--harness', '/x/run.sh', 's', 'c', 'm', 'o'],
                         env=env, capture_output=True, text=True, check=True).stdout
    assert out.count('/x/run.sh') == 3
