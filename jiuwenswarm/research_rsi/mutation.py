"""Validate every assessed mutation before isolated execution or hidden exposure."""
import fnmatch
import hashlib
from pathlib import Path
import os
import shutil
import stat
from copy import deepcopy
from .profiles import safe_path,ProfileError


class SecurityViolation(ValueError):pass


def checked_changes(parent,changes,allowed,protected):
    if len(changes)!=1:raise SecurityViolation('exactly one mutable body required')
    root=Path(parent).resolve(strict=True)
    for relative,data in changes.items():
        try:safe_path(relative)
        except ProfileError:raise SecurityViolation('unsafe mutation path') from None
        if not any(fnmatch.fnmatchcase(relative,x) for x in allowed) or any(fnmatch.fnmatchcase(relative,x) for x in protected):raise SecurityViolation('mutation outside allowed body')
        path=root/relative
        for item in [path,*path.parents]:
            if item==root:break
            if item.is_symlink():raise SecurityViolation('symlink mutation denied')
        if not path.is_file() or path.stat().st_nlink!=1:raise SecurityViolation('nonregular or linked parent body')
        if not isinstance(data,bytes) or not data:raise SecurityViolation('empty or invalid proposed body')
    return sorted(changes)


def materialize(parent,destination,changes,allowed,protected):
    checked_changes(parent,changes,allowed,protected)
    root=Path(parent)
    for path in root.rglob('*'):
        info=path.lstat()
        if stat.S_ISLNK(info.st_mode) or stat.S_ISREG(info.st_mode) and info.st_nlink!=1:raise SecurityViolation('linked parent snapshot denied')
    dest=Path(destination)
    if dest.exists():raise SecurityViolation('child sandbox must be new')
    shutil.copytree(root,dest,symlinks=False)
    for relative,data in changes.items():(dest/relative).write_bytes(data)
    digest=hashlib.sha256(next(iter(changes.values()))).hexdigest()
    return {'path':str(dest),'body_sha256':digest,'mutable_paths_touched':sorted(changes)}


def child_declaration(parent,*,body_hashes,version_label,carrier,lineage,validate):
    permitted=[x[6:] for x in parent['evolution'].get('may_change',[]) if x.startswith('files:')]
    old={x['path']:x['sha256'] for x in parent['identity']['body']}
    touched={path for path in old.keys()|body_hashes.keys() if old.get(path)!=body_hashes.get(path)}
    if not touched or any(not any(fnmatch.fnmatchcase(path,pattern) for pattern in permitted) for path in touched):raise SecurityViolation('child changed body outside parent may_change')
    if parent['evolution']['rsi']!='propose' or version_label==parent['identity']['version_label']:raise SecurityViolation('new proposed child version required')
    child=deepcopy(parent)
    child['identity'].update(version_label=version_label,body=[{'path':p,'sha256':h} for p,h in sorted(body_hashes.items())],carrier=carrier,lineage=lineage)
    validate('capsule-declaration',child)
    # Only these four derived pointers may differ; all authored obligations and
    # evolution permissions are inherited byte-equivalent as JSON values.
    return child
