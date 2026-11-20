"""Extract source-backed Python callable candidates from a pinned Git tree."""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from importlib.util import resolve_name
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tokenize
from urllib.parse import urlsplit, urlunsplit

from .workflow_library import write_json


_FUNCTION = (ast.FunctionDef, ast.AsyncFunctionDef)
_NESTED_SCOPE = (*_FUNCTION, ast.ClassDef, ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _git(checkout, *arguments):
    return subprocess.check_output(['git', '-C', str(checkout), *arguments], timeout=30)


def _read_modules(checkout, revision, package):
    modules = {}
    entries = _git(checkout, 'ls-tree', '-rz', revision, '--', package.as_posix()).split(b'\0')
    for entry in filter(None, entries):
        meta, raw_path = entry.split(b'\t', 1)
        mode, _, oid = meta.split()
        path = PurePosixPath(raw_path.decode())
        if mode not in (b'100644', b'100755') or path.suffix != '.py':
            continue
        relative = path.relative_to(package.parent)
        module = list(relative.with_suffix('').parts)
        if module[-1] == '__init__':
            module.pop()
        name = '.'.join(module)
        raw = _git(checkout, 'cat-file', 'blob', oid.decode())
        encoding, _ = tokenize.detect_encoding(BytesIO(raw).readline)
        source = raw.decode(encoding)
        if name in modules:
            raise ValueError(f'Ambiguous Python module: {name}')
        modules[name] = (path, source, ast.parse(source, filename=path.as_posix()))
    if not modules:
        raise ValueError(f'No tracked Python source under {package}')
    return modules


def _declarations(tree):
    for node in tree.body:
        if isinstance(node, _FUNCTION):
            yield '', node
        elif isinstance(node, ast.ClassDef):
            for method in node.body:
                if isinstance(method, _FUNCTION):
                    yield node.name, method


def _imports(module, path, tree):
    package = module if path.name == '__init__.py' else module.rpartition('.')[0]
    aliases = defaultdict(list)
    for node in tree.body:
        if isinstance(node, ast.Import):
            for item in node.names:
                local = item.asname or item.name.split('.')[0]
                aliases[local].append(item.name if item.asname else local)
        elif isinstance(node, ast.ImportFrom):
            target = node.module or ''
            if node.level:
                try:
                    target = resolve_name('.' * node.level + target, package)
                except ImportError:
                    continue
            for item in node.names:
                if item.name != '*':
                    aliases[item.asname or item.name].append(f'{target}.{item.name}')
    return {name: values[0] for name, values in aliases.items() if len(values) == 1}


def _parameters(node):
    args = node.args
    positional = [*args.posonlyargs, *args.args]
    defaults = [None] * (len(positional) - len(args.defaults)) + args.defaults
    fields = [(arg, default, 'positional_only' if index < len(args.posonlyargs) else 'positional_or_keyword')
              for index, (arg, default) in enumerate(zip(positional, defaults, strict=True))]
    if args.vararg:
        fields.append((args.vararg, None, 'variadic_positional'))
    fields.extend((arg, default, 'keyword_only') for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True))
    if args.kwarg:
        fields.append((args.kwarg, None, 'variadic_keyword'))
    return [{'name': arg.arg, 'kind': kind, 'annotation': ast.unparse(arg.annotation) if arg.annotation else None,
             'default': ast.unparse(default) if default is not None else None} for arg, default, kind in fields]


def _scoped_ast(node):
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _NESTED_SCOPE):
            continue
        yield child
        yield from _scoped_ast(child)


def _dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = _dotted(node.value)
        if head:
            return f'{head}.{node.attr}'
    return ''


