"""Run the installed import graph checker; mutations stay in disposable copies."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import jiuwenswarm

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="module")
def graph_copy(tmp_path_factory):
    tool = shutil.which("lint-imports")
    assert tool, "BLOCKED: the frozen verification image must contain import-linter"
    config = ROOT / ".importlinter"
    assert config.is_file(), "BLOCKED: the actual import contract must be mounted read-only"
    root = tmp_path_factory.mktemp("actual-import-graph")
    def python_sources(directory, names):
        # Import-linter parses Python. UI bundles, bytecode and packaged data
        # are not graph inputs and must not make the disposable copy unbounded.
        return [name for name in names if name in {"__pycache__", "node_modules", ".git", ".venv", "frontend"}
                or not (Path(directory) / name).is_dir() and not name.endswith(".py")]
    shutil.copytree(Path(jiuwenswarm.__file__).resolve().parent, root / "jiuwenswarm", ignore=python_sources)
    shutil.copyfile(config, root / ".importlinter")
    return root, tool


def lint(graph_copy):
    root, tool = graph_copy
    environment = {**os.environ, "PYTHONPATH": str(root)}
    return subprocess.run([tool, "--config", str(root / ".importlinter"), "--no-cache"],
                          cwd=root, env=environment, capture_output=True, text=True, timeout=120)


def test_current_protected_import_graph(graph_copy):
    result = lint(graph_copy)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("relative,target", [
    ("gateway/channel_manager/web/research_http.py", "research_router"),
    ("research/executor.py", "research_rsi"),
    ("research/capsules/screening.py", "research_sidecar"),
    ("research/router_client.py", "research_records"),
])
def test_real_graph_rejects_each_planted_hot_path_import(graph_copy, relative, target):
    root, _ = graph_copy
    path = root / "jiuwenswarm" / relative
    original = path.read_bytes()
    try:
        path.write_bytes(original + f"\nimport jiuwenswarm.{target}\n".encode())
        result = lint(graph_copy)
        assert result.returncode != 0
        assert target in result.stdout + result.stderr
        assert "Hot path imports no side system" in result.stdout + result.stderr
    finally:
        path.write_bytes(original)


def test_real_graph_rejects_transitive_hot_path_import(graph_copy):
    root, _ = graph_copy
    source = root / "jiuwenswarm/research/executor.py"
    intermediary = root / "jiuwenswarm/research_boundary_probe.py"
    original = source.read_bytes()
    try:
        source.write_bytes(original + b"\nimport jiuwenswarm.research_boundary_probe\n")
        intermediary.write_text("import jiuwenswarm.research_router\n", encoding="utf-8")
        result = lint(graph_copy)
        assert result.returncode != 0
        assert "research_boundary_probe" in result.stdout + result.stderr
        assert "research_router" in result.stdout + result.stderr
    finally:
        source.write_bytes(original)
        intermediary.unlink(missing_ok=True)
