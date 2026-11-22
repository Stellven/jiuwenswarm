"""CPU fixtures and fake child only; no native inference/model claims."""
import base64
import copy
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys

import pytest

PACKAGE=Path(__file__).resolve().parents[2]/'jiuwenswarm/factory/ccs/numerical_investigation_lab'
sys.path.insert(0,str(PACKAGE))
import capture_adapter as a
import components as c


def fixture(tmp_path):
    profile=dict(args=['--pack','/pack','--experts','6','--mmap-experts','on','--cpu-threads','8','--reserve-mib','16384','--vram-experts','1.0','--dspark','none','--dspark-conf','0.65','--no-expert-cache','--prefill-chunk','256'],environment={'STRATA_DS4_REUSE':'0','DS4_UMA_HEADROOM_GIB':'16','DS4_COPY_ALL':'0','DS4_STORE_GB':'0'},image='sha256:'+'a'*64)
    identity=dict(model='model-digest',tokenizer='tokenizer-digest',source='source-digest',precision='f32',routing='full6',profile=a.digest(profile))
    spec=c.replay_spec(identity,identity,[1,2],[1]*50,49,4,[],dict(declaration_id='predeclared',absolute_tolerance=0,relative_tolerance=0,top_k=2))['spec']
    raw=b''.join(struct.pack('<ffff',float(n),0,1,2) for n in range(50))
    (tmp_path/'dump.f32').write_bytes(raw)
    (tmp_path/'stdout.txt').write_text('READY 4096 stop\n'+('T 1\n'*50)+'DONE 50 2 10.0 20.0 length 0 0 0 0 0\n')
    (tmp_path/'stdin.txt').write_text(a.capture_plan(profile,spec,'baseline','/tmp/fixture')['request']+'\nQUIT\n')
    return profile,spec,raw


def invoke(tmp_path, profile, spec, dump='dump.f32'):
    return a.import_capture(spec,'baseline',str(tmp_path),dump,'stdout.txt','stdin.txt',profile,a.SOURCE_MAIN_SHA256)


def test_plan_is_opt_in_and_preserves_generation_profile(tmp_path):
    profile,spec,raw=fixture(tmp_path)
    original=copy.deepcopy(profile)
    plan=a.capture_plan(profile,spec,'baseline','/tmp/private/logits')
    assert plan['request']=='GEN 50 temperature=0 top_p=1 top_k=1 min_p=0 seed=42 spec=0 1,2'
    assert plan['profile']['environment']['DS4_SERVE_DUMP']=='/tmp/private/logits'
    assert profile==original and plan['executed'] is False
    assert plan['source_main_sha256']==a.SOURCE_MAIN_SHA256
    result=invoke(tmp_path,profile,spec)
    assert result['capture']['logits']==[49.,0.,1.,2.]
    assert result['capture']['history_ids']==[1,2]+[1]*49
    assert result['provenance']['full_raw_hash_recomputed'] is True
    c.capture(result['capture'],spec,'baseline')


@pytest.mark.parametrize('kind',['short','extra','nan','draft','history','cancel','error','missingdone','profile','source','symlink','prompt','multiple'])
def test_import_fails_closed(tmp_path,kind):
    profile,spec,raw=fixture(tmp_path)
    transcript=tmp_path/'stdout.txt'
    if kind=='short': (tmp_path/'dump.f32').write_bytes(raw[:-1])
    if kind=='extra': (tmp_path/'dump.f32').write_bytes(raw+b'xxxx')
    if kind=='nan': (tmp_path/'dump.f32').write_bytes(raw[:-4]+struct.pack('<f',float('nan')))
    if kind=='draft': transcript.write_text(transcript.read_text().replace('length 0 0','length 1 0'))
    if kind=='history': transcript.write_text(transcript.read_text().replace('T 1','T 2',1))
    if kind=='cancel': transcript.write_text(transcript.read_text().replace('length','cancel'))
    if kind=='error': transcript.write_text(transcript.read_text()+'ERR native failure\n')
    if kind=='missingdone': transcript.write_text('T 1\n'*50)
    if kind=='profile': profile['image']='changed'
    if kind=='prompt': (tmp_path/'stdin.txt').write_text((tmp_path/'stdin.txt').read_text().replace('1,2','2,1'))
    if kind=='multiple': (tmp_path/'stdin.txt').write_text((tmp_path/'stdin.txt').read_text()*2)
    if kind=='source':
        with pytest.raises(ValueError):
            a.import_capture(spec,'baseline',str(tmp_path),'dump.f32','stdout.txt','stdin.txt',profile,'0'*64)
        return
    if kind=='symlink':
        outside=tmp_path.parent/'outside-dump.f32';outside.write_bytes(raw)
        (tmp_path/'dump.f32').unlink();(tmp_path/'dump.f32').symlink_to(outside)
    with pytest.raises(ValueError): invoke(tmp_path,profile,spec)


