"""Shared pytest fixtures. BOUNDARY tests use the real service over its Unix socket and real MuJoCo."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "tests"))


def pytest_addoption(parser):
    parser.addoption("--live", action="store_true", default=False, help="run live tests that need external services or models")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return
    skip = pytest.mark.skip(reason="live test: opt-in with --live (never passed with mocks)")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


def _data_root(tmp_path_factory, name: str) -> Path:
    root = os.environ.get("SIMLAB_TEST_DATA_ROOT")
    if root:
        p = Path(root) / f"{name}-{os.getpid()}-{time.monotonic_ns()}"
        p.mkdir(parents=True)
        return p
    return tmp_path_factory.mktemp(name)


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory, request):
    return _data_root(tmp_path_factory, request.module.__name__.rsplit(".", 1)[-1])


def start_service(data_dir: Path):
    env = {**os.environ, "SIMLAB_DATA_DIR": str(data_dir)}
    proc = subprocess.Popen([sys.executable, "-m", "simlab.interface.cli", "serve", "--data-dir", str(data_dir)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    sock = data_dir / "runner.sock"
    deadline = time.monotonic() + 30
    while not sock.exists():
        if proc.poll() is not None or time.monotonic() > deadline:
            raise RuntimeError("simlab serve did not start: " + (proc.stderr.read() if proc.stderr else ""))
        time.sleep(0.05)
    return proc


@pytest.fixture(scope="module")
def service(data_dir):
    from simlab.interface.client import Client

    proc = start_service(data_dir)
    try:
        yield Client(data_dir)
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture()
def store(tmp_path_factory, request):
    from simlab.store import Store

    return Store(_data_root(tmp_path_factory, "store-" + request.node.name[:40]))
