"""Every product call of parse_predictions passes its stdout bound.

Live run pl2 (2026-10-29): the Builder smoke check called it without
max_stdout_bytes; the TypeError escaped and halted Builder as an opaque
executor fault after a passing smoke run.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / 'jiuwenswarm'


def test_every_parse_predictions_call_names_max_stdout_bytes():
    missing = []
    for path in ROOT.rglob('*.py'):
        for node in ast.walk(ast.parse(path.read_bytes(), str(path))):
            if (isinstance(node, ast.Call) and getattr(node.func, 'id', getattr(node.func, 'attr', None)) == 'parse_predictions'
                    and 'max_stdout_bytes' not in {k.arg for k in node.keywords}):
                missing.append('%s:%d' % (path.relative_to(ROOT), node.lineno))
    assert not missing, missing
