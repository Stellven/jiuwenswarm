from ..generalist.checks import check as _check


def check(ctx, inputs, outputs):
    rows = _check(ctx, inputs, outputs)
    rename = {'packet_schema': 'result_schema', 'packet_integrity': 'result_integrity'}
    return [dict(row, check_id=rename[row['check_id']]) for row in rows]
