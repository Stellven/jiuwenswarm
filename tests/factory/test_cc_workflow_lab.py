"""The capsule's invariants run without external resources or GPU."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

BUNDLE = Path(__file__).resolve().parents[2]/'jiuwenswarm/factory/ccs/cc_workflow_lab'

def test_cpu_invariants():
    spec = importlib.util.spec_from_file_location('cc_workflow_test', BUNDLE/'workflow.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.analyze_receipts(module.fixture())['call_count'] == 24
    result = subprocess.run([sys.executable,str(BUNDLE/'verification.py')],capture_output=True,text=True,check=True)
    assert "'passed': True" in result.stdout

def test_native_batch_rejects_external_operation():
    packet = {'capability':'run_batch','inputs':{'spec':{'jobs':[{'operation':'exec','spec':{}}]}}}
    result = subprocess.run([sys.executable,str(BUNDLE/'run.py')],input=json.dumps(packet),capture_output=True,text=True,check=True)
    response = json.loads(result.stdout)
    assert response['outcome'] == 'error'
    assert response['error']['code'] == 'INVALID_WORKFLOW_INPUT'

def test_native_packet_and_batch_bounds():
    cases = [
        {'capability':'run_batch','inputs':{'spec':{'jobs':[]}}},
        {'capability':'run_batch','inputs':{'spec':{'jobs':[{'operation':'benchmark_fixture','spec':{}}]*17}}},
        {'capability':'benchmark_fixture','inputs':{'spec':[]}},
    ]
    for packet in cases:
        result = subprocess.run([sys.executable,str(BUNDLE/'run.py')],input=json.dumps(packet),capture_output=True,text=True,check=True)
        assert json.loads(result.stdout)['outcome'] == 'error'
    result = subprocess.run([sys.executable,str(BUNDLE/'run.py')],input=' '*1048577,capture_output=True,text=True,check=True)
    assert json.loads(result.stdout)['error']['message'] == 'packet exceeds 1 MiB bound'
