"""Collect a bounded authorized original-byte archive without expanding traces."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from collections import Counter, defaultdict
import uuid
import zipfile

from jiuwenswarm.research_records.contracts import ContractData


METADATA_CEILING_BYTES = 128 * 1024 * 1024  # retrieval manifest and central directory

def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf8')


def safe_name(value):
    return (isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*',value) is not None
            and all(part not in {'.','..'} for part in value.split('/')))


def readable_name(item):
    """Keep optional host copies short; originals retain their archive paths."""
    original=item['path']
    if len(original)<=80:return original
    basename=PurePosixPath(original)
    identity=hashlib.sha256(encoded([original,item['sha256']])).hexdigest()
    return basename.stem[:6]+'-'+identity+basename.suffix


def directory(path):
    path=Path(path).absolute()
    if any(item.is_symlink() for item in (path,*path.parents)):raise ValueError('archive destination contains a symlink')
    path.mkdir(parents=True,exist_ok=True)
    if not path.is_dir():raise ValueError('archive destination directory required')


def metadata(path):
    path=Path(path);digest=hashlib.sha256();size=0
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink!=1:raise ValueError('archive evidence must be a regular owned file')
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(64*1024),b''):digest.update(chunk);size+=len(chunk)
    return {'path':str(path.absolute()),'sha256':digest.hexdigest(),'size':size}


def publish(path,raw):
    path=Path(path);directory(path.parent)
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink!=1 or path.stat().st_size!=len(raw) or path.read_bytes()!=raw:
            raise ValueError('existing archive evidence conflicts; never overwrite')
        return metadata(path)
    temporary=path.parent/('.archive-record-'+uuid.uuid4().hex)
    try:
        with temporary.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.link(temporary,path)
    finally:temporary.unlink(missing_ok=True)
    return metadata(path)


def flush_directory(path):
    if os.name=='posix':
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
        try:os.fsync(descriptor)
        finally:os.close(descriptor)


def strict_json(raw):
    def pairs(items):
        value={}
        for key,item in items:
            if key in value:raise ValueError('duplicate archive manifest JSON key')
            value[key]=item
        return value
    def nonfinite(_):raise ValueError('nonfinite archive manifest JSON')
    return json.loads(raw.decode('utf8'),object_pairs_hook=pairs,parse_constant=nonfinite)


def validate_archive(path,source,*,max_total_bytes,max_member_bytes,max_members,audience):
    """Prove exact identity multiplicity even when descriptive ordinal paths move."""
    artifacts=source.get('artifacts')
    if (not isinstance(artifacts,list) or len(artifacts)>max_members or source.get('audience')!=audience):
        raise ValueError('authorized archive inventory exceeds finite member policy')
    expected_source_hash=hashlib.sha256(encoded({k:v for k,v in source.items() if k!='manifest_sha256'})).hexdigest()
    if expected_source_hash!=source.get('manifest_sha256'):raise ValueError('authorized archive source manifest hash mismatch')
    if any(type(item.get('size')) is not int or item['size']<0 or item['size']>max_member_bytes for item in artifacts):
        raise ValueError('authorized archive member size exceeds policy')
    if sum(item['size'] for item in artifacts)>max_total_bytes:raise ValueError('authorized archive expanded bytes exceed policy')
    # Metadata is separately bounded; the actual artifact byte policy is unchanged.
    # A completed planned POC run retains ~60k files; its retrieval manifest is ~34 MB (pl13).
    metadata_limit=min(METADATA_CEILING_BYTES,max(1024*1024,max_members*2048))
    verified=[];total=0
    # The stdlib footer parser reads only the bounded EOCD tail/ZIP64 footer;
    # inspect counts and central-directory bytes before ZipFile allocates rows.
    with Path(path).open('rb') as stream:
        footer=zipfile._EndRecData(stream)
    if (footer is None or footer[zipfile._ECD_ENTRIES_TOTAL]!=len(artifacts)+1
            or footer[zipfile._ECD_ENTRIES_TOTAL]>max_members+1
            or footer[zipfile._ECD_SIZE]>METADATA_CEILING_BYTES or footer[zipfile._ECD_SIZE]<0
            or footer[zipfile._ECD_OFFSET]<0
            or footer[zipfile._ECD_OFFSET]+footer[zipfile._ECD_SIZE]>Path(path).stat().st_size):
        raise ValueError('archive central directory exceeds authorized metadata policy')
    with zipfile.ZipFile(path) as archive:
        entries=archive.infolist()
        if len(entries)!=len(artifacts)+1 or len(entries)>max_members+1:raise ValueError('archive member inventory differs')
        by_name={}
        for entry in entries:
            mode=entry.external_attr>>16
            if (not safe_name(entry.filename) or entry.filename in by_name or entry.is_dir() or entry.flag_bits&1
                    or stat.S_IFMT(mode) not in {0,stat.S_IFREG} or entry.file_size<0
                    or entry.compress_type not in {zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED}):
                raise ValueError('unsafe or duplicate archive member')
            limit=metadata_limit if entry.filename=='client_retrieval.json' else max_member_bytes
            if entry.file_size>limit:raise ValueError('archive member exceeds size policy')
            by_name[entry.filename]=entry
        manifest_entry=by_name.get('client_retrieval.json')
        if manifest_entry is None:raise ValueError('original archive retrieval manifest missing')
        with archive.open(manifest_entry) as stream:raw=stream.read(metadata_limit+1)
        if len(raw)>metadata_limit:raise ValueError('archive retrieval manifest exceeds metadata policy')
        retrieval=strict_json(raw);ContractData().validate('client-retrieval',retrieval)
        if retrieval['run_id']!=source['run_id'] or retrieval['audience']!=audience:raise ValueError('archive scope differs from authorized run')
        files=retrieval['files'];names=[item['path'] for item in files]
        if len(names)!=len(set(names)) or set(names)!=set(by_name)-{'client_retrieval.json'}:
            raise ValueError('archive has extra or missing original file paths')
        allowed_refs={(ref['id'],ref['sha256']) for ref in retrieval['artifact_refs']}
        actual_refs={(item['artifact_ref']['id'],item['artifact_ref']['sha256']) for item in files}
        if allowed_refs!=actual_refs:raise ValueError('archive allowed reference inventory differs')
        candidates=defaultdict(dict)
        for item in files:
            ref=item['artifact_ref']
            if item['audience']!=audience:raise ValueError('archive member audience differs')
            candidates[(ref['sha256'],item['media_type'])][(ref['id'],ref['sha256'])]=ref
        original=Counter();source_paths=set()
        for item in artifacts:
            if not safe_name(item['path']) or item['path'] in source_paths:raise ValueError('unsafe source archive path inventory')
            source_paths.add(item['path'])
            refs=[ref for ref in candidates[(item['sha256'],item['media_type'])].values()
                  if hashlib.sha256(encoded([item['path'],ref])).hexdigest()==item['artifact_id']]
            if len(refs)!=1:raise ValueError('archive original reference identity is missing or differs')
            original[(refs[0]['id'],item['sha256'],item['media_type'],item['size'])]+=1
        actual=Counter()
        for item in files:
            name=item['path'];entry=by_name[name];ref=item['artifact_ref'];digest=hashlib.sha256();size=0
            with archive.open(entry) as stream:
                while chunk:=stream.read(64*1024):
                    size+=len(chunk);total+=len(chunk)
                    if size>max_member_bytes or total>max_total_bytes:raise ValueError('archive expanded bytes exceed policy')
                    digest.update(chunk)
            if size!=entry.file_size or digest.hexdigest()!=ref['sha256']:raise ValueError('archive original member hash or size mismatch')
            actual[(ref['id'],ref['sha256'],item['media_type'],size)]+=1
            verified.append({'path':name,'sha256':ref['sha256'],'size':size,'media_type':item['media_type']})
        if original!=actual:raise ValueError('archive original identity/media/size multiplicity differs')
    return {'schema_version':'1.0.0','run_id':source['run_id'],'audience':audience,
            'source_manifest_sha256':source['manifest_sha256'],'client_retrieval':retrieval,
            'verified_members':verified,'total_uncompressed_bytes':total}


async def collect_archive(client,run_id,manifest,destination,*,max_archive_bytes,max_total_bytes,max_member_bytes,
                          max_members=100000,max_extract_files=32,max_extract_bytes=4*1024*1024,audience='researcher'):
    for value in (max_archive_bytes,max_total_bytes,max_member_bytes,max_members):
        if type(value) is not int or value<=0:raise ValueError('finite positive archive policy required')
    if type(max_extract_files) is not int or max_extract_files<0 or type(max_extract_bytes) is not int or max_extract_bytes<0:
        raise ValueError('bounded readable extraction policy required')
    if manifest.get('run_id')!=run_id:raise ValueError('archive run differs from authorized manifest')
    destination=Path(destination).absolute();directory(destination.parent)
    if destination.is_symlink():raise ValueError('archive destination is a symlink')
    temporary=destination.parent/('.archive-transfer-'+uuid.uuid4().hex+'.zip')
    selected=destination if destination.exists() else temporary
    try:
        if not destination.exists():
            await client.stream_export_archive(run_id,temporary,audience=audience,max_bytes=max_archive_bytes)
        archive_meta=metadata(selected)
        if archive_meta['size']>max_archive_bytes:raise ValueError('archive exceeds transport policy')
        inventory=validate_archive(selected,manifest,max_total_bytes=max_total_bytes,max_member_bytes=max_member_bytes,
                                   max_members=max_members,audience=audience)
        if selected==temporary:
            os.link(temporary,destination);temporary.unlink();flush_directory(destination.parent)
        archive_meta['path']=str(destination)
        inventory['archive']=archive_meta
        inventory_path=destination.with_suffix('.inventory.json')
        inventory_meta=publish(inventory_path,encoded(inventory));flush_directory(inventory_path.parent)
        extracted=[];extracted_bytes=0
        candidates=sorted((item for item in inventory['verified_members']
            if PurePosixPath(item['path']).suffix.lower() in {'.md','.markdown','.txt'}),
            key=lambda item:(len(PurePosixPath(item['path']).parts),item['path']))
        with zipfile.ZipFile(destination) as archive:
            for item in candidates:
                if len(extracted)>=max_extract_files:break
                if item['size']>max_extract_bytes-extracted_bytes:continue
                with archive.open(item['path']) as stream:raw=stream.read(item['size']+1)
                if len(raw)!=item['size'] or hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('readable extraction byte mismatch')
                target=destination.parent/'readable'/readable_name(item)
                extracted.append(publish(target,raw));flush_directory(target.parent)
                extracted_bytes+=len(raw)
        return {'archive':archive_meta,'inventory':inventory_meta,'extracted':extracted,
                'verified_members':len(inventory['verified_members']),'total_uncompressed_bytes':inventory['total_uncompressed_bytes']}
    except (zipfile.BadZipFile,RuntimeError,EOFError) as error:
        raise ValueError('malformed original-byte archive') from error
    finally:temporary.unlink(missing_ok=True)
