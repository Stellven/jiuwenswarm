"""Issue a fresh 24 hour runner grant through the running app and store it in the runner credential volume.

Mirrors deploy/m1/operator_host.issue_credential. The token moves only through pipes in memory.
It is never printed, logged or written outside the credential volume, and this file holds no
credential value.

Run it after `initialize` and again once the app answers (the first grant right after a
restart can return 401 or 502; a second refresh works).

Environment:
  AI4R_APP_CONTAINER      running app container name (default: ai4r-local-ai4r-1)
  AI4R_BOOTSTRAP_SESSION  path, inside the app container, of the reusable bootstrap session file
                          (default: /var/lib/ai4r-accounts/sessions/reusable-bootstrap.json)
  AI4R_RUNNER_VOLUME      runner credential volume (default: ai4r-local_runner_credentials)
"""
import argparse
import json
import os
import subprocess
import sys

UID = GID = 11001

ISSUE = '''import json,os,sys,time
from pathlib import Path
from jiuwenswarm.research.evaluation_grants import open_operator_authority
root=Path('/run/ai4r-supervisor')
p=json.loads(Path(os.environ['AI4R_BOOTSTRAP_SESSION']).read_bytes())['principal']
if isinstance(p,str):p=json.loads(p)
assert len(p['workspace_ids'])==1
target=root/('runner-'+str(time.time_ns()))
a=open_operator_authority()
try:
 result=a.issue_runner({'schema':'ai4r-runner-grant:1','account_id':p['account_id'],'workspace_id':p['workspace_ids'][0],'expires_in_s':86400},str(target))
 assert result['status']=='issued'
 print(json.dumps({'token':target.read_text(),'grant':result}))
finally:
 a.close();target.unlink(missing_ok=True)
'''

WRITER = '''import json,os,sys,uuid
from pathlib import Path
p=json.load(sys.stdin);root=Path('/operator');root.chmod(0o755)
t=root/('.token-'+uuid.uuid4().hex)
try:
 fd=os.open(t,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,'wb') as f:
  f.write(p['token'].encode());f.flush();os.fsync(f.fileno());os.fchown(f.fileno(),p['uid'],p['gid'])
 os.replace(t,root/'token')
 fd=os.open(root,os.O_RDONLY);os.fsync(fd);os.close(fd)
finally:t.unlink(missing_ok=True)
'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--image-tag', required=True, help='image used for the credential writer container')
    args = parser.parse_args(argv)
    app = os.environ.get('AI4R_APP_CONTAINER', 'ai4r-local-ai4r-1')
    session = os.environ.get('AI4R_BOOTSTRAP_SESSION', '/var/lib/ai4r-accounts/sessions/reusable-bootstrap.json')
    volume = os.environ.get('AI4R_RUNNER_VOLUME', 'ai4r-local_runner_credentials')
    first = subprocess.run(["docker", "exec", "-i", "--user", "0:0", "-e", "AI4R_BOOTSTRAP_SESSION=" + session,
                            app, "/opt/venv/bin/python", "-c", ISSUE],
                           capture_output=True, text=True, timeout=120)
    if first.returncode:
        print("issue failed:", first.stderr.strip().splitlines()[-1:] or first.returncode)
        return 1
    response = json.loads(first.stdout)
    second = subprocess.run(
        ["docker", "run", "--rm", "-i", "--network", "none", "--read-only", "--user", "0:0",
         "--cap-drop", "ALL", "--cap-add", "CHOWN", "--cap-add", "DAC_OVERRIDE", "--cap-add", "FOWNER",
         "--security-opt", "no-new-privileges", "--mount", f"type=volume,src={volume},dst=/operator",
         "--entrypoint", "/opt/venv/bin/python", args.image_tag, "-c", WRITER],
        input=json.dumps({"token": response["token"], "uid": UID, "gid": GID}),
        capture_output=True, text=True, timeout=120)
    if second.returncode:
        print("write failed:", second.stderr.strip().splitlines()[-1:] or second.returncode)
        return 1
    print(json.dumps({k: v for k, v in response["grant"].items() if k != "token"}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
