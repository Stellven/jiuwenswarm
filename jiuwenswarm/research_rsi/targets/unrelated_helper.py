"""Independent fixture target for same-engine interoperability, not Target 2.

No existing capsule mutation grant is widened. Admission and authority for an
actual unrelated parent remain external to this data-only adapter.
"""


def normalize_labels(labels):
    """Canonical set of nonempty labels with whitespace/case normalization."""
    if not isinstance(labels, list) or any(not isinstance(label, str) for label in labels):
        raise ValueError('Labels must be a list of strings')
    normalized = set()
    for label in labels:
        value = ' '.join(label.split()).casefold()
        if value:
            normalized.add(value)
    return {'labels': sorted(normalized)}


NORMALIZE_LABELS_PARENT = b'''def normalize_labels(labels):
    if not isinstance(labels, list) or any(not isinstance(label, str) for label in labels):
        raise ValueError('Labels must be a list of strings')
    normalized = set()
    for label in labels:
        value = ' '.join(label.split()).casefold()
        if value:
            normalized.add(value)
    return {'labels': sorted(normalized)}
'''


def validate_adapter(profile):
    if not profile.get('required_test_refs') or not profile.get('parent_ref'):raise ValueError('independently admitted helper/test pins required')
    return profile


def preparation_case(rng, count, mode):
    """Private generated units exercise every fixed normalization operation."""
    token = rng.getrandbits(128).to_bytes(16, 'big').hex()
    return {'labels': ['  Z ' + token + '  ', 'A\t' + token, 'a ' + token,
                       '', '   ', 'Straße ' + token, 'x  y ' + token]}


def preparation_expected(value):
    # Data-only independent formulation; never execute a proposed source body.
    return {'labels': sorted(set(filter(None, (' '.join(label.split()).casefold()
                                              for label in value['labels']))))}


def preparation_fingerprints(value):
    from ..records import encoded
    import hashlib
    digest = lambda data: hashlib.sha256(encoded(data)).hexdigest()
    return {'input_sha256': digest(value),
            'semantic_sha256': digest(preparation_expected(value))}


def preparation_children(parent_bytes):
    """Ten actual semantic faults and three distinct preservation sources."""
    if parent_bytes != NORMALIZE_LABELS_PARENT:
        raise ValueError('Exact independently reviewed normalization parent required')
    source = parent_bytes.decode()
    faults = {
        'omit_casefold': (".casefold()", ""),
        'upper': (".casefold()", ".upper()"),
        'lower_only': (".casefold()", ".lower()"),
        'strip_only': ("' '.join(label.split())", "label.strip()"),
        'keep_whitespace': ("' '.join(label.split())", "label"),
        'keep_empty': ('if value:', 'if True:'),
        'descending': ('sorted(normalized)', 'sorted(normalized, reverse=True)'),
        'omit_last': ('sorted(normalized)', 'sorted(normalized)[:-1]'),
        'omit_first': ('sorted(normalized)', 'sorted(normalized)[1:]'),
        'empty_result': ('sorted(normalized)', '[]'),
    }
    rows = []
    for name, (before, after) in faults.items():
        if source.count(before) != 1: raise ValueError('Fixed normalization adapter changed')
        rows.append({'id': name, 'kind': 'bad', 'body': source.replace(before, after).encode()})
    for name, before, after in (
        ('generator_split', "' '.join(label.split())", "' '.join(part for part in label.split())"),
        ('explicit_sorted', 'sorted(normalized)', 'list(sorted(normalized))'),
        ('set_union', 'normalized.add(value)', 'normalized |= {value}'),
    ):
        rows.append({'id': name, 'kind': 'good', 'body': source.replace(before, after).encode()})
    if len({row['body'] for row in rows}) != 13: raise ValueError('Distinct fixed controls required')
    return rows
