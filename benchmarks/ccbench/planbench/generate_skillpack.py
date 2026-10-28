"""Generate the skill arm's capability pack (ordinary tool files and SKILL.md folders) from the library.

Each description is the capability's own plain-language summary (identity.summary), nothing else from
the declaration. No port or artifact-type names, schema ids, check names, reason codes, pins or limits.
Tool files carry a normal signature and docstring and raise NotImplementedError: this is a planning
session, nothing is run, in either arm.

Run:  python -B planbench/generate_skillpack.py     (writes planbench/skillpack/; freeze with SHA256SUMS)
"""
import sys
sys.dont_write_bytecode = True
import importlib.util
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import caps

OUT = None   # set by main(): <--out>/skillpack
X3 = HERE.parent / 'skillpairs' / 'skills' / 'X3-plan' / 'SKILL.md'


def descriptions():
    spec = importlib.util.spec_from_file_location('planner_library', HERE.parent / 'planner' / 'library.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules['planner_library'] = mod
    spec.loader.exec_module(mod)
    seen, out = set(), {}
    for item in mod.undeclared_view():
        if item['name'] not in seen:             # first listing wins (two research.* names appear twice)
            seen.add(item['name'])
            out[item['name']] = item['description']
    return out


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode('utf-8'))


def tool_file(name, desc, pname):
    fn = name.split('.', 1)[1]
    what = {'packet': 'the packet to process (a dict)', 'summary': 'the structured paper summary (a dict)'}[pname]
    ret = 'the resulting packet (a dict)'
    return '''"""%s

%s
"""

TOOL_NAME = "%s"


def %s(%s: dict) -> dict:
    """%s.

    Args:
        %s: %s.
    Returns:
        %s.
    """
    raise NotImplementedError("Not installed in the planning session; plan only.")
''' % (name, desc, name, fn, pname, desc.rstrip('.'), pname, what, ret)


def skill_file(name, desc, kind_hint):
    slug = name.replace('.', '-').replace('_', '-')
    return '''---
name: %s
description: %s
---

# %s

%s

## How to call

Name the skill (`%s`) as a step in the plan. %s
''' % (slug, desc, name, desc, name, kind_hint)


def main(argv=None):
    global OUT
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True, help='writes DIR/skillpack')
    OUT = ap.parse_args(argv).out / 'skillpack'
    desc = descriptions()
    names = caps.all_names()
    assert set(names) == set(desc), (set(names) ^ set(desc))
    if OUT.exists():
        shutil.rmtree(OUT)
    rows = []
    for n in names:
        if n in caps.PARAM and caps.PARAM[n][0] == 'tool':
            rel = 'tools/%s.py' % n.replace('.', '_')
            write(OUT / rel, tool_file(n, desc[n], caps.PARAM[n][1]))
            rows.append((n, 'tool', rel))
        else:
            rel = 'skills/%s/SKILL.md' % n.replace('.', '-').replace('_', '-')
            hint = ('It takes the paper summary and returns a packet.' if n in caps.PARAM
                    else 'Give it the request context and the inputs it needs.')
            write(OUT / rel, skill_file(n, desc[n], hint))
            rows.append((n, 'skill', rel))
    (OUT / 'skills' / 'plan-research-workflow').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(X3, OUT / 'skills' / 'plan-research-workflow' / 'SKILL.md')
    index = ['---', 'name: available-capabilities',
             'description: The tools and skills available in this session, with what each does and where to read more. Use it to choose capabilities when planning.',
             '---', '', '# Available tools and skills', '',
             'Tools are Python functions in `tools/`; skills are folders in `skills/`. Use the exact name below when naming a capability.',
             '', '| Name | Kind | What it does | File |', '|---|---|---|---|']
    for n, kind, rel in rows:
        index.append('| `%s` | %s | %s | `%s` |' % (n, kind, desc[n].replace('|', '/'), rel))
    index += ['', 'The general planning skill is `skills/plan-research-workflow/SKILL.md`.', '']
    write(OUT / 'SKILL.md', '\n'.join(index))
    print('wrote', len(rows), 'capabilities to', OUT)


if __name__ == '__main__':
    main()
