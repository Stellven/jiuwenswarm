import asyncio
from pathlib import Path
from types import SimpleNamespace
import pytest
from jiuwenswarm.research.isolated_resources import build_isolated_resources
from jiuwenswarm.research.contracts import ResearchError


def test_isolated_factory_refuses_live_or_shared_credential_root_before_composition(tmp_path):
    isolation=tmp_path/'isolated';isolation.mkdir();live=tmp_path/'live';live.mkdir()
    with pytest.raises(ResearchError,match='isolation'):
        asyncio.run(build_isolated_resources(store=SimpleNamespace(root=isolation,blobs=SimpleNamespace(root=isolation/'blobs'),db_path=isolation/'db',input_root=isolation/'inputs'),
            operator=None,own_subscription_service=SimpleNamespace(root=live),own_executor=SimpleNamespace(workspace_root=isolation/'work'),
            principal=None,exact_binding_refs={},isolation_root=isolation,forbidden_roots=[live],readiness=None))


def test_core_factory_never_imports_side_implementation():
    import ast
    import inspect
    import jiuwenswarm.research.isolated_resources as module
    tree=ast.parse(inspect.getsource(module))
    names=[n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    assert not any('research_rsi' in n or 'research_sidecar' in n or 'research_router' in n for n in names)
