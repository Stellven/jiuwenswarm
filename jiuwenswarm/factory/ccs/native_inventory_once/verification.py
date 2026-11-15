"""Equivalence, read-count and mutation-negative checks, no external effects."""
from inventory import fresh_inventory, repeated_metadata_reads

class Distribution:
    def __init__(self, name, version):
        self.data = {'Name': name, 'Version': version}
        self.reads = 0
    @property
    def metadata(self):
        self.reads += 1
        return dict(self.data)
    @property
    def version(self):
        return self.metadata['Version']

def verify():
    values = [Distribution('zeta', '2'), Distribution('alpha', '1'),
              Distribution('alpha', '1'), Distribution(None, 'ignored'),
              Distribution('', 'ignored'), Distribution('missing-version', None)]
    snapshot = lambda: iter(values)
    old = repeated_metadata_reads(snapshot)
    baseline_reads = sum(d.reads for d in values)
    for distribution in values:
        distribution.reads = 0
    new = fresh_inventory(snapshot)
    optimized_reads = sum(d.reads for d in values)
    assert old == new == [['alpha', '1'], ['alpha', '1'], ['missing-version', None], ['zeta', '2']]
    assert baseline_reads == 14 and optimized_reads == 6
    # Negative control: a long-lived cache would miss this changed environment.
    values[0].data['Version'] = '3'
    assert fresh_inventory(snapshot)[-1] == ['zeta', '3']
    values.append(Distribution('added-after-first-call', '4'))
    assert ['added-after-first-call', '4'] in fresh_inventory(snapshot)
    values.pop(0)
    assert all(name != 'zeta' for name, _ in fresh_inventory(snapshot))
    return {'passed': True, 'baseline_metadata_reads': baseline_reads,
            'optimized_metadata_reads': optimized_reads, 'cache_used': False,
            'mutation_add_remove_negative_controls': True, 'cpu_only': True}

if __name__ == '__main__':
    print(verify())
