"""Package the amended native snapshot and verify the delivered archive in a fresh directory."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile
from jiuwenswarm.factory.export import verify

root=Path(__file__).resolve().parents[2]
dst=root/'jiuwenswarm/ops/spark/demo-20261120'
pub=json.loads((root/'OPS/final-publication.json').read_bytes())
bundle=Path(pub['export'])
assert 'previous_manifest_sha256' in pub
archive=dst/(bundle.name+'.tar.zst')
with tempfile.TemporaryDirectory(dir=dst) as temporary:
    tmp=Path(temporary)
    out=tmp/archive.name
    subprocess.run(['tar','--zstd','-cf',str(out),'-C',str(bundle.parent),bundle.name],check=True)
    subprocess.run(['tar','--zstd','-xf',str(out),'-C',str(tmp)],check=True)
    expanded=tmp/bundle.name
    count=verify(expanded)
    manifest=hashlib.sha256((expanded/'MANIFEST.json').read_bytes()).hexdigest()
    assert count==pub['verified_manifest_files'] and manifest==pub['manifest_sha256']
    citation=json.loads((expanded/'citation-map.json').read_bytes())['direct_local_citations']
    assert all(hashlib.sha256((expanded/ref['exported_path']).read_bytes()).hexdigest()==ref['exported_sha256'] for ref in citation)
    receipt=dict(schema='spark-delivery-archive/1',archive=archive.name,bytes=out.stat().st_size,
                 sha256=hashlib.sha256(out.read_bytes()).hexdigest(),unpacked_manifest_sha256=manifest,
                 verified_manifest_files=count,source_report_sha256=pub['source_report_sha256'],
                 direct_citations=pub['citation_count'],verified_report_links=pub['verified_link_targets'])
    out.replace(archive)
(root/'OPS/final-archive-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
files={Path(ref['source_path']) for ref in citation}
files.update(Path(s) for s in ('report.md','OPS/DECISIONS.md','OPS/STATUS.md','OPS/LEDGER.jsonl',
    'OPS/final-archive-verification.json','OPS/final-publication.json','OPS/p4/cache60-quiet-native-publication.json',
    'OPS/p4/observe-quiet-control.py','OPS/p4/refresh-quiet60-publication.py','OPS/p4/publish-quiet60-control.sh',
    'OPS/p4/package-quiet60.py','OPS/p3/rehearse-final-ui.py',
    'OPS/iterations/spark-p4-cache60-build-overlap/iteration-v3.json',
    'OPS/iterations/spark-p4-cache60-build-overlap/analysis-v3.json',
    'OPS/runs/p4-cache60-aplus-pass-2-quiet-01/host-activity.jsonl'))
files.update(p.relative_to(root) for p in (root/'OPS/ui-shots/quiet60-v3').glob('*') if p.is_file())
for path in sorted(files):
    (dst/path.parent).mkdir(parents=True,exist_ok=True)
    shutil.copy2(root/path,dst/path)
readme=dst/'README.md'
import re
text=readme.read_text()
text=re.sub(r'contains [\d,]+ manifest-verified files',f'contains {count:,} manifest-verified files',text)
text=re.sub(r'all [\d,]+ links in the readable report',f"all {pub['verified_link_targets']} links in the readable report",text)
readme.write_text(text)
print(json.dumps(receipt,indent=2))
