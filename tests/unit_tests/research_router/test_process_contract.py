import ast
from pathlib import Path

from jiuwenswarm.research_router.service import PROTOCOL, MAX_FRAME_BYTES


def test_process_is_selection_only_and_has_no_hotpath_imports():
    package = Path(__file__).parents[3] / "jiuwenswarm/research_router"
    for file in package.glob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("jiuwenswarm.research.")
    assert PROTOCOL == "ai4r-router-ipc:1"
    assert MAX_FRAME_BYTES == 4 * 1024 * 1024

