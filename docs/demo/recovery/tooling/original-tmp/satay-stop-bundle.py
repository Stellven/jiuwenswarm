from pathlib import Path
import os,signal
target=41172
assert b'/tmp/satay-demo-bundle-20261113.py' in (Path('/proc')/str(target)/'cmdline').read_bytes()
parents={}
for d in Path('/proc').iterdir():
    if not d.name.isdigit():continue
    try:parents[int(d.name)]=int((d/'stat').read_text().rsplit(')',1)[1].split()[1])
    except (FileNotFoundError,ProcessLookupError):pass
desc=[target]
for pid in desc:
    desc.extend(p for p,pp in parents.items() if pp==pid and p not in desc)
for pid in reversed(desc):
    try:os.kill(pid,signal.SIGTERM)
    except ProcessLookupError:pass
print('Stopped owned full-history packaging process tree',desc)