def _references(module, class_name, node, declarations, aliases):
    params = _parameters(node)
    body = [child for statement in node.body for child in (statement, *_scoped_ast(statement))
            if not isinstance(statement, _NESTED_SCOPE)]
    locals_ = {parameter['name'] for parameter in params}
    locals_.update(child.id for child in body if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store))
    locals_.update(item.asname or item.name.split('.')[0] for child in body
                   if isinstance(child, (ast.Import, ast.ImportFrom)) for item in child.names)
    receiver = params[0]['name'] if class_name and params else None
    calls = []
    for call in (child for child in body if isinstance(child, ast.Call)):
        expression = _dotted(call.func)
        head, _, suffix = expression.partition('.')
        target = None
        resolution = None
        if head and head == receiver and head in {'self', 'cls'} and suffix and '.' not in suffix:
            target = f'{module}.{class_name}.{suffix}'
            resolution = 'same-class declaration'
        elif head and head not in locals_:
            if head in aliases.get(module, {}):
                target = aliases[module][head] + (f'.{suffix}' if suffix else '')
                resolution = 'module import'
            else:
                target = f'{module}.{expression}'
                resolution = 'same-module declaration'
        seen = set()
        while target and target not in declarations and target not in seen:
            seen.add(target)
            target_module, _, name = target.rpartition('.')
            target = aliases.get(target_module, {}).get(name)
        if target not in declarations or declarations.get(target) != 1:
            target, resolution = None, None
        calls.append({'line': call.lineno, 'column': call.col_offset + 1, 'expression': ast.unparse(call.func),
                      'arguments': [ast.unparse(arg) for arg in call.args],
                      'keywords': [{'name': item.arg, 'value': ast.unparse(item.value)} for item in call.keywords],
                      'target': target, 'resolution': resolution})
    return sorted(calls, key=lambda item: (item['line'], item['column']))


def extract_python_catalog(checkout: Path, revision: str, package: str) -> dict:
    """Read the selected commit's source blobs. Catalog entries are source only."""
    if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', revision):
        raise ValueError('Supply a full Git commit ID')
    if _git(checkout, 'rev-parse', f'{revision}^{{commit}}').decode().strip() != revision:
        raise ValueError('The source pin must identify a commit')
    package_path = PurePosixPath(package)
    if not package_path.parts or not all(part.isidentifier() for part in package_path.parts):
        raise ValueError('Supply a package path relative to the repository')
    modules = _read_modules(checkout, revision, package_path)
    definitions = [(module, cls, node) for module, (_, _, tree) in modules.items()
                   for cls, node in _declarations(tree)]
    qualified = lambda module, cls, node: '.'.join(filter(None, (module, cls, node.name)))
    declarations = Counter(qualified(module, cls, node) for module, cls, node in definitions)
    aliases = {module: _imports(module, path, tree) for module, (path, _, tree) in modules.items()}
    groups = defaultdict(list)
    for module, cls, node in definitions:
        path, source, _ = modules[module]
        name = qualified(module, cls, node)
        first = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)])
        code = ''.join(source.splitlines(keepends=True)[first - 1:node.end_lineno])
        params = _parameters(node)
        returns = ast.unparse(node.returns) if node.returns is not None else None
        group = path.parent.as_posix()
        groups[group].append({
            'id': name if declarations[name] == 1 else f'{name}@{node.lineno}',
            'name': f'{cls}.{node.name}' if cls else node.name,
            'symbol': name, 'path': path.as_posix(), 'line': first, 'end_line': node.end_lineno,
            'code': code, 'language': 'python', 'source_package': group,
            'input': ', '.join(param['name'] for param in params), 'output': returns,
            'parameters': params, 'return_annotation': returns, 'async': isinstance(node, ast.AsyncFunctionDef),
            'calls': _references(module, cls, node, declarations, aliases),
        })
    remote = _git(checkout, 'remote', 'get-url', 'origin').decode().strip()
    url = urlsplit(remote)
    if url.scheme != 'https' or not url.hostname:
        raise ValueError('An HTTPS origin is required to record source links')
    repository = urlunsplit(('https', url.hostname, url.path.removesuffix('.git'), '', ''))
    return {'schema': 'factory.python-source-catalog.v1', 'id': package_path.name,
            'name': package_path.name, 'repository': repository, 'revision': revision,
            'method': 'Pinned Git blobs and Python AST', 'execution_verified': False,
            'files': len(modules),
            'groups': [{'id': group, 'name': group, 'parts': values} for group, values in sorted(groups.items())]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--package', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    catalog = extract_python_catalog(args.checkout.resolve(strict=True), args.revision, args.package)
    write_json(args.output, catalog)
    parts = [part for group in catalog['groups'] for part in group['parts']]
    print(json.dumps({'files': catalog['files'], 'functions': len(parts),
                      'resolved_calls': sum(call['target'] is not None for part in parts for call in part['calls'])}))


if __name__ == '__main__':
    main()
