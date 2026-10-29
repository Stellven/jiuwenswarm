"""Pre-session read-only public reference capture with bounded pinned origins."""
import hashlib
import os
from pathlib import Path
from urllib.parse import urlsplit


def origin(url):
    p=urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.fragment:raise ValueError('credential-free HTTPS origin required')
    return p.scheme+'://'+p.netloc


def prepare(pin,destination,*,allowed_origins,fetch,max_bytes=4*1024*1024):
    if not pin.get('revision') or not pin.get('license') or origin(pin['url']) not in allowed_origins:raise ValueError('public reference approval incomplete')
    final,data=fetch(pin['url'])
    if origin(final) not in allowed_origins or not isinstance(data,bytes) or len(data)>max_bytes:raise ValueError('public reference redirect or size denied')
    digest=hashlib.sha256(data).hexdigest()
    if digest!=pin['sha256']:raise ValueError('public reference hash drift')
    path=Path(destination)
    if path.is_symlink():raise ValueError('reference destination symlink denied')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    path.chmod(0o444)
    return {'origin':origin(final),'url':final,'revision':pin['revision'],'license':pin['license'],'sha256':digest,'bytes':len(data)}
