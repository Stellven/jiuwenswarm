"""Core-only specification tests: no MCP, services or agent framework needed."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from jsonschema import ValidationError
import rfc8785

from jiuwenswarm.ccv2.ccv2 import Host, CCError, load, normalize, resolve_request, sha
from jiuwenswarm.ccv2.schema_tools import validate

ROOT = Path(__file__).resolve().parent


class SpecTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.host = Host(self.root/'state')

    def tearDown(self): self.temp.cleanup()

    def test_request_and_prebuilt_have_identical_bytes_identity_and_usage(self):
        request = json.loads((ROOT/'protocol_examples/trim-request.json').read_bytes())
        resolved = resolve_request(request,json.loads((ROOT/'protocol_examples/trim-answers.json').read_bytes()))
        source = ROOT/'protocol_examples/trim'
        self.assertEqual(resolved,load(source/'cc.yaml'))
        runtime = self.root/'runtime-built';shutil.copytree(source,runtime)
        first = self.host.prepare(source);second = self.host.prepare(runtime)
        self.assertEqual(first,second)
        a = self.host.call(first,'trim',{'text':'   '});b = self.host.call(second,'trim',{'text':'   '})
        self.assertEqual(a['outputs'],b['outputs']);self.assertEqual(a['outputs']['trimmed'],'')
        validate('messages.schema.json',a,'receipt')
        self.assertEqual(a['assessment']['verdict'],'not_requested')

    def test_portable_identity_ignores_host_paths_and_file_modes(self):
        source = ROOT/'protocol_examples/trim'
        relocated = self.root/'another-python.exe';shutil.copyfile(sys.executable,relocated)
        other = Host(self.root/'other-state',python=str(relocated))
        a=self.host.prepare(source);b=other.prepare(source)
        self.assertEqual(a,b)
        manifest=json.loads((self.host.store/'releases'/a/'manifest.json').read_bytes())
        self.assertNotIn('executables',manifest)
        self.assertTrue(all(set(row)=={'path','size','sha256'} for row in manifest['files']))
        self.assertEqual(sha(rfc8785.dumps(manifest)),a)
        validate('messages.schema.json',manifest,'release')

    def test_named_binding_does_not_require_unused_default(self):
        raw=load(ROOT/'protocol_examples/trim/cc.yaml')
        raw['bindings']['selected']=raw['bindings'].pop('default')
        raw['capabilities']['trim']['using']='selected'
        validate('cc.schema.json',raw);normalize(raw)

    def test_invalid_protocol_envelopes_are_rejected_but_domain_json_open(self):
        with self.assertRaises(ValidationError):validate('messages.schema.json',{'outcome':'partial','outputs':{}},'processResult')
        validate('messages.schema.json',{'outcome':'ok','outputs':{'result':{'unannounced':{'nested':[1,True,None]}}}},'processResult')
        with self.assertRaises(ValidationError):validate('messages.schema.json',{'outcome':'ok','outputs':{},'invented':1},'processResult')
        raw=load(ROOT/'protocol_examples/trim/cc.yaml');raw['applications']={}
        with self.assertRaises(CCError):normalize(raw)

    def test_unresolved_request_fixed_fields_and_duplicate_ids_fail(self):
        request=json.loads((ROOT/'protocol_examples/trim-request.json').read_bytes())
        request['open']['/id']={'question':'Change fixed identity'}
        with self.assertRaises(CCError):resolve_request(request,{'/id':'changed','/bindings/default':{'kind':'native','command':['python']}})
        bad=self.root/'bad.yaml';bad.write_text("cc: '2'\nid: one\nid: two")
        with self.assertRaises(CCError):load(bad)

    def test_artifact_integrity_missing_files_and_effect_ceiling(self):
        source=self.root/'artifact';source.write_bytes(b'bytes');ref=self.host.put_artifact(source)
        self.host.artifact_path(ref).write_bytes(b'tampered')
        with self.assertRaises(CCError):self.host.artifact_path(ref)
        release=self.host.prepare(ROOT/'protocol_examples/trim')
        result=self.host.call(release,'trim',{'text':'x'},grants=['workspace.write'])
        self.assertEqual(result['reason'],'UNDECLARED_EFFECT')

    def test_image_can_use_its_pinned_entrypoint(self):
        raw={'cc':'2','id':'test.app','version':'1.0.0',
             'bindings':{'app':{'kind':'image','image':'sha256:'+'a'*64}},
             'capabilities':{'serve':{'does':'Serve the image native API','using':'app','serves':{}}}}
        validate('cc.schema.json',raw)
        normalized=normalize(raw)
        self.assertEqual(normalized['bindings']['app']['command'],[])
        validate('cc.schema.json',normalized)

    def test_unavailable_sibling_runtime_does_not_block_selected_capability(self):
        source=self.root/'bundle';shutil.copytree(ROOT/'protocol_examples/trim',source)
        raw=load(source/'cc.yaml')
        raw['bindings']['other']={'kind':'native','command':['cc-intentionally-missing-runtime']}
        raw['capabilities']['other']={'does':'Requires an unavailable runtime','using':'other'}
        (source/'cc.yaml').write_text(json.dumps(raw),encoding='utf-8')
        release=self.host.prepare(source)
        self.assertIn('bindings',self.host.describe(release))
        self.assertEqual(self.host.call(release,'trim',{'text':' x '})['outputs']['trimmed'],'x')
        unavailable=self.host.call(release,'other',{})
        self.assertEqual((unavailable['state'],unavailable['reason']),('blocked','MISSING_IMPLEMENTATION'))

    def test_process_failure_preserves_available_outputs_and_rejects_nonobjects(self):
        source=self.root/'bundle';shutil.copytree(ROOT/'protocol_examples/trim',source)
        (source/'tool.py').write_text("import json,sys; print(json.dumps({'outcome':'partial','outputs':{'trimmed':'partial'},'reason':'interrupted'})); sys.exit(7)",encoding='utf-8')
        result=self.host.run(source,'trim',{'text':'x'})
        self.assertEqual((result['state'],result['reason']),('failed','PROCESS_FAILED'))
        self.assertEqual(result['outputs']['trimmed'],'partial')
        (source/'tool.py').write_text("print('[]')",encoding='utf-8')
        result=self.host.run(source,'trim',{'text':'x'})
        self.assertEqual((result['state'],result['reason']),('failed','INVALID_OUTPUT'))

    def test_release_verification_uses_canonical_index_and_detects_tampering(self):
        release=self.host.prepare(ROOT/'protocol_examples/trim')
        index=self.host.store/'releases'/release/'manifest.json'
        document=json.loads(index.read_bytes())
        index.write_text(json.dumps(document,indent=2),encoding='utf-8')
        self.assertEqual(self.host.describe(release)['id'],'text.trim')
        document['files'][0]['sha256']='0'*64
        index.write_text(json.dumps(document),encoding='utf-8')
        with self.assertRaises(CCError) as error:self.host.release(release)
        self.assertEqual(error.exception.code,'DIGEST_MISMATCH')

    def test_partial_binding_kind_can_be_decided_later(self):
        raw=load(ROOT/'protocol_examples/trim/cc.yaml')
        raw['bindings']={'default':{}}
        request={'format':'cc-request/2','id':'request.partial','desired':raw,
                 'open':{'/bindings/default/kind':{'question':'Choose provider'},
                         '/bindings/default/command':{'question':'Choose argv'}}}
        resolved=resolve_request(request,{'/bindings/default/kind':'native','/bindings/default/command':['{python}','{bundle}/tool.py']})
        self.assertEqual(resolved['bindings']['default']['kind'],'native')

    def test_imported_index_cannot_omit_implementation_or_change_contract(self):
        original=self.host.prepare(ROOT/'protocol_examples/trim')
        original_dir=self.host.store/'releases'/original
        document=json.loads((original_dir/'manifest.json').read_bytes())
        for omission in (True,False):
            forged=deepcopy(document)
            if omission:forged['files']=[r for r in forged['files'] if r['path']!='tool.py']
            else:forged['declaration']['capabilities']['trim']['does']='Different contract'
            identity=sha(rfc8785.dumps(forged));destination=self.host.store/'releases'/identity
            shutil.copytree(original_dir,destination)
            (destination/'manifest.json').write_bytes(rfc8785.dumps(forged))
            with self.assertRaises(CCError) as error:self.host.release(identity)
            self.assertIn(error.exception.code,{'INVALID_RELEASE','DIGEST_MISMATCH'})

    def test_running_receipt_with_requested_checks_matches_schema(self):
        import threading
        started,finish=threading.Event(),threading.Event()
        def delegate(packet,context):
            started.set();finish.wait(5)
            return {'outcome':'ok','outputs':{'trimmed':'x'}}
        source=self.root/'bundle';shutil.copytree(ROOT/'protocol_examples/trim',source)
        raw=load(source/'cc.yaml');raw['bindings']={'default':{'kind':'delegate','agent':'worker'}}
        (source/'cc.yaml').write_text(json.dumps(raw),encoding='utf-8')
        self.host.delegates['worker']=delegate
        release=self.host.prepare(source);result=[]
        worker=threading.Thread(target=lambda: result.append(self.host.call(release,'trim',{'text':'x'},key='progress',checks=['optional'])))
        worker.start()
        try:
            self.assertTrue(started.wait(5))
            progress=self.host.status('progress')
            self.assertEqual(progress['assessment']['verdict'],'pending')
            validate('messages.schema.json',progress,'receipt')
        finally:
            finish.set();worker.join(5)
        validate('messages.schema.json',result[0],'receipt')

    def test_rfc8785_number_vector(self):
        self.assertEqual(rfc8785.dumps({'n':1e-7,'a':1.0}),b'{"a":1,"n":1e-7}')


if __name__=='__main__':unittest.main()
