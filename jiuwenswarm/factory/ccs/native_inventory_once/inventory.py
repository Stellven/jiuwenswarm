"""Equivalent fresh metadata snapshot; deliberately no cross-call cache."""
def repeated_metadata_reads(distributions):
    """Baseline from Host.call, retained as an explicit comparison."""
    return sorted([d.metadata['Name'], d.version] for d in distributions() if d.metadata['Name'])

def fresh_inventory(distributions):
    """Read each distribution's metadata once during this invocation."""
    inventory = []
    for distribution in distributions():
        metadata = distribution.metadata
        name = metadata['Name']
        if name:
            inventory.append([name, metadata['Version']])
    return sorted(inventory)
