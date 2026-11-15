"""Build native role images offline from existing approved local dependencies."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True, help='new owned build-context directory')
    p.add_argument('--agent-python', type=Path, required=True)
    p.add_argument('--cmake-data', type=Path, required=True)
    p.add_argument('--ninja', type=Path, required=True)
    p.add_argument('--tag-suffix', default='cc-dgx-spark-001')
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('A new context directory is required')
    base = 'ghcr.io/ggml-org/llama.cpp@sha256:695214dcb4d4062014335702caee98836bbf92c5974b78331c70e152176cbf08'
    info = json.loads(subprocess.check_output(['docker', 'image', 'inspect', base]))[0]
    if info['Architecture'] != 'arm64':
        raise ValueError('Existing pinned native ARM64 base is required; never pull implicitly')
    a.output.mkdir(parents=True)
    here = Path(__file__).resolve().parent
    commands = {
        'agent': [str(a.agent_python), str(here/'package-agent.py'), '--output', str(a.output/'agent')],
        'builder': [sys.executable, str(here/'package-builder.py'), '--output', str(a.output/'builder'),
                    '--cmake-data', str(a.cmake_data), '--ninja', str(a.ninja)]}
    receipts = {}
    for role, argv in commands.items():
        with (a.output/(role+'-package.log')).open('w') as stream:
            subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT, check=True)
        tag = 'factory/'+role+':'+a.tag_suffix
        with (a.output/(role+'-build.log')).open('w') as stream:
            subprocess.run(['docker','build','--network=none','--pull=false','-t',tag,str(a.output/role)],
                           stdout=stream, stderr=subprocess.STDOUT, check=True)
        built = json.loads(subprocess.check_output(['docker','image','inspect',tag]))[0]
        manifest = a.output/role/('closure.json' if role=='agent' else 'toolchain.json')
        receipts[role] = dict(tag=tag, image_id=built['Id'], architecture=built['Architecture'],
                              manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                              manifest_path=str(manifest))
    (a.output/'roles.json').write_text(json.dumps(receipts,indent=2)+'\n')
    print(json.dumps(receipts))


if __name__ == '__main__':
    main()
