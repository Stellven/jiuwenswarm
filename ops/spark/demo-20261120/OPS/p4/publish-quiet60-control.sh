#!/usr/bin/env bash
set -eu -o pipefail
cd "$HOME/predemo-spark"
scope=OPS/runs/p4-cache60-aplus-pass-2-quiet-01
test -s "$scope/probe.json"
jq -e '.scope_verified and .returncode == 0 and .reason == null' "$scope/result.json" >/dev/null
export PYTHONPATH="$PWD/jiuwenswarm"
py=jiuwenswarm/.venv/bin/python
ops=jiuwenswarm/ops/spark
"$py" "$ops/report_p4.py" OPS/p4/cache-abba-60g.json \
  --manifest-sha256 e40a0a7364f78c9ca2558453b1438ffe1279bf7a834f9d3960a1c71e42305695 \
  --scope-amendment OPS/p4/cache-abba-60g-amendment.json \
  --scope-amendment-sha256 0b46d00a66a8de1eb50e6f9bee7b0225339584ad19ce8d69e0e6ee444cfb0e22 \
  --control-amendment OPS/p4/cache-abba-60g-quiet-control-amendment.json \
  --control-amendment-sha256 6275879ba0bf5aed1e9e6831d3ba2cba70d09f0af87bad98ffc1eb7c84f9f904 \
  >OPS/p4/cache60-quiet-native-publication.json
"$py" "$ops/final_headlines.py"
"$py" OPS/p4/refresh-quiet60-publication.py
"$py" OPS/p3/verify-final-campaign.py > OPS/final-campaign-verification.json.tmp
mv OPS/final-campaign-verification.json.tmp OPS/final-campaign-verification.json
"$py" "$ops/publish_report.py" --status final --out "$PWD/factory-runs/exports/.quiet60-new" >OPS/p4/cache60-quiet-snapshot.json
"$py" - <<'PY'
import ctypes,hashlib,json,os
from pathlib import Path
base=Path.cwd()
previous=json.loads((base/'OPS/final-publication.json').read_bytes())
fresh=json.loads((base/'OPS/p4/cache60-quiet-snapshot.json').read_bytes())
old,new=Path(previous['export']),Path(fresh['export'])
def manifest(p): return hashlib.sha256((p/'MANIFEST.json').read_bytes()).hexdigest()
assert manifest(old)==previous['manifest_sha256'] and manifest(new)==fresh['manifest_sha256']
assert old.parent==new.parent
backup=base/'receipts'/('frozen-snapshot-'+previous['publication_id'])
assert not backup.exists()
lib=ctypes.CDLL(None,use_errno=True)
if lib.renameat2(-100,os.fsencode(old),-100,os.fsencode(new),2):
    raise OSError(ctypes.get_errno(),'Atomic snapshot exchange failed')
new.rename(backup)
fresh.update(export=str(old),previous_manifest_sha256=previous['manifest_sha256'],archived_snapshot=str(backup))
tmp=base/'OPS/final-publication.json.tmp'
tmp.write_text(json.dumps(fresh,indent=2)+'\n')
tmp.replace(base/'OPS/final-publication.json')
PY
