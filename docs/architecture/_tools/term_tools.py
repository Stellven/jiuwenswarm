"""Key terms live next to the item they name. This tool indexes them and links first uses.

Convention: a page that is the home of a concept has a section

    ## Key terms

    | Term | Meaning |
    |---|---|
    | **Declaration** (also: Declarations) | the typed contract of a capsule ... |

Rules:
  * a term is defined on exactly one page (the page that is the item's home)
  * `index`  writes the generated term index into terms.md (term, first sentence, link). The index copies nothing by hand.
  * `link`   links the FIRST use of each term on every other page to the defining row (anchor `term-<slug>`).
  * `check`  fails on duplicate definitions, missing anchors, or a row without a meaning.
Usage: python term_tools.py index|link|check|all [--dry]
"""
import re
import sys
from pathlib import Path

V = Path(__file__).resolve().parent.parent
SKIP_DIRS = ('.obsidian', '_tools', 'exports', 'data-foundation', 'contracts/fixtures')
SKIP_FILES = {'model_router_design_en.md'}
NO_LINK_PAGES = {'terms.md', 'README.md', 'flow-variants.md', 'contracts/boundaries.md', 'standards.md'}
GENERIC = {'Run', 'Phase', 'Step', 'Node', 'Release', 'Halt', 'Resume', 'Attempt', 'Dispatch', 'Reservation', 'Block', 'Boundary',
           'Fixture', 'Demo', 'Probe', 'Doctor', 'Track', 'Adapter', 'Seam', 'Session', 'Quota', 'Trial', 'Body', 'Carrier',
           'Check', 'Port', 'Port type', 'Needs', 'Effects', 'Guarantees', 'Evolution', 'Lineage', 'Alias', 'Registry', 'Epoch',
           'Policy', 'Freeze', 'Call', 'Frame', 'Report', 'Helper', 'Record', 'Referee', 'Provisional', 'Exempt', 'Rollback',
           'Activation', 'Admission', 'Intake', 'Delivery', 'Planner', 'Runner', 'Broker', 'Verifier', 'Supervisor', 'Singleton',
           'Headless', 'Confinement', 'Deviation', 'Rubric', 'Candidate', 'Standing', 'Finding', 'Verdict', 'Artifact',
           'Task node', 'Prep node', 'Run graph', 'Fixed node'}
ROW = re.compile(r'^\| (<a id="term-[^"]+"></a>)?\*\*(.+?)\*\*(?: \(also: ([^)]*)\))? \| (.+) \|$')


def slug(t):
    return re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-')


def pages():
    for p in sorted(V.rglob('*.md')):
        rel = p.relative_to(V).as_posix()
        if any(rel.startswith(s) for s in SKIP_DIRS) or p.name in SKIP_FILES:
            continue
        yield p, rel


def read(p):
    return p.read_bytes().decode('utf-8').replace('\r\n', '\n')


def key_terms(text):
    """-> list of (term, aliases, meaning) from the page's Key terms section."""
    m = re.search(r'^## Key terms\s*\n(.*?)(?=^## |\Z)', text, re.S | re.M)
    out = []
    if not m:
        return out
    for line in m.group(1).split('\n'):
        r = ROW.match(line)
        if r:
            aliases = [a.strip() for a in (r.group(3) or '').split(',') if a.strip()]
            out.append((r.group(2), aliases, r.group(4)))
    return out


def registry():
    reg, problems = {}, []
    for p, rel in pages():
        for term, aliases, meaning in key_terms(read(p)):
            if term in reg:
                problems.append(f'term "{term}" defined on both {reg[term]["page"]} and {rel}')
            reg[term] = {'page': rel, 'aliases': aliases, 'meaning': meaning, 'slug': slug(term)}
    return reg, problems


def add_anchors():
    changed = 0
    for p, rel in pages():
        text = read(p)
        out = []
        for line in text.split('\n'):
            r = ROW.match(line)
            if r and not r.group(1):
                line = line.replace('| **', f'| <a id="term-{slug(r.group(2))}"></a>**', 1)
                changed += 1
            out.append(line)
        if changed:
            new = '\n'.join(out)
            if new != text:
                p.write_bytes(new.encode('utf-8'))
    return changed


def first_sentence(m):
    m = re.sub(r'\s+', ' ', m)
    s = re.split(r'(?<=[.!?])\s', m, 1)[0]
    return s[:200]


