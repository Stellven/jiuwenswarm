"""Read-only live acceptance preflight. Presence never substitutes for service qualification."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))


def probe():
    from jiuwenswarm.research.native import OPENJIUWEN_COMMIT,verify_native_pin
    reasons=[]
    try:
        verify_native_pin()
        native='pinned_distribution_verified'
    except Exception as exc:
        native=getattr(exc,'code',type(exc).__name__)
        reasons.append(native)
    endpoints={}
    for key,path in {'model':'/run/ai4r/model.sock','executor':'/run/ai4r-executor/executor.sock'}.items():
        target=Path(path)
        present=target.exists() and stat.S_ISSOCK(target.lstat().st_mode) and not target.is_symlink()
        endpoints[key]={'path':path,'socket_present':present,'qualified':False}
        if not present:reasons.append(key+'_service_unavailable')
    if not shutil.which('bwrap'):reasons.append('bubblewrap_unavailable')
    if os.name!='posix' or not hasattr(os,'geteuid') or os.geteuid()!=0:reasons.append('protected_linux_root_required')
    return {'schema':'ai4r-agentic-builder-live-preflight:1','sdk_commit':OPENJIUWEN_COMMIT,
        'native_runtime':native,'bubblewrap_available':bool(shutil.which('bwrap')),
        'cgroup_v2_present':Path('/sys/fs/cgroup/cgroup.controllers').is_file(),
        'service_endpoints':endpoints,'status':'blocked' if reasons else 'service_qualification_required',
        'reasons':reasons,'authenticated_build_performed':False,'benchmark_performed':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    raw=json.dumps(probe(),indent=2)+'\n'
    if args.output:args.output.write_text(raw,encoding='utf-8')
    print(raw,end='')


if __name__=='__main__':main()
