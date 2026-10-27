"""Machine-selected read-only dependency context for proposer prompts.

Ported from Codex's ``capsule_context.py`` without its fixed source list, its
free-text ``diagnosis_facts``/``requirements`` channel and its pinned model
name. Given a worker body, ``dependency_context`` parses (never imports or
executes) its imports and returns bounded source excerpts:

* modules inside the capsule-extensions package (e.g. ``packet.py``) are
  included whole and followed for their own imports;
* names imported from the surrounding research package (e.g.
  ``ProducedArtifact`` from ``research/runner.py``) are included as exact
  definition excerpts;
* everything else (stdlib, third party) is omitted.

Every excerpt is pinned to its full source file digest and marked immutable.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from ..records import encoded
from .capsules import _PACKAGE, carrier_module, registered_capsule

SCHEMA = 'ai4r-rsi-capsule-dependency-context:1'
MAX_FILE_BYTES = 16 * 1024
MAX_TOTAL_BYTES = 48 * 1024
MAX_DEPTH = 2


def _source_root(source_root):
    # ``source_root`` is the directory holding the top-level package directory
    # (the repo root, or a frozen runtime's ``source/``).
    return Path(__file__).resolve().parents[3] if source_root is None else Path(source_root)


def _module_file(root, module):
    base = root.joinpath(*module.split('.'))
    for candidate in (base.with_suffix('.py'), base / '__init__.py'):
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    return None


def _resolve(current, node):
    """Absolute module names an import node refers to (``from X import a`` -> X, X.a)."""
    if isinstance(node, ast.Import):
        return [(alias.name, None) for alias in node.names]
    package = current.rpartition('.')[0]
    if node.level:
        parts = package.split('.')
        if node.level - 1 >= len(parts):
            return []
        base = '.'.join(parts[:len(parts) - (node.level - 1)])
        module = base + ('.' + node.module if node.module else '')
    else:
        module = node.module or ''
    return [(module, [alias.name for alias in node.names])]


def _definition(tree, lines, symbol):
    for node in tree.body:
        names = ([node.name] if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) else
                 [target.id for target in getattr(node, 'targets', []) if isinstance(target, ast.Name)]
                 + ([node.target.id] if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) else []))
        if symbol in names:
            first = min([node.lineno, *(item.lineno for item in getattr(node, 'decorator_list', []))])
            return first, node.end_lineno, ''.join(lines[first - 1:node.end_lineno])
    return None


def _owner(root, module, symbol, hops=2):
    """The module that defines ``symbol`` (following up to ``hops`` re-exports)."""
    path = _module_file(root, module)
    if path is None:
        return None
    source = path.read_text('utf-8')
    tree = ast.parse(source)
    if _definition(tree, source.splitlines(keepends=True), symbol) is not None:
        return module
    if hops:
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and any(alias.name == symbol and alias.asname in (None, symbol)
                                                        for alias in node.names):
                current = module + ('.__init__' if path.name == '__init__.py' else '')
                for target, _ in _resolve(current, node):
                    found = _owner(root, target, symbol, hops - 1)
                    if found is not None:
                        return found
    return None


def dependency_context(name, body, *, source_root=None, max_file_bytes=MAX_FILE_BYTES,
                       max_total_bytes=MAX_TOTAL_BYTES):
    """Bounded read-only excerpts of what the worker ``body`` imports.

    Returns ``{schema, capsule_name, mutable_path, sources, total_bytes,
    truncated, omitted}``; each source row is ``{module, path, selection,
    first_line, last_line, text, source_sha256, excerpt_sha256, truncated,
    mutable: False}``. A body that does not parse yields no sources and a
    ``parse_error``.
    """
    target = registered_capsule(name)
    root = _source_root(source_root)
    extensions = _PACKAGE
    research = _PACKAGE.rpartition('.')[0]
    worker = carrier_module(name)
    text = body.decode('utf-8', 'replace') if isinstance(body, bytes) else str(body)
    value = {'schema': SCHEMA, 'capsule_name': name, 'mutable_path': target.carrier_path, 'sources': [],
             'total_bytes': 0, 'truncated': False, 'omitted': []}
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        value['parse_error'] = 'SyntaxError: %s (line %s)' % (error.msg, error.lineno)
        return value
    seen, symbols, order = set(), {}, []
    queue = [(worker, tree, 0)]
    while queue:
        current, node_tree, depth = queue.pop(0)
        for node in ast.walk(node_tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for module, names in _resolve(current, node):
                if module == extensions or module.startswith(extensions + '.'):
                    # Whole extension modules; ``from .. import packet`` names a submodule.
                    targets = [module] + [module + '.' + item for item in (names or ())
                                          if _module_file(root, module + '.' + item) is not None]
                    for item in targets:
                        path = _module_file(root, item)
                        if path is None or item in seen or item == worker or item.endswith('.__init__'):
                            continue
                        if path.name == '__init__.py' and item != module:
                            continue
                        if path.name == '__init__.py' and not path.read_text('utf-8').strip():
                            continue
                        seen.add(item); order.append(('whole', item, path))
                        if depth + 1 < MAX_DEPTH:
                            queue.append((item, ast.parse(path.read_text('utf-8')), depth + 1))
                elif module == research or module.startswith(research + '.'):
                    if names:
                        bucket = symbols.setdefault(module, [])
                        bucket.extend(item for item in names if item not in bucket and item != '*')
                    elif module not in seen:
                        value['omitted'].append(module)
    for module, names in symbols.items():
        if module in seen:
            continue
        for symbol in names:
            # Follow re-exports (``from .errors import X`` in a package __init__).
            owner = _owner(root, module, symbol)
            if owner is None:
                value['omitted'].append(module + '.' + symbol)
                continue
            entry = next((row for row in order if row[0] == 'symbols' and row[1] == owner), None)
            if entry is None:
                order.append(('symbols', owner, [symbol]))
            elif symbol not in entry[2]:
                entry[2].append(symbol)
    total = 0
    for kind, module, extra in order:
        path = extra if kind == 'whole' else _module_file(root, module)
        if path is None:
            value['omitted'].append(module)
            continue
        raw = path.read_bytes()
        source = raw.decode('utf-8')
        lines = source.splitlines(keepends=True)
        pieces = []
        if kind == 'whole':
            pieces.append(('whole_file', 1, len(lines), source))
        else:
            parsed = ast.parse(source)
            for symbol in extra:
                pieces.append((symbol, *_definition(parsed, lines, symbol)))
        for selection, first, last, excerpt in pieces:
            encoded_text = excerpt.encode('utf-8')
            truncated = len(encoded_text) > max_file_bytes
            if truncated:
                excerpt = encoded_text[:max_file_bytes].decode('utf-8', 'ignore') + '\n# ... truncated ...\n'
            size = len(excerpt.encode('utf-8'))
            if total + size > max_total_bytes:
                value['truncated'] = True
                value['omitted'].append(module + ('' if selection == 'whole_file' else '.' + selection))
                continue
            total += size
            value['sources'].append({'module': module, 'path': path.relative_to(root).as_posix(),
                'selection': selection, 'first_line': first, 'last_line': last, 'text': excerpt,
                'source_sha256': hashlib.sha256(raw).hexdigest(),
                'excerpt_sha256': hashlib.sha256(excerpt.encode('utf-8')).hexdigest(),
                'truncated': truncated, 'mutable': False})
            value['truncated'] = value['truncated'] or truncated
    value['total_bytes'] = total
    value['context_sha256'] = hashlib.sha256(encoded({k: v for k, v in value.items() if k != 'context_sha256'})).hexdigest()
    return value


def render_dependency_context(context):
    """Prompt text for a context: one fenced, path-labelled block per excerpt."""
    blocks = []
    for row in context.get('sources', ()):
        label = row['path'] + ('' if row['selection'] == 'whole_file' else
                               ' (%s, lines %d-%d)' % (row['selection'], row['first_line'], row['last_line']))
        blocks.append('# read-only dependency: %s\n```python\n%s```' % (label, row['text'] if row['text'].endswith('\n')
                                                                          else row['text'] + '\n'))
    return '\n\n'.join(blocks)
