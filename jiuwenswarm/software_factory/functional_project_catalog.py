"""Source-backed project modules and the boundaries for reassembling a checkout."""
from __future__ import annotations

import argparse
import ast
from inspect import getsource
from pathlib import Path, PurePosixPath
import re
import subprocess

from .cuda_lowering import balanced
from .workflow_library import write_json


STRATA_DIRECTORIES = {
    'artifact': 'model-formats',
    'core': 'inference-core',
    'dsv41': 'deepseek-engine',
    'hip_compat': 'hip-support',
    'kernels': 'compute-kernels',
    'ngram': 'ngram-draft',
    'plan': 'hardware-placement',
    'platform': 'platform-support',
    'prefill': 'prompt-processing',
    'program': 'engine-programs',
    'qwen35': 'qwen-engine',
    'spec': 'speculative-decoding',
    'split': 'multi-device-engine',
}

GOOGLE_SUPPORT = {
    'cmake': 'build', 'samples': 'examples', 'docs': 'documentation', 'test': 'framework-tests',
}

DECOMPOSITION_EXAMPLES = {
    'strata': ('routing', (
        ('src/core/layer.cpp', 'w_router->data, b.logits, g.n_embd, g.n_expert, true, stream)', 0),
        ('src/core/layer.cpp', '} else router_top10(b.logits, 1,', 0),
        ('src/kernels/cuda/router_top10.cu', 'at least one full warp, for the reductions', 7),
        ('src/core/layer.cpp', 'doorbell_publish(x, b.ids, b.weights', 1),
    )),
    'googletest': ('match_names', (
        ('googletest/src/gtest.cc', 'const bool matches_filter =', 2),
        ('googletest/src/gtest.cc', 'ShouldRunTestOnShard(total_shards, shard_index, num_runnable_tests)', 0),
    )),
}


def package_for_path(project, relative):
    parts = PurePosixPath(relative).parts
    first = parts[0]
    if project == 'strata':
        unit = parts[1:] if first == 'src' else parts[2:] if parts[:2] == ('include', 'strata') else ()
        if unit and unit[0] in STRATA_DIRECTORIES:
            if unit[:2] in {('kernels', 'cpu'), ('kernels', 'cuda')}:
                return unit[1] + '-kernels'
            return STRATA_DIRECTORIES[unit[0]]
        if first in {'cmake', 'packaging', 'docker'} or first == 'CMakeLists.txt':
            return 'build-and-packaging'
    if project == 'googletest' and first in {'googletest', 'googlemock'}:
        framework = 'gtest' if first == 'googletest' else 'gmock'
        if parts[1] in GOOGLE_SUPPORT:
            return framework + '-' + GOOGLE_SUPPORT[parts[1]]
        stem = PurePosixPath(relative).stem.replace('_', '-')
        if len(parts) > 2 and re.fullmatch(r'g(?:test|mock)(?:-[a-z0-9-]+)?', stem):
            return stem + '-core' if stem in {'gtest', 'gmock'} else stem
        return framework + '-support'
    if first in {'.github', 'ci'}:
        return 'automation'
    return first.replace('_', '-') if len(parts) > 1 else 'project-root'


def _python_end(text, start):
    line = text.count('\n', 0, start) + 1
    definition = next((node for node in ast.walk(ast.parse(text)) if
                       isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                       and node.lineno == line), None)
    if definition is None:
        raise ValueError('Python source anchor does not refer to a callable or class')
    return definition.end_lineno


def _extract_cpp_definition(source, anchor, signature, first_line):
    opening = source.index('{', signature.end() - int(anchor.endswith('{')))
    closing = balanced(source, opening)
    last_line = source.count('\n', 0, closing) + 1
    return '\n'.join(source.splitlines()[first_line - 1:last_line]), last_line