def index(dry=False):
    add_anchors()
    reg, problems = registry()
    rows = ['| Term | Meaning | Defined on |', '|---|---|---|']
    for term in sorted(reg, key=str.lower):
        d = reg[term]
        rows.append(f'| **{term}** | {first_sentence(d["meaning"])} | [{d["page"]}]({d["page"]}#term-{d["slug"]}) |')
    block = ('<!-- generated:term-index -->\n' + '\n'.join(rows) + '\n<!-- /generated:term-index -->')
    path = V / 'terms.md'
    text = read(path)
    pat = r'<!-- generated:term-index -->.*?<!-- /generated:term-index -->'
    if not re.search(pat, text, re.S):
        print('terms.md has no term-index markers')
        return 1
    new = re.sub(pat, lambda _: block, text, flags=re.S)
    if not dry and new != text:
        path.write_bytes(new.encode('utf-8'))
    print(f'term index: {len(reg)} terms')
    return 0


def protected_spans(line):
    """Spans of a line that must not be edited: inline code, links, html, bold term cells handled by caller."""
    spans = []
    for m in re.finditer(r'`[^`]*`|\[[^\]]*\]\([^)]*\)|<[^>]+>|\[\[[^\]]*\]\]', line):
        spans.append((m.start(), m.end()))
    return spans


def link(dry=False):
    reg, problems = registry()
    if problems:
        print('\n'.join(problems))
        return 1
    n = 0
    names = []
    for term, d in reg.items():
        for form in [term] + d['aliases']:
            generic = form in GENERIC or form.lower() in {g.lower() for g in GENERIC} and form[0].islower()
            if len(form) >= 3 and not generic:
                names.append((form, term))
    names.sort(key=lambda x: -len(x[0]))
    for p, rel in pages():
        text = read(p)
        fm = re.match(r'---\n.*?\n---\n', text, re.S)
        head, body = (text[:fm.end()], text[fm.end():]) if fm else ('', text)
        lines = body.split('\n')
        done = set(re.findall(r'#term-([a-z0-9-]+)\)', body))
        in_code = False
        in_comment = False
        seen_h1 = False
        for i, line in enumerate(lines):
            if line.startswith('```'):
                in_code = not in_code
                continue
            if in_code:
                continue
            if '<!--' in line:
                in_comment = '-->' not in line
                continue
            if in_comment:
                in_comment = '-->' not in line
                continue
            if line.startswith('#'):
                seen_h1 = seen_h1 or line.startswith('# ')
                continue
            if not seen_h1 or line.startswith(('PRD:', '> Answers:', '|---', '| Term | Meaning')) or ROW.match(line):
                continue
            for form, term in names:
                d = reg[term]
                if d['page'] == rel or d['slug'] in done:
                    continue
                spans = protected_spans(line)
                for m in re.finditer(r'(?<![\w`/#.-])' + re.escape(form) + r'(?![\w`-])', line):
                    if any(a <= m.start() < b for a, b in spans):
                        continue
                    target = Path(d['page'])
                    cur = Path(rel).parent
                    relpath = Path(__import__('os').path.relpath(target, cur)).as_posix()
                    repl = f'[{form}]({relpath}#term-{d["slug"]})'
                    line = line[:m.start()] + repl + line[m.end():]
                    done.add(d['slug'])
                    n += 1
                    spans = protected_spans(line)
                    break
            lines[i] = line
        new = head + '\n'.join(lines)
        if new != text and not dry:
            p.write_bytes(new.encode('utf-8'))
    print(f'linked {n} first uses')
    return 0


def unlink():
    n = 0
    for p, rel in pages():
        text = read(p)
        new = re.sub(r'\[([^\]]+)\]\([^)\s]*#term-[a-z0-9-]+\)', lambda m: m.group(1), text)
        if new != text:
            n += len(re.findall(r'#term-', text)) - len(re.findall(r'#term-', new))
            p.write_bytes(new.encode('utf-8'))
    print('removed', n, 'term links')
    return 0


def check():
    reg, problems = registry()
    for p, rel in pages():
        text = read(p)
        for line in text.split('\n'):
            if line.startswith('| **') and ROW.match(line) is None and rel != 'terms.md' and 'Key terms' in text:
                pass
        if re.search(r'^## Key terms', text, re.M) and not key_terms(text):
            problems.append(f'{rel}: Key terms section has no valid rows (| **Term** | meaning |)')
    for term, d in reg.items():
        if len(d['meaning'].strip()) < 12:
            problems.append(f'term "{term}" on {d["page"]}: meaning too short')
    if problems:
        print('\n'.join(problems))
        print(len(problems), 'term problem(s)')
        return 1
    print(f'terms ok: {len(reg)} terms, each defined once')
    return 0


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'check'
    dry = '--dry' in sys.argv
    if cmd == 'index':
        sys.exit(index(dry))
    if cmd == 'unlink':
        sys.exit(unlink())
    if cmd == 'link':
        sys.exit(link(dry))
    if cmd == 'check':
        sys.exit(check())
    if cmd == 'all':
        rc = check()
        rc = rc or index(dry)
        rc = rc or link(dry)
        sys.exit(rc)
    print(__doc__)
