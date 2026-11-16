"""Extract source-bound CUDA declarations. Regex inventory is not a compiler AST."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

# Handle common __launch_bounds__ decorators, multiline arguments and templates.
KERNEL = re.compile(r'__global__\s+(?:__launch_bounds__\s*\([^\n]*?\)\s*)?(?:static\s+|inline\s+)*void\s+([A-Za-z_]\w*)\s*\((.*?)\)\s*\{', re.S)

def analyze(repository: Path) -> dict:
    root = repository.resolve(strict=True)
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, check=True, text=True, capture_output=True).stdout.strip()
    files, ops = [], []
    for path in sorted(root.rglob('*')):
        if path.suffix not in {'.cu', '.cpp', '.cuh', '.hpp'} or '.git' in path.parts or not path.is_file():
            continue
        raw = path.read_bytes()
        text = raw.decode('utf-8', errors='replace')
        matches = list(KERNEL.finditer(text))
        if not matches:
            continue
        relative, digest = str(path.relative_to(root)), hashlib.sha256(raw).hexdigest()
        files.append({'path': relative, 'sha256': digest, 'bytes': len(raw)})
        for match in matches:
            ops.append({'id': f'{relative}:{match.start()}', 'name': match.group(1), 'file': relative,
                        'line': text.count('\n', 0, match.start()) + 1, 'arguments': ' '.join(match.group(2).split()), 'source_sha256': digest})
    if not ops:
        raise ValueError('No CUDA kernel declarations were found in the actual checkout')
    return {'schema': 'strata.cuda.inventory.v1', 'extraction_method': 'source_regex', 'commit_sha': commit,
            'source_dir': str(root), 'files': files, 'cuda_ops': ops,
            'semantic_lowering_complete': False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.repository)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'file': str(args.output), 'commit_sha': result['commit_sha'], 'cuda_kernels': len(result['cuda_ops']), 'source_files': len(result['files'])}), flush=True)
