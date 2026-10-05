"""Bounded architecture review inputs; hashes establish freshness, not correctness."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(name):
    path = (ROOT / name).resolve()
    relative = path.relative_to(ROOT).as_posix()
    if not relative.startswith(('docs/architecture/', 'docs/product/')):
        raise ValueError('Review inputs must be architecture or frozen product documents')
    if '.obsidian' in path.parts or path.suffix not in {'.md', '.txt', '.json', '.py'}:
        raise ValueError('Unsupported review input: ' + relative)
    if not path.is_file():
        raise ValueError('Missing input: ' + relative)
    return path, relative


def changes(base):
    # HEAD plus index and working tree changes relative to the selected baseline.
    names = git('diff', '--name-only', base, '--', 'docs/architecture', 'docs/product').splitlines()
    untracked = git('ls-files', '--others', '--exclude-standard', '--',
                    'docs/architecture', 'docs/product').splitlines()
    return sorted(set(names + untracked) - {n for n in untracked if '/.obsidian/' in n})


def generate(args):
    output = Path(args.out).resolve()
    if output.suffix != '.json':
        raise ValueError('Packet output must end in .json')
    try:
        relative_output = output.relative_to(ROOT).as_posix()
    except ValueError:
        relative_output = None
    if relative_output is not None and not relative_output.startswith('docs/architecture/reviews/'):
        raise ValueError('Repository packets belong in docs/architecture/reviews; use scratch otherwise')
    if output.exists() or output.with_suffix('.md').exists():
        raise ValueError('Packet or companion already exists; select a new revision filename')
    base = git('rev-parse', '--verify', args.base + '^{commit}').strip()
    changed = changes(base)
    if not args.include or not args.source:
        raise ValueError('Select owning/affected files and exact source ranges')
    baseline_sources = {'docs/product/SOURCE_FREEZE.md',
                        'docs/product/source-freeze-2026-10-02.json'}
    selected = sorted(set(args.include + args.impact) | baseline_sources)
    inputs = []
    for name in selected:
        path, relative = safe_path(name)
        inputs.append({'path': relative, 'sha256': digest(path.read_bytes()),
                       'role': 'source-baseline' if name in baseline_sources else
                               ('impact' if name in args.impact else 'owner')})
    excerpts = []
    for spec in args.source:
        match = re.fullmatch(r'(.+)#L(\d+)-L(\d+)', spec)
        if not match:
            raise ValueError('Source syntax: repo/path#LSTART-LEND')
        path, relative = safe_path(match[1])
        first, last = map(int, match.groups()[1:])
        lines = path.read_text(encoding='utf-8').splitlines()
        if not 1 <= first <= last <= len(lines):
            raise ValueError('Invalid source range: ' + spec)
        excerpts.append({'path': relative, 'sha256': digest(path.read_bytes()),
                         'first': first, 'last': last,
                         'text': '\n'.join(f'{i}: {lines[i-1]}' for i in range(first, last+1))})
    # Scope is intentionally selected, not every changed document in a large batch.
    diff = git('diff', '--no-ext-diff', '--no-color', base, '--', *selected)
    packet = {'format_version': 1, 'base_commit': base,
              'head_at_creation': git('rev-parse', 'HEAD').strip(),
              'focus': args.focus, 'inputs': inputs, 'source_excerpts': excerpts,
              'selected_diff': diff, 'selected_diff_sha256': digest(diff.encode('utf-8')),
              'changed_paths_at_creation': changed,
              'unselected_changes': [n for n in changed if n not in selected],
              'impact_complete': False,
              'limitations': ['Author-selected scope requires reviewer confirmation.',
                             'No semantic, runtime or full-PRD acceptance is implied.']}
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = ['---', 'type: review', 'status: draft', 'tags: [review, packet]', '---', '',
                '# Bounded review packet', '', args.focus, '',
                f'Baseline: `{base}`. Packet: `{output.name}`.', '',
                '## Scope confirmation', '',
                'Confirm affected owners, consumers, Gates, records, diagrams and fixtures before reviewing.',
                'Unselected changes are inventory only. Report missing impact as a finding; do not certify this batch.', '',
                '## Inputs', '']
    for item in inputs:
        rendered.append(f"- `{item['path']}` ({item['role']}), SHA-256 `{item['sha256']}`")
    rendered.extend(['', '## Exact source excerpts', ''])
    for source in excerpts:
        rendered.extend([f"### {source['path']} L{source['first']}–L{source['last']}", '',
                         '```text', source['text'], '```', ''])
    rendered.extend(['## Review output', '',
                     'Use the roles and finding format in review-workflow.md. Cite evidence, not agreement.', '',
                     '## Selected diff', '', '````diff', diff.rstrip(), '````', ''])
    # Exclusive creation protects existing files even if a second process races us.
    # A partial pair after an I/O failure is incomplete evidence, never a review pass.
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(packet, ensure_ascii=False, indent=2) + '\n')
    with output.with_suffix('.md').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write('\n'.join(rendered))
    print(f'Packet written: {output}; {len(inputs)} inputs, {len(excerpts)} source ranges')


def check(args):
    packet = json.loads(Path(args.packet).read_text(encoding='utf-8'))
    stale = []
    for item in packet['inputs'] + packet['source_excerpts']:
        try:
            path, _ = safe_path(item['path'])
            if digest(path.read_bytes()) != item['sha256']:
                stale.append(item['path'])
        except (ValueError, OSError):
            stale.append(item['path'])
    for item in packet['source_excerpts']:
        try:
            path, _ = safe_path(item['path'])
            lines = path.read_text(encoding='utf-8').splitlines()
            first, last = item['first'], item['last']
            if not 1 <= first <= last <= len(lines):
                stale.append('source range: ' + item['path'])
                continue
            expected = '\n'.join(f'{i}: {lines[i-1]}' for i in range(first, last+1))
            if expected != item['text']:
                stale.append('source excerpt: ' + item['path'])
        except (ValueError, OSError):
            stale.append('source excerpt: ' + item['path'])
    if digest(packet['selected_diff'].encode('utf-8')) != packet['selected_diff_sha256']:
        stale.append('embedded diff')
    diff = git('diff', '--no-ext-diff', '--no-color', packet['base_commit'], '--',
               *(item['path'] for item in packet['inputs']))
    if digest(diff.encode('utf-8')) != packet['selected_diff_sha256']:
        stale.append('selected diff')
    if stale:
        raise ValueError('STALE: ' + ', '.join(sorted(set(stale))))
    print('Fresh selected inputs and diff; impact completeness and review acceptance remain human/agent judgments')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create')
    create.add_argument('--base', required=True)
    create.add_argument('--include', action='append', default=[])
    create.add_argument('--impact', action='append', default=[])
    create.add_argument('--source', action='append', default=[])
    create.add_argument('--focus', required=True)
    create.add_argument('--out', required=True)
    verify = sub.add_parser('check')
    verify.add_argument('packet')
    args = parser.parse_args()
    try:
        generate(args) if args.command == 'create' else check(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