def test_wrapper_witness_import_retains_limits(tmp_path):
    profile,spec,raw=fixture(tmp_path)
    record=a.witness(raw,4)
    (tmp_path/'witness.json').write_text(json.dumps(record))
    result=invoke(tmp_path,profile,spec,'witness.json')
    assert result['capture']['logits']==[49.,0.,1.,2.]
    assert result['provenance']['full_raw_hash_recomputed'] is False
    record['row_f32_base64']=base64.b64encode(b'\0'*16).decode()
    (tmp_path/'witness.json').write_text(json.dumps(record))
    with pytest.raises(ValueError,match='hash'): invoke(tmp_path,profile,spec,'witness.json')


def test_explicit_wrapper_fake_engine_only(tmp_path):
    child=tmp_path/'fake.py'
    child.write_text("import os,struct,sys\np=os.environ['DS4_SERVE_DUMP']+'.1.f32'\nopen(p,'wb').write(struct.pack('<ffff',1.,2.,3.,4.)*50)\nfor line in sys.stdin:\n print(line.strip(),flush=True)\n")
    result=subprocess.run([sys.executable,str(PACKAGE/'capture_wrapper.py'),'--vocabulary-size','4','--',sys.executable,str(child),'--serve','--dspark','none'],input='fake-input\n',capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert result.stdout=='fake-input\n'
    record=json.loads(result.stderr.split(a.MARKER)[1].splitlines()[0])
    assert record['rows']==50 and record['raw_size']==800
    resources=json.loads(result.stderr.split('STRATA_NUMERICAL_CAPTURE_RESOURCES ')[1])
    assert resources['transport']=='fifo'
    assert resources['tmp_after']['total_bytes']>0
    assert resources['tmp_after']['free_bytes']>=0
    assert 'STRATA_NUMERICAL_CAPTURE_ERROR' not in result.stderr


@pytest.mark.parametrize('prefix,accepted', [('FACTORY_EXEC'+chr(10),True), (('FACTORY_EXEC'+chr(10))*2,False), ('FACTORY_EXEC'+chr(92)+'n',False)])
def test_recorder_line_gate_only(tmp_path,prefix,accepted):
    profile,spec,raw=fixture(tmp_path)
    path=tmp_path/'stdin.txt'
    path.write_text(prefix+path.read_text())
    if accepted:
        assert invoke(tmp_path,profile,spec)['capture']['step']==49
    else:
        with pytest.raises(ValueError,match='stdin'):
            invoke(tmp_path,profile,spec)


def test_contained_read_bounds_and_special_file(tmp_path):
    (tmp_path/'large').write_bytes(b'12345')
    with pytest.raises(ValueError,match='bound'):
        a.read_contained(tmp_path,'large',4)
    import os
    os.mkfifo(tmp_path/'fifo')
    with pytest.raises(ValueError,match='regular'):
        a.read_contained(tmp_path,'fifo',4)


@pytest.mark.parametrize('size,exitcode',[(784,0),(804,0),(0,0),(800,2)])
def test_wrapper_rejection_retains_diagnostic_witness(tmp_path,size,exitcode):
    child=tmp_path/'fake_bad.py'
    child.write_text("import os,sys\nopen(os.environ['DS4_SERVE_DUMP']+'.1.f32','wb').write(b'x'*"+str(size)+")\nsys.exit("+str(exitcode)+")\n")
    result=subprocess.run([sys.executable,str(PACKAGE/'capture_wrapper.py'),'--vocabulary-size','4','--',sys.executable,str(child),'--serve','--dspark','none'],capture_output=True,text=True)
    assert result.returncode != 0
    assert a.MARKER not in result.stderr
    record=json.loads(result.stderr.split('STRATA_NUMERICAL_CAPTURE_ERROR ')[1])
    assert record['format']=='strata-native-logit-capture-failure/1'
    assert record['actual_bytes']==size
    assert record['expected_bytes']==800
    assert record['row_alignment_remainder']==size%16
    assert record['float_alignment_remainder']==size%4
    assert record['complete_rows']==size//16
    assert record['raw_sha256']==a.sha(b'x'*size)
    assert record['hash_scope']=='entire_observed_fifo_stream'
    assert record['complete_capture'] is False
    assert record['child_returncode']==exitcode


def test_fifo_never_opened_exits_without_hang(tmp_path):
    child=tmp_path/'never_open.py';child.write_text('pass\n')
    result=subprocess.run([sys.executable,str(PACKAGE/'capture_wrapper.py'),'--vocabulary-size','4','--',sys.executable,str(child),'--serve','--dspark','none'],capture_output=True,text=True,timeout=5)
    assert result.returncode==1
    record=json.loads(result.stderr.split('STRATA_NUMERICAL_CAPTURE_ERROR ')[1])
    assert record['actual_bytes']==0 and record['retained_bytes']==0
    assert record['capture_transport']=='fifo_ram'
    assert record['tmp_free_bytes_before']>=0 and record['tmp_free_bytes_after']>=0


def test_fifo_drains_overflow_with_bounded_retention(tmp_path):
    child=tmp_path/'overflow.py'
    child.write_text("import os\nwith open(os.environ['DS4_SERVE_DUMP']+'.1.f32','wb') as f:\n for _ in range(1024): f.write(b'x'*4096)\n")
    result=subprocess.run([sys.executable,str(PACKAGE/'capture_wrapper.py'),'--vocabulary-size','4','--',sys.executable,str(child),'--serve','--dspark','none'],capture_output=True,text=True,timeout=5)
    assert result.returncode==1
    record=json.loads(result.stderr.split('STRATA_NUMERICAL_CAPTURE_ERROR ')[1])
    assert record['actual_bytes']==4*1024*1024
    assert record['retained_bytes']==801
    assert record['raw_sha256']==a.sha(b'x'*(4*1024*1024))
    assert record['complete_capture'] is False


def test_fifo_rejects_additional_request_file(tmp_path):
    child=tmp_path/'extra_request.py'
    child.write_text("import os,struct\np=os.environ['DS4_SERVE_DUMP']\nopen(p+'.1.f32','wb').write(struct.pack('<ffff',1.,2.,3.,4.)*50)\nopen(p+'.2.f32','wb').write(b'extra')\n")
    result=subprocess.run([sys.executable,str(PACKAGE/'capture_wrapper.py'),'--vocabulary-size','4','--',sys.executable,str(child),'--serve','--dspark','none'],capture_output=True,text=True,timeout=5)
    assert result.returncode==1
    assert a.MARKER not in result.stderr
    assert 'exactly one original FIFO' in result.stderr


def test_gate_matches_actual_recorder_byte_constant():
    import ast
    from jiuwenswarm.factory import lab_recorder
    tree=ast.parse(Path(lab_recorder.__file__).read_text())
    gates=[node.value for node in ast.walk(tree) if isinstance(node,ast.Constant)
           and isinstance(node.value,bytes) and node.value.startswith(b'FACTORY_EXEC')]
    assert gates==[b'FACTORY_EXEC'+bytes([10])]
