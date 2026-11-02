"""Run one SIMLAB-Bench oracle in isolation: python -I run_oracle.py ORACLE EVIDENCE CRITERIA OUT. Standard library only."""
import importlib.util
import json
import sys

spec = importlib.util.spec_from_file_location("case_oracle", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
evidence = json.load(open(sys.argv[2]))
criteria = json.load(open(sys.argv[3]))
result = mod.evaluate(evidence, criteria)
json.dump(result, open(sys.argv[4], "w"), indent=1, sort_keys=True)
