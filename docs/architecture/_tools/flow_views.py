"""Generate the flow views from the single graph source block in flow.md.

flow.md holds the full view; flow-variants.md holds no-observability, no-rsi and core.

Usage: python flow_views.py [--check]
Source lines may start with [obs], [rsi] or [detail]; untagged lines are core. [detail] is hidden in the core view.
"""
import re
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
VIEWS = [('flow.md', 'full', True, True, True), ('flow-variants.md', 'no-observability', False, True, True),
         ('flow-variants.md', 'no-rsi', True, False, True), ('flow-variants.md', 'core', False, False, False)]


def source_lines(text):
    m = re.search(r'<!-- flow-source:begin -->\s*```text\n(.*?)```\s*<!-- flow-source:end -->', text, re.S)
    if not m:
        raise ValueError('flow-source block not found')
    return m.group(1).rstrip('\n').split('\n')


def render(lines, obs, rsi, detail=True):
    keep = []
    for line in lines:
        tag = re.match(r'\s*\[(obs|rsi|detail)\]\s?', line)
        if tag:
            if (tag.group(1) == 'obs' and not obs) or (tag.group(1) == 'rsi' and not rsi) or (tag.group(1) == 'detail' and not detail):
                continue
            line = '  ' + line[tag.end():]
        keep.append(line)
    return '```mermaid\n' + '\n'.join(keep) + '\n```'


def refresh(check=False):
    lines = source_lines((VAULT / 'flow.md').read_text(encoding='utf-8'))
    texts = {}
    for fname, name, obs, rsi, detail in VIEWS:
        if fname not in texts:
            texts[fname] = (VAULT / fname).read_text(encoding='utf-8')
        marker = f'flow-{name}'
        block = '\n'.join(['<!-- generated:' + marker + ' -->', render(lines, obs, rsi, detail), '<!-- /generated:' + marker + ' -->'])
        pattern = rf'<!-- generated:{marker} -->.*?<!-- /generated:{marker} -->'
        if not re.search(pattern, texts[fname], re.S):
            raise ValueError(f'missing marker {marker} in {fname}')
        texts[fname] = re.sub(pattern, lambda _: block, texts[fname], flags=re.S)
    current = all((VAULT / f).read_text(encoding='utf-8') == t for f, t in texts.items())
    if current:
        return True
    if check:
        return False
    for f, t in texts.items():
        (VAULT / f).write_text(t, encoding='utf-8', newline='\n')
    return True


if __name__ == '__main__':
    ok = refresh(check='--check' in sys.argv)
    print('flow views current' if ok else 'flow views STALE')
    sys.exit(0 if ok else 1)