def source_component(checkout, part, project):
    path = part['path']
    source = (checkout / path).read_text(encoding='utf-8-sig')
    anchor = part['anchor']
    hits = list(re.finditer(r'(?m)^[ \t]*' + re.escape(anchor.lstrip()), source))
    if not hits:
        # A definition may have an export macro before the anchored signature.
        hits = list(re.finditer(re.escape(anchor.lstrip()), source))
    if len(hits) != 1:
        raise ValueError(f'Expected one definition for {part["symbol"]} in {path}, got {len(hits)}')
    start = source.rfind('\n', 0, hits[0].start()) + 1
    line = source.count('\n', 0, start) + 1
    if path.endswith('.py'):
        last_line = _python_end(source, start)
        code = '\n'.join(source.splitlines()[line - 1:last_line])
    else:
        # Definition anchors include enough of the signature to distinguish overloads.
        code, last_line = _extract_cpp_definition(source, anchor, hits[0], line)
    return {**{k: v for k, v in part.items() if k != 'anchor'}, 'line': line,
            'end_line': last_line, 'code': code,
            'source_package': package_for_path(project, path)}


def decomposition_example(project, checkout, groups, definitions, registered_parts):
    part_id, sites = DECOMPOSITION_EXAMPLES[project]
    group, part = next((group, part) for group in groups for part in group['parts'] if part['id'] == part_id)
    excerpts = []
    for path, needle, after in sites:
        lines = (checkout / path).read_text(encoding='utf-8-sig').splitlines()
        locations = [index for index, line in enumerate(lines) if needle in line]
        if len(locations) != 1:
            raise ValueError(f'Expected one call site for {project}/{part_id} in {path}')
        index = locations[0]
        excerpts.append({'path': path, 'line': index + 1, 'code': '\n'.join(lines[index:index + after + 1])})
    entry = next((candidate for candidate in registered_parts if candidate['id'] == part.get('recorded_part')), None)
    definition = next(item for group in definitions for item in group['parts'] if item['id'] == part_id)
    return {'group': group['name'], 'part': part_id, 'calls': excerpts,
            'anchor': definition['anchor'], 'python': getsource(_extract_cpp_definition).rstrip(),
            'registered': {key: entry[key] for key in ('id', 'name', 'inputs', 'outputs')} if entry else None}


def catalog_project(project, checkout, revision, groups, recorded_parts=()):
    checkout = Path(checkout)
    actual = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
    changes = subprocess.check_output(['git', '-C', str(checkout), 'status', '--porcelain'], text=True)
    if actual != revision or changes:
        raise ValueError(f'{project} checkout differs from its pinned import')
    recorded = {part['upstream_function']['name']: part['id'] for part in recorded_parts
                if part.get('upstream_function')}
    recorded_paths = {part['id']: part['upstream_function']['path'] for part in recorded_parts
                      if part.get('upstream_function')}
    catalog = []
    for group in groups:
        parts = []
        for description in group['parts']:
            item = source_component(checkout, description, project)
            link = recorded.get(item['symbol'])
            if link is None and recorded_paths.get(item['id']) == item['path']:
                link = item['id']
            if link is not None:
                item['recorded_part'] = link
            parts.append(item)
        catalog.append({**group, 'parts': parts})
    tree = subprocess.check_output(['git', '-C', str(checkout), 'ls-files', '-z']).decode().rstrip('\0').split('\0')
    packages = {}
    for path in tree:
        packages.setdefault(package_for_path(project, path), []).append(path)
    return {'id': project, 'revision': actual, 'groups': catalog,
            'decomposition': decomposition_example(project, checkout, catalog, groups, recorded_parts),
            'source_packages': dict(sorted(packages.items()))}


def build_catalog(library, destination):
    from .googletest_runtime_components import GROUPS as google_groups
    from .strata_runtime_components import STRATA_RUNTIME_GROUPS as strata_groups

    groups = {'strata': strata_groups, 'googletest': google_groups}
    projects = []
    for workflow in library.list():
        project = workflow['id']
        if project not in groups:
            continue
        source = workflow['source']
        catalog = catalog_project(project, source['checkout'], source['revision'],
                                  groups[project], workflow['subworkflows'])
        projects.append({**catalog, 'name': workflow['name'], 'repository': source['repository']})
    write_json(Path(destination), projects)
    return projects


if __name__ == '__main__':
    from .workflow_library import WorkflowLibrary

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build_catalog(WorkflowLibrary(args.library), args.output)
