"""Pure contract-to-test compiler. No filesystem, RNG, candidates or truth table.

Supported semantic vocabulary is intentionally bounded to the two port types in
this study. Returns fresh serializable input/assertion records, not callbacks.
"""
import csv
import io
import itertools
import json


def csv_input(columns, rows, delimiter=','):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, delimiter=delimiter)
    writer.writerows([columns, *rows])
    return {'text': stream.getvalue(), 'format': 'csv', 'columns': columns[:], 'delimiter': delimiter}


def json_input(columns, rows):
    return {'text': json.dumps([dict(zip(columns, r)) for r in rows], ensure_ascii=False), 'format': 'json', 'columns': columns[:], 'delimiter': None}


def derive_tests(declaration):
    ports = declaration['ports']['inputs']
    invariant = declaration.get('invariants', {})
    edges = declaration.get('edge_cases', [])
    ranges = declaration['ranges']
    tests = []
    # Assertions come from contract obligations, never candidate identities.
    semantic = bool(invariant)
    def add(p):
        tests.append({'input': p, 'assertions': ['output_types'] + (['declared_semantics'] if semantic else [])})
    if 'operation' in ports:
        sequences = [[1, 2], [0]]
        if 'empty' in edges: sequences.append([])
        if invariant.get('signed'): sequences.extend([[-1, 2], [-3, -1]])
        if 'numeric_boundaries' in edges:
            # Binary precision transition and declared decimal range boundaries.
            sequences.extend([[2**b + 1, 1] for b in [24, 53, 63]])
            sequences.extend([[10**ranges['max_digits'] - 1], [10**ranges['max_digits'] + 1]])
        for mode, op, seq in itertools.product(ports['mode'], ports['operation'], sequences):
            add({'values': [str(v) for v in seq] if mode == 'decimal_strings' else seq[:], 'mode': mode, 'operation': op})
        if 'type_boundaries' in edges:
            for value, mode, op in itertools.product([True, False, None, '', [], {}], ports['mode'], ports['operation']):
                add({'values': [value], 'mode': mode, 'operation': op})
        if 'representations' in edges:
            # Character-class / separator partitions derive from the grammar.
            tokens = ['1.5', '-0.5', '1e-28', '1e28', '1e-29', '1e29', '+2.0']
            if invariant.get('numeric_alphabet') == 'ascii': tokens.extend(['１２', '١٢'])
            if invariant.get('decimal_separator') == '.': tokens.extend(['1,5', '1 000', ' 2'])
            for token, op in itertools.product(tokens, ports['operation']):
                add({'values': [token, '2'], 'mode': 'decimal_strings', 'operation': op})
    elif 'format' in ports:
        columns = ['a', 'b']
        rows_sets = [[['x', '1'], ['y', '2']]]
        if 'empty' in edges: rows_sets.append([])
        if invariant.get('preserve_order'): rows_sets.append([['z', '3'], ['a', '1'], ['z', '3']])
        if 'type_boundaries' in edges:
            for v in [True, False, None, 0, 1.25, '', '001', '0.10']:
                rows_sets.append([[v, v]])
        if 'numeric_boundaries' in edges:
            rows_sets.extend([[[2**b+1, 0]] for b in [24, 53, 63]])
        if 'representations' in edges:
            rows_sets.extend([[[v, v]] for v in [' a ', 'é', '１２', 'a,b', 'line\nbreak', '"quoted"']])
        for fmt, rows in itertools.product(ports['format'], rows_sets):
            add(csv_input(columns, rows) if fmt == 'csv' else json_input(columns, rows))
        if 'malformed' in edges:
            for text in ['a,b\nx\n', 'a,b\nx,y,z\n', 'b,a\nx,y\n', 'a,b\n"unterminated']:
                add({'text': text, 'format': 'csv', 'columns': columns[:], 'delimiter': ','})
            for text in ['[{"a":1,"a":2,"b":3}]', '[{"a":1}]', '[{"a":[],"b":0}]', '[{"a":NaN,"b":0}]']:
                add({'text': text, 'format': 'json', 'columns': columns[:], 'delimiter': None})
        if 'representations' in edges:
            for delimiter in [';', '\t', '|']:
                add(csv_input(columns, [['x', '1']], delimiter))
    else:
        raise ValueError('Unsupported input semantic vocabulary')
    # Deduplicate without hashing or process-dependent ordering.
    unique = {}
    for t in tests: unique.setdefault(json.dumps(t, sort_keys=True), t)
    return list(unique.values())
