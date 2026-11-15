"""Pure CPU helper equivalence and freshness checks for an optional component."""
from pathlib import Path
import subprocess
import sys

BUNDLE = Path(__file__).resolve().parents[2]/'jiuwenswarm/factory/ccs/native_inventory_once'

def test_equivalence_and_freshness():
    result = subprocess.run([sys.executable,str(BUNDLE/'verification.py')],capture_output=True,text=True,check=True)
    assert "'passed': True" in result.stdout
    assert "'cache_used': False" in result.stdout
