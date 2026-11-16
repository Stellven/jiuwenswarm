"""Bind inventory descriptors to extracted, executable STRATA core semantics.

Descriptor classification remains distinct from semantic lowering. Only the
source functions inspected by core_codegen enter the source-construction IR.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

# This adapter is also invoked directly as a subprocess from a stage workspace.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from jiuwenswarm.software_factory.core_codegen import extract_core


def convert(path: Path, core_output: Path | None = None, selected=None) -> dict:
    raw = path.read_bytes()
    source = json.loads(raw)
    if not isinstance(source, dict) or not isinstance(source.get('cuda_ops'), list) or not source['cuda_ops']:
        raise ValueError('Input must contain a nonempty cuda_ops inventory')
    output = []
    for kernel in source['cuda_ops']:
        if not isinstance(kernel, dict) or not all(isinstance(kernel.get(k), str) and kernel[k] for k in ('id', 'name', 'file', 'source_sha256')):
            raise ValueError('CUDA inventory entries require exact source identities')
        name = kernel['name'].lower()
        # These are candidate operation families, NOT validated operator implementations.
        family = ('matmul' if any(key in name for key in ('gemm', 'gemv', 'matmul')) else
                  'swiglu' if 'swiglu' in name else 'normalization' if any(key in name for key in ('rms', 'norm')) else
                  'softmax' if 'softmax' in name else 'unclassified')
        candidates = {'matmul': ['aclnnMatmul'], 'swiglu': ['aclnnSilu', 'aclnnMul'],
                      'normalization': ['aclnnRmsNorm'], 'softmax': ['aclnnSoftmax'], 'unclassified': []}[family]
        output.append({'source_id': kernel['id'], 'source_name': kernel['name'], 'file': kernel['file'],
                       'line': kernel.get('line'), 'source_sha256': kernel['source_sha256'],
                       'operation_family': family, 'candidate_ascend_ops': candidates,
                       'implementation_status': 'requires_semantic_implementation', 'numerical_validation': 'not_run'})
    core = extract_core(Path(source['source_dir']), core_output or path.parent/'core_extraction', selected)
    if core['commit_sha'] != source['commit_sha']:
        raise ValueError('Core extraction and CUDA scan refer to different source revisions')
    return {'schema': 'strata.ascend.inventory.v2', 'commit_sha': source['commit_sha'],
            'source_dir': source['source_dir'], 'files': source['files'], 'ascend_ops': output,
            'input_sha256': hashlib.sha256(raw).hexdigest(), 'core_ir': core,
            'semantic_lowering_complete': False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--core', action='append', choices=['router', 'swiglu', 'moe_combine'])
    args = parser.parse_args()
    result = convert(args.input, args.output.parent/'core_extraction', args.core)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'input': str(args.input), 'output': str(args.output), 'mapped_descriptors': len(result['ascend_ops']),
                      'extracted_core': result['core_ir']['selected'], 'semantic_lowering_complete': False}), flush=True)
