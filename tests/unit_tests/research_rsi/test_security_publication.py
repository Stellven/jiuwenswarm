"""Defensive immutable-file publication mechanics; never IF015 qualification."""
import base64
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.contracts import rsi_installation as installation
from jiuwenswarm.research_rsi import security_publication as publication
from jiuwenswarm.research_rsi.records import encoded


def originals_fixture():
    rows=[];values={}
    for index in range(6):
        raw=encoded({'unit':'File mechanics only; no qualification','ordinal':index})
        digest=hashlib.sha256(raw).hexdigest();pin={'id':'unit:original:'+str(index),'sha256':digest}
        rows.append({'ref':pin,'kind':'unit-original'});values[encoded(pin)]=raw
    def read(pin):return values[encoded(pin)]
    def kind(pin):return 'unit-original'
    manifest=dict(schema='ai4r-rsi-security-installation:1',qualification_ref=rows[0]['ref'],scope_ref=rows[1]['ref'],
        validation_profile_ref=rows[2]['ref'],assertion_manifest_ref=rows[3]['ref'],attack_pins_ref=rows[4]['ref'],
        runtime_observation_ref=rows[5]['ref'],custodian_key_id='unit:not-operational',
        custodian_public_key=base64.urlsafe_b64encode(b'x'*32).decode().rstrip('='),rpc_session_id='unit:scope',rpc_capability='A'*43,
        originals=rows)
    return manifest,publication._Originals(rows,read,kind),read,kind


@pytest.fixture
def empty_fixed_root(tmp_path,monkeypatch):
    if os.name!='posix' or os.geteuid()!=0:
        yield None;return
    root=tmp_path/'fixed-root';root.mkdir(mode=0o750);os.chown(root,0,13000);os.chmod(root,0o750)
    monkeypatch.setattr(installation,'ROOT',root)
    yield root


def test_private_key_types_are_rejected_before_original_bytes_are_read():
    pin={'id':'unit:forbidden','sha256':'a'*64};calls=[]
    def read(_):calls.append(True);raise AssertionError('Private-key bytes must not be imported')
    with pytest.raises(ValueError):
        publication._Originals([{'ref':pin,'kind':'custodian-private-key'}],read,lambda _:'custodian-private-key')
    assert calls==[]


def test_supplied_kind_cannot_shadow_protected_type_index():
    pin={'id':'unit:forbidden','sha256':'a'*64};calls=[]
    def read(_):calls.append(True);return b'never read'
    with pytest.raises(ValueError):
        publication._Originals([{'ref':pin,'kind':'public-original'}],read,lambda _:'custodian-private-key')
    assert calls==[]


def test_empty_raw_original_is_hash_verified_without_becoming_a_json_record():
    raw=b'';pin={'id':'unit:empty-stderr','sha256':hashlib.sha256(raw).hexdigest()}
    originals=publication._Originals([{'ref':pin,'kind':'original-bytes'}],lambda _:raw,lambda _:'original-bytes')
    assert originals.read(pin)==b''
    with pytest.raises(ValueError):originals.get(pin)


def test_missing_full_authority_never_touches_empty_installation_root(empty_fixed_root):
    if empty_fixed_root is None:return
    manifest,_,read,kind=originals_fixture()
    for authority in (None,True,SimpleNamespace(require=lambda *args,**kwargs:{'qualified':True})):
        result=publication.publish_security_installation(manifest,read=read,kind_reader=kind,
            authority=authority,current_observer=True)
        assert result['status']=='BLOCKED' and list(empty_fixed_root.iterdir())==[]


def test_verified_file_mechanics_have_exact_root_modes_and_atomic_manifest_last(empty_fixed_root,monkeypatch):
    """Private I/O helper only: these bytes are deliberately not qualification."""
    if empty_fixed_root is None:return
    manifest,originals,_,_=originals_fixture();calls=[];install=publication._install_exclusive
    def last(pending,target):
        assert target==empty_fixed_root/'installation.json' and not target.exists()
        assert (empty_fixed_root/'originals/original-byte-index.json').is_file()
        assert (empty_fixed_root/'runtime-observation.json').read_bytes()==originals.raw[encoded(manifest['runtime_observation_ref'])]
        assert not (empty_fixed_root/'.publication-claim').exists()
        calls.append(True);return install(pending,target)
    monkeypatch.setattr(publication,'_install_exclusive',last)
    result=publication._publish_verified(manifest,originals)
    assert result['status']=='PUBLISHED' and calls==[True]
    assert (empty_fixed_root/'installation.json').read_bytes()==encoded(manifest)
    index=json.loads((empty_fixed_root/'originals/original-byte-index.json').read_bytes())
    assert index=={'schema':'ai4r-original-bytes:1','refs':{row['ref']['id']:row['ref']['sha256'] for row in manifest['originals']}}
    for path in empty_fixed_root.rglob('*'):
        meta=path.stat();assert meta.st_uid==0 and meta.st_gid==13000
        if path.is_file():assert meta.st_nlink==1
        assert (meta.st_mode&0o777)==(0o750 if path.is_dir() else 0o640)


def test_existing_installation_is_never_overwritten_even_by_a_new_publication_request(empty_fixed_root):
    if empty_fixed_root is None:return
    marker=empty_fixed_root/'installation.json';marker.write_bytes(b'unit: existing immutable installation')
    manifest,_,_,_=originals_fixture();calls=[]
    def absent(_):calls.append(True);raise AssertionError('Existing installation must be refused before reads')
    result=publication.publish_security_installation(manifest,read=absent,kind_reader=absent,authority=None,current_observer=None)
    assert result['status']=='BLOCKED' and marker.read_bytes()==b'unit: existing immutable installation' and calls==[]


def test_failed_staging_removes_only_new_files_and_never_exposes_manifest(empty_fixed_root,monkeypatch):
    if empty_fixed_root is None:return
    manifest,originals,_,_=originals_fixture();write=publication._write_new;count=[0]
    def fail(path,data):
        count[0]+=1
        if count[0]==3:raise OSError('Controlled metadata write failure')
        return write(path,data)
    monkeypatch.setattr(publication,'_write_new',fail)
    with pytest.raises(OSError):publication._publish_verified(manifest,originals)
    assert list(empty_fixed_root.iterdir())==[]
