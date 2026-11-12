"""Inventory declarations using the CC-v2 loader and validator."""
from pathlib import Path

from jiuwenswarm.ccv2.ccv2 import load, tree_files
from .story import paint, wrap


def capsule_rows(root=None):
    root = Path(root) if root else Path(__file__).parent / 'ccs'
    rows = []
    for path in sorted(root.rglob('cc.yaml')):
        declaration = load(path)
        caps = declaration.get('capabilities', {})
        rows.append(dict(id=declaration['id'], version=declaration['version'],
                         binding=','.join(sorted({b['kind'] for b in declaration.get('bindings', {}).values()})) or 'material-only',
                         capabilities=list(caps), changes=sorted({e for c in caps.values() for e in c.get('changes', [])}),
                         files=len(tree_files(path.parent)), lines=len(path.read_text().splitlines()), valid=True))
    return rows


def format_capsules(rows, plain=False):
    lines = ['ID                          VERSION BINDING        FILES YAML VALID', '─' * 99]
    for row in rows:
        lines.extend(wrap(f"{row['id']:27} {row['version']:7} {row['binding']:14} "
                          f"{row['files']:5} {row['lines']:4} ✓ valid"))
        lines.extend(wrap('capabilities: ' + (', '.join(row['capabilities']) or '·'), '  '))
        lines.extend(wrap('changes: ' + (', '.join(row['changes']) or '·'), '  '))
    lines.extend(wrap(f"{len(rows)} capsules · {sum(len(r['capabilities']) for r in rows)} capabilities · "
                      f"{sum(r['lines'] for r in rows)} lines of cc.yaml · 0 adapters"))
    return '\n'.join(paint(line, plain) for line in lines)
