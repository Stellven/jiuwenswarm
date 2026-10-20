"""Real runner/referee UID transfer under umask077; controlled visible bytes.

This is a custody mechanics check, not a campaign or product acceptance result.
"""
import hashlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import tempfile
import zipfile

import pytest


def identity(pipe,uid,groups,root,operation):
    try:
        os.setgroups(groups);os.setgid(uid);os.setuid(uid);os.umask(0o077)
        root=Path(root)
        from jiuwenswarm.research_sidecar.evidence import freeze_archive,read_verified
        if operation=='freeze':
            data=b'controlled authorized visible evidence';pin={'id':'controlled:bytes','sha256':hashlib.sha256(data).hexdigest()}
            manifest={'run_id':'controlled','audience':'researcher','artifact_refs':[pin],
                'files':[{'path':'evidence/visible.txt','artifact_ref':pin,'audience':'researcher'}]}
            buffer=io.BytesIO()
            with zipfile.ZipFile(buffer,'w') as archive:
                archive.writestr('client_retrieval.json',json.dumps(manifest));archive.writestr('evidence/visible.txt',data)
            freeze_archive(root/'results/controlled/export',buffer.getvalue(),run_id='controlled',audience='researcher')
            pipe.send({'path':'evidence/visible.txt','sha256':pin['sha256']})
        elif operation=='read':
            manifest=json.loads((root/'results/controlled/export/client_retrieval.json').read_bytes())
            row=manifest['files'][0]
            assert read_verified(root/'results/controlled/export',{'path':row['path'],'sha256':row['artifact_ref']['sha256']})==b'controlled authorized visible evidence'
            pipe.send('read exact visible bytes')
        else:
            try:(root/'results/controlled/export/client_retrieval.json').read_bytes()
            except PermissionError:pipe.send('denied')
            else:raise AssertionError('unrelated UID read protected evidence')
    except BaseException as exc:pipe.send({'error':type(exc).__name__,'message':str(exc)})
    finally:pipe.close()


def invoke(uid,groups,root,operation):
    parent,child=multiprocessing.Pipe(duplex=False);process=multiprocessing.Process(target=identity,args=(child,uid,groups,str(root),operation))
    process.start();child.close()
    try:
        assert parent.poll(15),'UID transfer did not complete'
        value=parent.recv();process.join(5)
        assert process.exitcode==0,value
        assert not (isinstance(value,dict) and 'error' in value),value
        return value
    finally:
        if process.is_alive():process.kill();process.join(5)
        parent.close()


def test_actual_runner_referee_exact_archive_bytes_and_unrelated_uid_denial():
    if not hasattr(os,'geteuid') or os.geteuid()!=0:pytest.fail('BLOCKED: explicit Linux root UID-transition mechanics driver required')
    root=Path(tempfile.mkdtemp(prefix='ai4r-qa-evidence-'));root.chmod(0o711)
    try:
        results=root/'results';results.mkdir();os.chown(results,11001,11001);results.chmod(0o2750)
        assert 'sha256' in invoke(11001,[],root,'freeze')
        assert invoke(11002,[11001],root,'read')=='read exact visible bytes'
        assert invoke(11003,[],root,'denied')=='denied'
        for path in (results/'controlled',results/'controlled/export',results/'controlled/export/evidence'):
            assert path.stat().st_mode&0o7777==0o2750
            assert path.stat().st_gid==11001
        assert (results/'controlled/export/client_retrieval.json').stat().st_mode&0o777==0o640
    finally:shutil.rmtree(root)
