"""Refresh documentation projections from canonical examples, never runtime evidence."""
import json
import re


def refresh(vault, check=False):
    path = vault / 'types/evidence-bundle.md'
    text = path.read_text(encoding='utf-8')
    examples = {}
    for name in ('intake', 'source-text', 'research-brief'):
        source = (vault / 'types' / (name + '.md')).read_text(encoding='utf-8')
        match = re.search(r'```json\s*\n(.*?)```', source, re.S)
        examples[name] = json.loads(match.group(1))
    value = {
        'subject': {'capsule_name': 'research.compile_brief', 'decl_hash': '0' * 64,
                    'summary': 'Compile source-grounded objectives, constraints and acceptance into a Research Brief.'},
        'criteria': [{'check_id': 'brief_objective_faithful',
                      'description': 'The Brief preserves mandatory task requirements without inventing evidence.',
                      'rubric': 'Check each mandatory requirement against the supplied source evidence; missing or unsupported coverage cannot pass.',
                      'over': 'inputs_and_outputs'}],
        'inputs': {'intake': examples['intake'], 'source_text': examples['source-text']},
        'outputs': {'research_brief': examples['research-brief']},
        'issues': {'research_brief': []},
    }
    block = '<!-- generated:example-view -->\n```json\n' + json.dumps(value, indent=2) + '\n```\n<!-- /generated:example-view -->'
    pattern = r'<!-- generated:example-view -->.*?<!-- /generated:example-view -->'
    if re.search(pattern, text, re.S):
        updated = re.sub(pattern, lambda _: block, text, flags=re.S)
    else:
        updated = re.sub(r'```json\s*\n.*?```', lambda _: block, text, count=1, flags=re.S)
    same = updated == text
    if not same and not check:
        path.write_text(updated, encoding='utf-8', newline='\n')
    return refresh_production_flow(vault, check) and (same or not check)


def refresh_production_flow(vault, check=False):
    pipeline = (vault / 'm1/pipeline.md').read_text(encoding='utf-8')
    plan = json.loads(re.search(r'```json\s*\n(.*?)```', pipeline, re.S).group(1))
    outputs = {}
    for line in pipeline.splitlines():
        match = re.match(r'^\| ([a-z]+) \| (research\.[a-z_]+) \| [^|]+ \| ([a-z_]+) \|', line)
        if match:
            outputs[match.group(1)] = match.group(3)
    lines = ['```mermaid', 'flowchart TB', '    IN["Launcher: committed intake and source_text"]']
    previous, payload = 'IN', 'intake and source_text'
    for ordinal, step in enumerate(plan['steps']):
        node = 'P' + str(ordinal)
        lines.append(f'    {node}["{step["step_id"]}: {step["capsule_name"]}"]')
        lines.append(f'    {previous} -->|"{payload}"| {node}')
        previous, payload = node, outputs[step['step_id']]
    lines += ['    PUB["Publisher: committed report manifest"]', f'    {previous} -->|"{payload}"| PUB', '```']
    block = '<!-- generated:production-flow -->\n' + '\n'.join(lines) + '\n<!-- /generated:production-flow -->'
    path = vault / 'system/diagram-atlas.md'
    text = path.read_text(encoding='utf-8')
    updated = re.sub(r'<!-- generated:production-flow -->.*?<!-- /generated:production-flow -->', lambda _: block, text, flags=re.S)
    if text == updated:
        return True
    if check:
        return False
    path.write_text(updated, encoding='utf-8', newline='\n')
    return True
