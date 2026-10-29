"""Request text and the neutral answer format. No CC vocabulary: no port names, check names, pins or schemas."""
import sys
sys.dont_write_bytecode = True

FORMAT_BLOCK = '''Answer with one JSON object and nothing else, in this shape:
{"feasible": true,
 "reason": "",
 "steps": [
   {"id": "s1",
    "capability": "<exact name of a listed tool or skill>",
    "inputs": {"<parameter name>": "<source>"},
    "depends_on": ["<id of an earlier step>"],
    "covers": ["D1"],
    "success_criteria": ["<how to tell that this step worked>"]}
 ],
 "final_step": "<id of the step whose output is the final result>"}
A source is either "input:<key of a supplied input>" or the id of an earlier step (its output).
"covers" lists the deliverables (D1, D2, ...) that the step helps produce.
If the request cannot be completed with the available tools and skills and the supplied inputs, set
"feasible" to false, "steps" to [], and give the actual reason in "reason".
Use only the listed capabilities. Plan only: do not run any tool.
'''


def capability_table():
    """The ordinary capability index (name, kind, what it does, file) from the skill pack's own index skill."""
    from pathlib import Path
    lines = (Path(__file__).resolve().parent / 'skillpack' / 'SKILL.md').read_text('utf-8').splitlines()
    return chr(10).join(l for l in lines if l.startswith('|'))


def request_with_format(task):
    """What the skill arm receives as the task: the shared request, the capability list, then the neutral format."""
    nl = chr(10)
    return (task['request'] + nl + 'Available tools and skills (use these exact names; files are in the skill folder):' + nl
            + capability_table() + nl + nl + FORMAT_BLOCK)


def shared_request(task):
    """What both arms are asked (the CC arm receives it as the Brief's objective text)."""
    return task['request']
