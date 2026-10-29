"""Capability table shared by the executor, the skill-pack generator and the tests.

One entry per selectable capability of the CC library snapshot (planner/library.py).
The executable subset runs the real, deterministic product bodies (pure functions;
no model, no network). Capabilities with no deterministic body (research.*) are
listed so both arms see the same set; a plan that uses one is "not executable".

The typed variants (calculate_typed, ...) share the base worker in the product, so
the executor aliases them to the same body.
"""
import sys
sys.dont_write_bytecode = True

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import roots  # noqa: E402

REPO = str(roots.code_root())
if REPO not in sys.path:
    sys.path.insert(0, REPO)

# kind: how the skill arm sees it ("tool" = plain python file with a docstring,
# "skill" = a folder with SKILL.md). Parameter kinds are what the executor
# type-checks: "packet" (a work-packet dict) or "summary" (a paper-summary dict).
PARAM = {
    'utility.calculate': ('tool', 'packet', 'packet'),
    'utility.calculate_typed': ('tool', 'packet', 'packet'),
    'utility.table_normalize': ('tool', 'packet', 'packet'),
    'utility.table_normalize_typed': ('tool', 'packet', 'packet'),
    'utility.markdown_report': ('tool', 'packet', 'packet'),
    'utility.markdown_report_typed': ('tool', 'packet', 'packet'),
    'utility.packet_report': ('tool', 'packet', 'packet'),
    'utility.summary_to_packet': ('skill', 'summary', 'summary'),
}
# Library members that exist for both arms but have no deterministic body here.
NON_EXECUTABLE = [
    'research.search', 'research.screening', 'research.hypothesis', 'research.builder',
    'research.benchmark', 'research.evaluation', 'research.delivery',
    'research.paper_summary', 'research.paper_summary_delivery', 'research.generalist',
]
OUTPUT = 'result'          # every executable capability returns one packet
OUTPUT_KIND = 'packet'

# Kind of a supplied input, from its declared artifact type.
KIND_OF_TYPE = {'work_packet': 'packet', 'paper_summary': 'summary'}


def _bodies():
    from jiuwenswarm.research.capsule_extensions.packet import output_packet
    from jiuwenswarm.research.capsule_extensions.calculate.worker import calculate
    from jiuwenswarm.research.capsule_extensions.table_normalize.worker import normalize
    from jiuwenswarm.research.capsule_extensions.markdown_report.worker import render as md_render
    from jiuwenswarm.research.capsule_extensions.packet_report.worker import render as pk_render
    from jiuwenswarm.research.capsule_extensions.summary_to_packet.worker import convert

    def run_calculate(p):
        return output_packet(p, data=dict(p['data'], calculation_result=calculate(p)))

    def run_normalize(p):
        return output_packet(p, data=dict(p['data'], table=normalize(p)))

    return {
        'utility.calculate': run_calculate, 'utility.calculate_typed': run_calculate,
        'utility.table_normalize': run_normalize, 'utility.table_normalize_typed': run_normalize,
        'utility.markdown_report': md_render, 'utility.markdown_report_typed': md_render,
        'utility.packet_report': pk_render, 'utility.summary_to_packet': convert,
    }


_BODIES = None


def body(name):
    """The deterministic product body, or None if the capability has none."""
    global _BODIES
    if _BODIES is None:
        _BODIES = _bodies()
    return _BODIES.get(name)


def all_names():
    """Every selectable capability name, in a stable order (library order, deduplicated)."""
    return list(PARAM) + NON_EXECUTABLE


def resolve(name):
    """Map a written capability name to (canonical, how). how in {'exact','alias',None}.

    An alias is a case/whitespace difference or a missing 'utility.'/'research.'
    prefix that identifies exactly one capability. Anything else is fabricated.
    """
    if not isinstance(name, str):
        return None, None
    n = name.strip()
    names = all_names()
    if n in names:
        return n, 'exact'
    low = n.lower()
    for c in names:
        if c.lower() == low:
            return c, 'alias'
    bare = [c for c in names if c.split('.', 1)[1].lower() == low]
    if len(bare) == 1:
        return bare[0], 'alias'
    return None, None
