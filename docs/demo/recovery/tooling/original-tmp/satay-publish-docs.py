from pathlib import Path
import shutil,subprocess
P=Path('/home/muk/backup/20261113 Satay CC Demo and Recovery prepresentation')
J=Path('/home/muk/projects/jiuwenswarm'); D=J/'docs/demo/recovery'; D.mkdir(exist_ok=True)
for f in list(P.iterdir())+list((P/'scripts').iterdir()):
    if f.is_file() and f.suffix in ['.md','.html','.py','.sh']:
        f.write_text(f.read_text(),newline='\n')
for f in P.iterdir():
    if f.suffix in ['.md','.html']:shutil.copy2(f,D/f.name)
shutil.copytree(P/'scripts',D/'scripts',dirs_exist_ok=True)
(D/'PACKAGE.md').write_text('''# 20261113 Recovery Package Sources prepresentation

These files are the authored console, guides and launch helpers for the assembled Satay recovery package. The console's relative evidence/context links resolve inside the assembled package, not this source-only directory. Sources and selected raw evidence are packaged separately to avoid committing large duplicate bundles. Runtime data and authentication are excluded.

The original demo video remains at artifacts/factory/demo-incremental/demo-final.mp4. J-OM13 raw evidence remains in siminfeng. The recoverable ZIP is under /home/muk/backup and copied to the operator Downloads directory. Package checksums and SOURCE-PINS.json are generated after source commits are finalized. Do not move published tags.

Service setup now has Linger=yes; process restart was tested, physical reboot was not. The package includes exact source snapshots with .shallow boundary sidecars, not full repository history.
''')
subprocess.run(['git','-C',str(J),'add','docs/demo/recovery'],check=True)
subprocess.run(['git','-C',str(J),'diff','--cached','--check'],check=True)
subprocess.run(['git','-C',str(J),'commit','-m','demo: package portable Satay story and recovery instructions'],check=True)
subprocess.run(['git','-C',str(J),'push','git@github.com:Stellven/jiuwenswarm.git','HEAD:refs/heads/cc-siminfeng'],check=True)
