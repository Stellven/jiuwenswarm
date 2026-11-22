"""Known packed storage is independently bounded; no native kernel claims."""
import importlib.util
import struct
from pathlib import Path
import pytest

PATH=Path(__file__).resolve().parents[2]/'jiuwenswarm/factory/ccs/performance_baseline/model_layout.py'
spec=importlib.util.spec_from_file_location('baseline_layout_review',PATH)
layout=importlib.util.module_from_spec(spec);spec.loader.exec_module(layout)


def fixture(path, tensors, payload):
    data=b'GGUF'+struct.pack('<IQQ',3,len(tensors),0)
    for name,shape,kind,offset in tensors:
        name=name.encode();data+=struct.pack('<Q',len(name))+name+struct.pack('<I',len(shape))
        data+=b''.join(struct.pack('<Q',n) for n in shape)+struct.pack('<IQ',kind,offset)
    data+=b'\0'*((-len(data))%32)
    path.write_bytes(data+payload)
    return path


@pytest.mark.parametrize('kind,expected',[(13,176),(16,66),(17,74),(19,50),(21,110),(29,56)])
def test_actual_quantized_block_storage(kind,expected,tmp_path):
    p=fixture(tmp_path/'weights.gguf',[('expert',[256,2],kind,0)],b'\0'*(2*expected))
    result=layout.inspect_gguf(p);tensor=result['tensors'][0]
    assert tensor['bytes']==2*expected and tensor['block_elements']==256
    assert tensor['storage_layout_known'] and not tensor['kernel_qualified']
    assert result['gaps'] and not result['full_weights_digest_verified']


def test_truncated_packed_tensor_rejected(tmp_path):
    p=fixture(tmp_path/'bad.gguf',[('expert',[256],29,0)],b'\0'*55)
    with pytest.raises(ValueError,match='beyond'):layout.inspect_gguf(p)


def test_packed_rows_cannot_cross_block_boundary(tmp_path):
    p=fixture(tmp_path/'bad.gguf',[('expert',[128,2],29,0)],b'\0'*56)
    with pytest.raises(ValueError,match='block aligned'):layout.inspect_gguf(p)


def test_overlap_rejected(tmp_path):
    p=fixture(tmp_path/'bad.gguf',[('a',[256],29,0),('b',[4],0,32)],b'\0'*64)
    with pytest.raises(ValueError,match='overlap'):layout.inspect_gguf(p)


def test_duplicate_tensor_rejected(tmp_path):
    p=fixture(tmp_path/'bad.gguf',[('a',[4],0,0),('a',[4],0,32)],b'\0'*64)
    with pytest.raises(ValueError,match='Duplicate'):layout.inspect_gguf(p)


def test_unknown_layout_does_not_invent_tensor_bytes(tmp_path):
    p=fixture(tmp_path/'future.gguf',[('future',[256],999,0)],b'\0'*64)
    t=layout.inspect_gguf(p)['tensors'][0]
    assert t['storage_extent_bytes']==64 and 'bytes' not in t and not t['storage_layout_known']


def test_q8_storage_uses_32_element_blocks(tmp_path):
    p=fixture(tmp_path/'q8.gguf',[('q8',[64,2],8,0)],b'\0'*136)
    t=layout.inspect_gguf(p)['tensors'][0]
    assert t['bytes']==136 and t['block_elements']==32
