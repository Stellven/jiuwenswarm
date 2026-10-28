"""Pure output-review wire representation; no Store or runtime authority.

Callers independently validate the declared type and archive representation
using their own installed contract authority before formatting these bytes.
"""
import json


def port_context(declaration: bytes, port: str, *, archive=False):
    outputs = json.loads(declaration)['ports']['outputs']
    selected = [row for row in outputs if row['name'] == port]
    if not isinstance(port, str) or not port or len(selected) != 1 or type(archive) is not bool:
        raise ValueError('One exact declared output port and representation required')
    selected = selected[0]
    return {'port_name': port, 'schema_ref': selected['schema_ref'], 'artifact_type': selected['artifact_type'],
            'subject_output_is': 'selected_port_value',
            'transport': 'archive_member_projection' if archive else 'exact_utf8_value'}


def system_text(instructions: str, criteria: list, context: dict):
    selected = [row for row in criteria if row['target_port'] in (None, context['port_name'])]
    return (instructions + '\nHost-selected output context (declaration metadata, not an extra output envelope):\n'
            + json.dumps(context, ensure_ascii=False, sort_keys=True)
            + '\nCriteria for this output:\n' + json.dumps(selected, ensure_ascii=False))


def payload_text(declaration: bytes, output: bytes):
    return json.dumps({'subject_declaration': declaration.decode('utf8'), 'subject_output': output.decode('utf8')}, ensure_ascii=False)
