from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]
items=json.loads((root/'MANIFEST.json').read_text())['files']
for item in items:
 p=root/item['path']; h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 assert h.hexdigest()==item['sha256'],str(p)
print(f"Verified {len(items)} files")
