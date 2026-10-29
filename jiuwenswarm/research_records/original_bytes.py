"""Small explicit original-byte publication with opaque Ref identities.

Only the owner writes the index. Readers receive a bounded read-only root;
neither a Ref ID nor a caller chooses a filesystem path.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import threading
import uuid


def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')


class OriginalBytes:
    def __init__(self,root,*,writable=False):
        self.root=Path(root);self.writable=writable;self.lock=threading.RLock()
        if not self.root.is_absolute() or any(p.is_symlink() for p in (self.root,*self.root.parents)):raise ValueError('Unsafe original-byte root')
        if writable:
            self.root.mkdir(mode=0o2750,parents=True,exist_ok=True)
            if os.name=='posix':
                info=self.root.stat()
                if info.st_uid!=os.geteuid() or info.st_mode&0o022:raise ValueError('Unsafe original-byte publisher custody')
                os.chmod(self.root,0o2750)
    def index(self):
        path=self.root/'original-byte-index.json'
        if not path.exists() and self.writable:return {}
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
        try:
            meta=os.fstat(descriptor)
            if not stat.S_ISREG(meta.st_mode) or meta.st_nlink!=1 or meta.st_mode&0o022 or meta.st_size>4*1024*1024:raise ValueError('Unsafe original-byte index')
            with os.fdopen(descriptor,'rb',closefd=False) as stream:value=json.loads(stream.read(4*1024*1024+1))
        finally:os.close(descriptor)
        if set(value)!={'schema','refs'} or value['schema']!='ai4r-original-bytes:1' or not isinstance(value['refs'],dict):raise ValueError('Unknown original-byte index')
        return value['refs']
    def read(self,ref):
        if not isinstance(ref,dict) or set(ref)!={'id','sha256'}:raise ValueError('Exact Ref required')
        entry=self.index().get(ref['id'])
        if entry is None or entry!=ref['sha256'] or not isinstance(entry,str) or len(entry)!=64 or any(c not in '0123456789abcdef' for c in entry):raise ValueError('Original-byte identity unavailable')
        path=self.root/(entry+'.bytes');descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
        try:
            meta=os.fstat(descriptor)
            if not stat.S_ISREG(meta.st_mode) or meta.st_nlink!=1 or meta.st_mode&0o022 or meta.st_size>4*1024*1024:raise ValueError('Unsafe original bytes')
            with os.fdopen(descriptor,'rb',closefd=False) as stream:raw=stream.read(4*1024*1024+1)
        finally:os.close(descriptor)
        if hashlib.sha256(raw).hexdigest()!=entry:raise ValueError('Original bytes changed')
        return raw
    def get(self,ref):return json.loads(self.read(ref))
    def put_ref(self,ref,raw):
        if not self.writable or not isinstance(ref,dict) or set(ref)!={'id','sha256'} or not isinstance(ref['id'],str) or not ref['id'] or not isinstance(raw,bytes) or len(raw)>4*1024*1024 or hashlib.sha256(raw).hexdigest()!=ref['sha256']:raise ValueError('Unauthorized original-byte publication')
        with self.lock:
            index=self.index()
            if ref['id'] in index and index[ref['id']]!=ref['sha256']:raise ValueError('Opaque identity conflict')
            path=self.root/(ref['sha256']+'.bytes')
            try:
                with path.open('xb') as stream:
                    if os.name=='posix':os.fchmod(stream.fileno(),0o640)
                    stream.write(raw);stream.flush();os.fsync(stream.fileno())
            except FileExistsError:
                if path.is_symlink() or path.read_bytes()!=raw:raise ValueError('Original-byte collision')
            index[ref['id']]=ref['sha256'];temporary=self.root/('.index-'+uuid.uuid4().hex)
            try:
                with temporary.open('xb') as stream:
                    if os.name=='posix':os.fchmod(stream.fileno(),0o640)
                    stream.write(encoded({'schema':'ai4r-original-bytes:1','refs':index}));stream.flush();os.fsync(stream.fileno())
                os.replace(temporary,self.root/'original-byte-index.json')
                if hasattr(os,'O_DIRECTORY'):
                    descriptor=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY)
                    try:os.fsync(descriptor)
                    finally:os.close(descriptor)
            finally:temporary.unlink(missing_ok=True)
        return ref
    def put_bytes(self,raw):
        digest=hashlib.sha256(raw).hexdigest()
        return self.put_ref({'id':digest+'.json','sha256':digest},raw)
    def put(self,value):return self.put_bytes(encoded(value))
