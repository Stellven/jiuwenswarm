import json
from pathlib import Path
import sys

json.load(sys.stdin)
root = Path(__file__).resolve().parent
build = root / 'build-record.json'
record = json.loads(build.read_text(encoding='utf-8')) if build.is_file() else {}
print(json.dumps({'outcome': 'ok', 'outputs': {'report': {'application': 'api', 'contract': 'api.json',
                                                         'source_tree': record.get('observed_tree'),
                                                         'fixture': True}}}))
