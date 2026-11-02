"""V-BLK-IMPORT (AC-019): no AI4R import under labs/physicalai_sim; a planted one is caught."""
import shutil
import subprocess
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[2]
TOOL = LAB / "tools" / "import_check.py"


def test_real_tree_has_no_ai4r_import():
    r = subprocess.run([sys.executable, str(TOOL), "--root", str(LAB), "--json"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


def test_planted_import_fails(tmp_path):
    root = tmp_path / "lab"
    (root / "src" / "simlab").mkdir(parents=True)
    (root / "src" / "simlab" / "ok.py").write_text("import json\n")
    (root / "src" / "simlab" / "bad.py").write_text("from jiuwenswarm.research import contracts\n")
    (root / "src" / "simlab" / "bad2.py").write_text("import importlib\nimportlib.import_module('jiuwenswarm.server')\n")
    r = subprocess.run([sys.executable, str(TOOL), "--root", str(root), "--repo", str(tmp_path), "--json"], capture_output=True, text=True)
    assert r.returncode == 1
    assert "bad.py" in r.stdout and "bad2.py" in r.stdout and "ok.py" not in r.stdout.split("violations")[1]
