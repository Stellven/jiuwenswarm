"""Run the partner's unchanged declaration-derived checks on exported tools.

Invoked inside the chosen benchmark image by run_t1_rsi.py validate. This
records benchmark compatibility only, never production admission.
"""
import importlib.util
import json
from pathlib import Path
import sys

partner, served = map(Path, sys.argv[1:3])
sys.path[:0] = [str(partner / 'benchmarks/ccbench/admission')]
from derive import derive_tests
from study import assess

declarations = json.loads((partner / 'benchmarks/ccbench/admission/declarations.json').read_bytes())
families = sys.argv[3:]
tools = {'calculate': 'calc_tool.py', 'table_normalize': 'table_tool.py'}
if not families or len(families) != len(set(families)) or not set(families) <= set(tools):
    raise ValueError('Explicit supported validation families required')
rows = []
for family in families:
    tool = tools[family]
    spec = importlib.util.spec_from_file_location('rsi_' + family, served / tool)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    passed, evidence = assess(family, module.run, derive_tests(declarations[family]))
    rows.append({'family': family, 'passed': passed, 'tests': len(evidence),
                 'failures': [row for row in evidence if not row['pass']]})
print(json.dumps({'schema': 'ai4r-t1-rsi-contract-validation:1', 'rows': rows,
                  'passed': all(row['passed'] for row in rows), 'production_admission': 'UNKNOWN'}))
sys.exit(0 if all(row['passed'] for row in rows) else 1)
