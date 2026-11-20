from collections import defaultdict
import importlib.util
import os
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / 'ops/spark/source_residency.py'
SPEC = importlib.util.spec_from_file_location('source_residency', SOURCE)
RESIDENCY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RESIDENCY)


def test_mincore_preserves_sparse_page_state_and_identifies_alias(tmp_path):
    page = RESIDENCY.PAGE
    weight = tmp_path / 'weight.gguf'
    with weight.open('wb') as stream:
        stream.truncate(16 * page)
        os.pwrite(stream.fileno(), b'X', 3 * page)
    alias = tmp_path / 'alias.gguf'
    alias.symlink_to(weight.name)
    groups = defaultdict(list, expert=[(page, 12 * page)])
    geometry = RESIDENCY.file_geometry(weight, groups)
    linked = RESIDENCY.file_geometry(alias, groups)
    assert geometry['identity'] == linked['identity']
    measure = RESIDENCY.Mincore()
    before = measure.inspect(geometry, 1, 42)['expert']
    assert before['sampled_pages'] == 11
    assert 1 <= before['resident_sampled_pages'] < 11
    assert measure.inspect(linked, 1, 42)['expert'] == before
    weight.unlink()
    weight.touch()
    with pytest.raises(ValueError, match='Source inode changed'):
        measure.inspect(geometry, 1, 42)


def test_strata_index_groups_experts_dense_and_engram_without_payload_reads(tmp_path):
    page = RESIDENCY.PAGE
    (tmp_path / 'ds4.txt').write_text(f'model_dir {tmp_path}\nformat gguf\n')
    (tmp_path / 'tensors.txt').write_text(
        'file 0 model.gguf\nfile 1 dspark-model.gguf\n'
        f't layers.1.ffn.experts.2.w3.weight IQ1_M 0 96 {page} 1 1\n'
        f't layers.1.engram.embed.weight IQ4_NL 0 {page + 96} {page} 1 1\n'
        f't head.weight Q8_0 0 {2 * page + 96} {page} 1 1\n'
        't mtp.0.foo Q8_0 1 100 256 1 1\n')
    with (tmp_path / 'model.gguf').open('wb') as stream:
        stream.truncate(4 * page)
    (tmp_path / 'engram.bin').write_bytes(b'x')
    geometry = RESIDENCY.strata_geometry(tmp_path)
    assert geometry['files_without_active_tensors'] == [str(tmp_path / 'dspark-model.gguf')]
    assert geometry['files'][0]['regions'] == {
        'expert': [[96, page + 96]], 'engram': [[page + 96, 2 * page + 96]],
        'dense': [[2 * page + 96, 3 * page + 96]],
    }
    assert geometry['files'][1]['regions']['engram'] == [[0, 1]]
