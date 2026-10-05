"""Generate presentation tables and diagrams from canonical architecture owners."""
import json
import re
from pathlib import Path

def refresh(vault, check=False):
    root = vault / 'presentation/showcase'
    blocks = {}
    for target, source, index in [('system', 'system/overall-draft.md', 1),
                                   ('capsules', 'system/overall-draft.md', 0),
                                   ('recovery', 'system/information-flow.md', 4),
                                   ('experiments', 'system/experiments.md', 0)]:
        diagrams = re.findall(r'```mermaid\s*\n.*?```', (vault/source).read_text(encoding='utf-8'), re.S)
        blocks[target] = diagrams[index]
    pipeline = (vault/'m1/pipeline.md').read_text(encoding='utf-8')
    rows = re.findall(r'^\| ([a-z]+) \| (research\.[a-z_]+) \| ([^|]+) \| ([a-z_]+) \| ([^|]+) \|$', pipeline, re.M)
    blocks['ports'] = '\n'.join(['| Step / capability | Required inputs and context | Output | Gate profile |', '|---|---|---|---|'] +
        [f'| {step}: `{name}` | {inputs.strip()} | `{output}` | `{gate.strip()}` |' for step,name,inputs,output,gate in rows])
    manifest = json.loads((vault/'exports/manifest.json').read_text(encoding='utf-8'))
    blocks['schemas'] = '\n'.join(['| Definition | Exact version | Owning field table | Generated schema |', '|---|---|---|---|'] +
        [f'| `{s["name"]}` | `{s["version"]}` | [owner](../../{s["source"]}) | [schema](../../exports/{s["file"]}) |' for s in manifest['schemas']])
    success = True
    for filename, names in [('presentation.md',['system']), ('capsules.md',['capsules','ports']),
                             ('runtime-and-improvement.md',['recovery','experiments']), ('schemas-and-connections.md',['schemas'])]:
        path = root/filename
        original = path.read_text(encoding='utf-8')
        updated = original
        for name in names:
            marker = f'showcase-{name}'
            pattern = rf'<!-- generated:{marker} -->.*?<!-- /generated:{marker} -->'
            if not re.search(pattern, updated, re.S):
                raise ValueError(f'Missing {marker} in {filename}')
            block = f'<!-- generated:{marker} -->\n{blocks[name]}\n<!-- /generated:{marker} -->'
            updated = re.sub(pattern, lambda _: block, updated, flags=re.S)
        if original != updated:
            success = False
            if not check:
                path.write_text(updated, encoding='utf-8', newline='\n')
    return success or not check

if __name__ == '__main__':
    import sys
    raise SystemExit(0 if refresh(Path(__file__).resolve().parents[1], '--check' in sys.argv) else 1)
