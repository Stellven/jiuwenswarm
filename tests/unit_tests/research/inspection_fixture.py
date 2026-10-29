"""I032 independent observations; controlled replies never qualify services."""
import hashlib
import importlib
import importlib.util


def readonly_snapshot(store):
    files = []
    for root in (store.blobs.root, store.root / 'records'):
        if root.exists():
            files.extend((str(p.relative_to(store.root)), hashlib.sha256(p.read_bytes()).hexdigest())
                         for p in root.rglob('*') if p.is_file())
    return tuple(store.connection.iterdump()), store.connection.total_changes, tuple(sorted(files))


def inspect_private(store, binding, **kwargs):
    from jiuwenswarm.research import evaluation_authority
    helper = getattr(evaluation_authority, 'inspect_evaluation_executor_binding', None)
    assert callable(helper), 'UNBUILT private proof10; genuine fixture already prepared'
    before = readonly_snapshot(store)
    try:
        return helper(store, binding, **kwargs)
    finally:
        assert readonly_snapshot(store) == before, 'Private inspector mutated authoritative state/files'


def inspect_ordinary(store, request):
    module = 'jiuwenswarm.research.attempt_inspection'
    assert importlib.util.find_spec(module) is not None, 'UNBUILT ordinary proof9; genuine canonical fixture already prepared'
    helper = getattr(importlib.import_module(module), 'inspect_node_attempt', None)
    assert callable(helper), 'UNBUILT ordinary proof9 function'
    before = readonly_snapshot(store)
    try:
        return helper(store, request)
    finally:
        assert readonly_snapshot(store) == before, 'Ordinary inspector mutated authoritative state/files'
