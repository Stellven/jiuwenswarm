from pathlib import Path
import json,hashlib,zipfile,subprocess,shutil,urllib.parse
from html.parser import HTMLParser
P=Path('/home/muk/backup/20261113 Satay CC Demo and Recovery prepresentation')
J=Path('/home/muk/projects/jiuwenswarm')
for name in ['builder','lab_client','methodology_ab','expert_streaming']:
    shutil.copy2(J/'jiuwenswarm/factory/ccs'/name/'cc.yaml',P/'context/capsules'/f'{name}.yaml')
(P/'REPLAY.md').write_text('''# 20261113 Recorded Demo Replay prepresentation

Open the package console, select Replay and play at normal speed. The existing film is 406.03 seconds at 1920x1080. It already compresses long waits and labels that compression. The talk allows 193.97 seconds around it, for ten minutes total.

On Linux, from this extracted package, replay raw terminal recordings without a model or factory:

```sh
cd evidence/incremental/recording
for n in 1 2 3; do
  scriptreplay -t "seg$n.timing" "seg$n.typescript" -d 20
done
```

Use -d 1 for original timing. No live job is submitted. Current startup instructions are in context/recovery; the original LAUNCH-REPLAY.md beside the recordings is historical and contains superseded startup prerequisites.

This is the 32-token fill-only task, whose outcome was inconclusive. The historical 64-token J-OM13 performance result has a separate report and specification. Raw recordings and measured results were not altered.
''')
console=P/'20261113 Satay CC Demo Console prepresentation.html'
console.write_text(console.read_text().replace('href="evidence/incremental/LAUNCH-REPLAY.md"','href="REPLAY.md"'))
class Links(HTMLParser):
    def handle_starttag(self,tag,attrs):
        for k,v in attrs:
            if k in ('href','src') and v and not v.startswith(('#','http:','https:','data:')):
                assert (P/urllib.parse.unquote(v)).exists(),v
Links().feed(console.read_text())
assert 'Run 5' not in console.read_text()
pins=json.loads((P/'SOURCE-PINS.json').read_text())
for name,item in pins.items():
    restored=Path('/home/muk/backup/restore-check-20261113')/name
    actual=subprocess.check_output(['git','-C',str(restored),'rev-parse','HEAD'],text=True).strip()
    assert actual==item['commit'],(name,actual)
    subprocess.run(['git','-C',str(restored),'fsck','--full'],check=True,stdout=subprocess.DEVNULL)
engine=Path('/home/muk/backup/restore-check-20261113/llama-engine')
for name in ['plain','fill','headline']:
    subprocess.run(['git','-C',str(engine),'cat-file','-e','refs/heads/recovery/'+name+'-20261113^{tree}'],check=True)
(P/'VALIDATION.md').write_text('''# 20261113 Package Validation prepresentation

## Completed

- 41 focused factory/ontology tests passed. Existing task compatibility and invalid-slice rejection covered.
- 17 isolated queue tests passed: worker interruption without duplicate execution, dead runners, reboot identity and clock jumps.
- 2 checkpoint tests passed. A private SQLite snapshot was validated on internal storage; it is excluded from this package.
- Production queue was idle for its controlled worker interruption. systemd restarted it. Service enabled/active and Linger=yes. No model job submitted.
- Four repository snapshots restored separately using only local bundles plus shallow boundaries. Pinned HEADs matched and git fsck passed. Plain/fill/headline engine trees are present.
- Original video and all six raw terminal files matched published hashes. All three scriptreplay sessions completed in accelerated verification mode.
- Video decoded successfully for frame sampling: H.264, 1920x1080, 406.03 seconds. Six representative frames visually reviewed. Real-time decode result is appended below.
- Console links resolve in the package. Python helpers and shell syntax checked; launch script uses Linux LF endings.
- Four independent text reviews completed and fixes applied (REVIEW.md). Selected-text/gzip credential-pattern scan found no hits; this is not an exhaustive Git-object security audit.
- No inference runs, hardware builds, Danta writes, physical reboot or published-tag changes performed for this package.

## Limits

Browser policy rejected the local-file preview. No alternate browser workaround was used. The new HTML console has static/link review, not interactive rendered-browser sign-off. Check display scaling/fullscreen locally before presenting.

The sequence allows a verified 406.03-second video plus 193.97-second narration. This is not a completed human spoken rehearsal. Hardware power-loss and unattended physical reboot were not tested; service configuration and process restart were tested.

Dependencies not bundled: Qwen weights (contract path/size, no model content hash), JetPack/CUDA, Docker/base images, Python environments, authenticated Codex and engine images. Bundles preserve exact pins but omit parent history beyond shallow boundaries. This is not a bare-metal recovery image.

## Versions and build inspection

Observed Codex CLI 0.167.0 and Docker server 29.1.3. Factory's separately pinned Codex transport was not upgraded. Current engine.expert_streaming 2.0.1 / ontology 0.2 postdates recorded execution. cc-rsi-v1 remains f8ff8d1f05535ee2f1175ec67a0d0c89139fd63f.

Build path already uses native CMake/Ninja with persistent ccache for C/C++/CUDA, then runtime-image assembly. No build-speed change or claim made. Cumulative cache hit rate 87.45% is not a measured demo speedup.
''')
if (P/'MEDIA-CHECK.json').exists():
    with (P/'VALIDATION.md').open('a') as f:f.write('\nReal-time media check: '+(P/'MEDIA-CHECK.json').read_text()+'\n')
files=[]
for f in sorted(P.rglob('*')):
    if not f.is_file() or f.name=='MANIFEST.json':continue
    assert f.suffix!='.lock',str(f)
    h=hashlib.sha256()
    with f.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    files.append({'path':str(f.relative_to(P)),'bytes':f.stat().st_size,'sha256':h.hexdigest()})
manifest={'schema':'satay.demo.recovery/1','source_pins':'SOURCE-PINS.json','history':'shallow snapshots with original commit identities','included':['source bundles and boundary sidecars','selected raw evidence','recorded video/terminal sessions','contracts and prompt files','guides and launch/recovery helpers'],'installed_not_bundled':['model weights','CUDA/JetPack','Docker and base images','Python environments','authenticated Codex','engine Docker images'],'excluded':['live factory database','credentials and authentication directories','model weights','image tarballs'],'files':files}
(P/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
subprocess.run(['python3',str(P/'scripts/verify.py')],check=True)
out=P.with_suffix('.zip')
with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=2) as z:
    for f in P.rglob('*'):
        if f.is_file():z.write(f,str(Path(P.name)/f.relative_to(P)))
h=hashlib.sha256()
with out.open('rb') as stream:
    for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
out.with_suffix('.sha256').write_text(h.hexdigest()+'  '+out.name+'\n')
print(json.dumps({'zip':str(out),'bytes':out.stat().st_size,'sha256':h.hexdigest(),'files':len(files)}),flush=True)
