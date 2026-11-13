from pathlib import Path
import subprocess,json,sys,shutil
root=Path(__file__).resolve().parents[1]; dest=Path(sys.argv[1]).resolve()
if dest.exists() and any(dest.iterdir()):raise SystemExit('Destination must be empty')
dest.mkdir(parents=True,exist_ok=True)
for name,item in json.loads((root/'SOURCE-PINS.json').read_text()).items():
    target=dest/name
    subprocess.run(['git','init',str(target)],check=True,stdout=subprocess.DEVNULL)
    shutil.copy2(root/item['shallow'],target/'.git/shallow')
    refs=subprocess.check_output(['git','-C',str(target),'bundle','unbundle',str(root/item['bundle'])],text=True)
    for line in refs.splitlines():
        sha,ref=line.split()
        subprocess.run(['git','-C',str(target),'update-ref',ref,sha],check=True)
    subprocess.run(['git','-C',str(target),'checkout','--detach',item['commit']],check=True)
    subprocess.run(['git','-C',str(target),'fsck','--full'],check=True)
    got=subprocess.check_output(['git','-C',str(target),'rev-parse','HEAD'],text=True).strip()
    assert got==item['commit']
    print(name,got)
