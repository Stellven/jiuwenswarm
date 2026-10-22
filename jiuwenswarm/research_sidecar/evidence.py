"""Immutable bounded evidence files. No product state volume access."""
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import io
import stat
import tempfile
import zipfile
import math
import errno


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')


def relative(value):
    p=PurePosixPath(value)
    if not value or p.is_absolute() or '..' in p.parts or '\\' in value or ':' in value:raise ValueError('unsafe evidence path')
    return p


def _owned_acl_directory_mode(path, mode):
    """Permit inherited host ACLs only inside an explicitly owned output tree.

    Some writable host filesystems map newly created directories to another UID
    and reject chmod. Their ACL is the access authority. Never apply this to
    credentials, old custody exports, foreign paths or a read-only mount.
    """
    path=Path(path)
    if any(item.is_symlink() for item in (path,*path.parents)) or not path.is_dir():raise ValueError('unsafe owned ACL directory')
    try:path.chmod(mode);return
    except OSError as error:
        if error.errno not in {errno.EPERM,errno.EACCES,errno.ENOTSUP,errno.EOPNOTSUPP}:raise
        original=error
    owned=False
    for parent in (path,*path.parents):
        marker=parent/'.runner-owner.json'
        if marker.is_symlink():raise ValueError('unsafe output ownership marker')
        if marker.is_file():
            if marker.stat().st_size>4096 or marker.stat().st_nlink!=1:raise ValueError('invalid output ownership marker')
            record=json.loads(marker.read_bytes())
            if record=={'owner':'ai4r-sequential-runner:1','campaign_id':parent.name}:owned=True
            break
    if not owned:raise original
    descriptor,probe=tempfile.mkstemp(prefix='.acl-access-',dir=path)
    try:
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(b'owned output ACL access probe');stream.flush();os.fsync(stream.fileno())
    finally:os.unlink(probe)


def _evidence_directory(path,*,portable=False):
    """Set group-read custody only on directories this invocation creates."""
    path=Path(path);missing=[];current=path
    while not current.exists():
        if current.is_symlink():raise ValueError('symlink evidence directory denied')
        missing.append(current);current=current.parent
    if any(item.is_symlink() for item in (current,*current.parents)) or not current.is_dir():raise ValueError('unsafe evidence parent')
    for directory in reversed(missing):
        directory.mkdir(mode=0o2750)
        if os.name=='posix':
            if portable:_owned_acl_directory_mode(directory,0o2750)
            else:directory.chmod(0o2750)
    if path.is_symlink() or not path.is_dir():raise ValueError('unsafe evidence directory')
    return path


def write_once(path,value):
    path=Path(path);_evidence_directory(path.parent)
    data=value if isinstance(value,bytes) else canonical(value)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o640)
    with os.fdopen(fd,'wb') as stream:
        if os.name=='posix':os.fchmod(stream.fileno(),0o640)
        stream.write(data);stream.flush();os.fsync(stream.fileno())
    return {'path':str(path),'sha256':hashlib.sha256(data).hexdigest()}


def read_verified(root,row,max_bytes=16*1024*1024):
    base=Path(root).resolve(strict=True);path=base/relative(row['path'])
    for p in [path,*path.parents]:
        if p==base:break
        if p.is_symlink():raise ValueError('symlink evidence denied')
    if not path.resolve(strict=True).is_relative_to(base):raise ValueError('evidence outside frozen export')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>max_bytes:raise ValueError('evidence is not one bounded regular file')
        data=stream.read(max_bytes+1)
        if len(data)>max_bytes:raise ValueError('evidence exceeds read bound')
    if hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('evidence digest mismatch')
    return data


def validate_empirical(value,receipts,metric_ids,validate):
    validate('empirical-results',value)
    rows=value['runs']
    expected={r['sequence'] for r in receipts}
    actual=[r['sequence'] for r in rows]
    if len(actual)!=len(set(actual)) or set(actual)!=expected:raise ValueError('one empirical row per actual receipt required')
    if actual!=list(range(1,len(rows)+1)):raise ValueError('empirical sequence is not the actual ordered receipt sequence')
    receipts_by_sequence={r['sequence']:r for r in receipts}
    for row in rows:
        measured=set(row['metrics']);missing=set(row['unmeasured_metrics'])
        if measured&missing or measured|missing!=set(metric_ids):raise ValueError('complete disjoint metric coverage required')
        if any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) for v in row['metrics'].values()):raise ValueError('nonfinite or nonnumeric empirical observation')
        status='measured' if not missing else 'partial' if measured else 'unmeasured'
        if row['status']!=status:raise ValueError('metric coverage contradicts measurement status')
        receipt=receipts_by_sequence[row['sequence']]
        if receipt.get('exit_code',0)!=0 and measured:raise ValueError('failed-process printed numbers are not admissible measurements')
    return value


def unpack_authorized_archive(raw,*,run_id,audience,validate=None,max_bytes=64*1024*1024,max_files=4096):
    if audience not in {'researcher','reviewer'} or not isinstance(raw,bytes) or len(raw)>max_bytes:raise ValueError('export archive policy exceeded')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries=archive.infolist();names=[x.filename for x in entries]
            if len(entries)>max_files or len(names)!=len(set(names)) or names.count('client_retrieval.json')!=1:raise ValueError('duplicate or missing manifest')
            if sum(x.file_size for x in entries)>max_bytes:raise ValueError('expanded archive policy exceeded')
            for entry in entries:
                relative(entry.filename)
                if entry.is_dir() or stat.S_ISLNK(entry.external_attr>>16) or entry.flag_bits&1:raise ValueError('nonregular or encrypted export member')
            manifest=json.loads(archive.read('client_retrieval.json'))
            if validate:validate('client-retrieval',manifest)
            if manifest['run_id']!=run_id or manifest['audience']!=audience:raise ValueError('export identity or audience mismatch')
            expected={};refs=manifest['artifact_refs']
            for file in manifest['files']:
                name=str(relative(file['path']))
                if name=='client_retrieval.json' or name in expected or file['artifact_ref'] not in refs:raise ValueError('duplicate or unbound NamedFile')
                if file['audience'] not in ({'researcher'} if audience=='researcher' else {'researcher','reviewer'}):raise ValueError('unauthorized NamedFile audience')
                expected[name]=file
            if set(names)!={'client_retrieval.json',*expected}:raise ValueError('missing or unexpected exported file')
            files={}
            for name,file in expected.items():
                payload=archive.read(name)
                if hashlib.sha256(payload).hexdigest()!=file['artifact_ref']['sha256']:raise ValueError('swapped exported bytes')
                files[name]=payload
            return manifest,files
    except (zipfile.BadZipFile,KeyError,TypeError,json.JSONDecodeError):raise ValueError('invalid authorized export archive') from None


def freeze_archive(destination,raw,*,run_id,audience,validate=None):
    manifest,files=unpack_authorized_archive(raw,run_id=run_id,audience=audience,validate=validate)
    dest=Path(destination)
    if dest.exists() or dest.is_symlink():raise ValueError('frozen export identity already exists')
    _evidence_directory(dest.parent)
    with tempfile.TemporaryDirectory(prefix='.export-',dir=dest.parent) as temporary:
        staging=Path(temporary)
        if os.name=='posix':staging.chmod(0o2750)
        for name,payload in files.items():write_once(staging/name,payload)
        write_once(staging/'client_retrieval.json',manifest)
        write_once(staging/'archive.zip',raw)
        os.rename(staging,dest)
    return manifest
