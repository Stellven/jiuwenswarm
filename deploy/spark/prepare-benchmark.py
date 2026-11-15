"""Fetch/hash public ARC data and prepare exact model-tokenized benchmark inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jiuwenswarm.factory.benchmark_data import prepare
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('/home/user2/software-factory-spark-20261113'))
p.add_argument('--output',type=Path);a=p.parse_args()
output=a.output or a.root/'benchmark-data/arc-v1/dataset.json'
if output.suffix != '.json':
    output=output/'dataset.json'
value=prepare(a.root,output)
print(json.dumps(dict(output=str(output),sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
 quality_cases=len(value['quality']),pilot_cases=len(value['pilot']),speed_cases=len(value['speed']),
 revision=value['provenance']['dataset_revision'],license=value['provenance']['license'])))
