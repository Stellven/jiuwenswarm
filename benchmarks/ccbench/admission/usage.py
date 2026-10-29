"""Fixed synthetic office-data usage distribution, independent of candidates.

Probabilities are assumptions, not production telemetry. Samples are ordinary
transaction summaries / imported office tables; no defect-trigger lookup.
"""
import csv
import io
import json


def typical_use(tool, rng):
    n = rng.choices([0, 1, 4, 12], [3, 12, 50, 35])[0]
    if tool == 'calculate':
        mode = rng.choices(['json_numbers', 'decimal_strings'], [70, 30])[0]
        op = rng.choices(['count', 'sum', 'mean', 'min', 'max'], [10, 40, 30, 10, 10])[0]
        values = []
        for _ in range(n):
            # Counts, prices, signed refunds, and occasional long account IDs.
            category = rng.random()
            if category < .70: v = rng.randint(0, 1000)
            elif category < .94: v = rng.randint(0, 100000) / 100
            elif category < .995: v = -rng.randint(1, 100)
            else: v = rng.randrange(10**16, 10**17)
            values.append(str(v) if mode == 'decimal_strings' else v)
        # Rare user-supplied data entry, sampled without consulting defects.
        if values and rng.random() < .015:
            values[rng.randrange(len(values))] = rng.choice([None, True, '1,25', '１２'])
        return {'values': values, 'mode': mode, 'operation': op}
    fmt = rng.choices(['csv', 'json'], [65, 35])[0]
    columns = ['account', 'amount']
    rows = []
    for _ in range(n):
        name = 'acct_' + str(rng.randint(1, 999))
        if rng.random() < .02: name = ' '+name+' '
        value = rng.randint(0, 1000)
        if fmt == 'json':
            category = rng.random()
            if category < .03: value = rng.choice([True, False, None])
            elif category < .035: value = rng.randrange(10**16, 10**17)
        rows.append([name, value])
    if fmt == 'json':
        return {'format':fmt,'text':json.dumps([dict(zip(columns,r)) for r in rows]),'columns':columns,'delimiter':None}
    if rows and rng.random() < .01: rows[rng.randrange(len(rows))].pop()
    stream = io.StringIO(newline='')
    csv.writer(stream).writerows([columns,*rows])
    return {'format':fmt,'text':stream.getvalue(),'columns':columns,'delimiter':','}
