from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from jiuwenswarm.ccv2.ccv2 import CCError, Host, normalize, service_entries, callable_entries


class UnifiedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.host = Host(self.root/'store')
        self.example = Path(__file__).parent/'examples/method_library'

    def tearDown(self): self.temp.cleanup()

    def test_material_only_needs_no_binding_or_execution_authority(self):
        release = self.host.prepare(self.example)
        declaration = self.host.release(release)[0]
        self.assertEqual(declaration['bindings'], {})
        self.assertEqual(declaration['capabilities'], {})
        material = self.host.material(release, 'method')
        self.assertIn(b'synthetic', self.host.artifact_path(material['artifact']).read_bytes())
        self.assertEqual(self.host.describe(release)['materials']['method']['path'], 'SKILL.md')

    def test_passive_release_is_immutable(self):
        import shutil
        bundle = self.root/'library'; shutil.copytree(self.example, bundle)
        release = self.host.prepare(bundle)
        before = self.host.material(release, 'method')
        (bundle/'SKILL.md').write_text('changed', encoding='utf-8')
        after = self.host.material(release, 'method')
        self.assertEqual(before['artifact'], after['artifact'])
        self.assertNotEqual(self.host.artifact_path(after['artifact']).read_bytes(), b'changed')

    def test_excluded_material_cannot_publish_broken_release(self):
        import yaml
        bundle = self.root/'broken'; (bundle/'.cc-state').mkdir(parents=True)
        (bundle/'.cc-state/notes.md').write_text('notes')
        declaration = {'cc':'2','id':'test.library','version':'1.0.0','materials':{'notes':{'path':'.cc-state/notes.md'}}}
        (bundle/'cc.yaml').write_text(yaml.safe_dump(declaration))
        with self.assertRaises(CCError) as error: self.host.prepare(bundle)
        self.assertEqual(error.exception.code, 'UNSEALED_MATERIAL')

    def test_obsolete_application_map_rejected(self):
        with self.assertRaises(CCError) as error:
            normalize({'cc':'2','id':'test.old','version':'1.0.0','applications':{}})
        self.assertEqual(error.exception.code, 'UNKNOWN_FIELD')

    def test_active_capability_still_needs_real_binding(self):
        with self.assertRaises(CCError) as error:
            normalize({'cc':'2','id':'test.unbound','version':'1.0.0','capabilities':{'search':{'does':'Search'}}})
        self.assertEqual(error.exception.code, 'MISSING_BINDING')

    def test_empty_package_and_unknown_mandatory_meanings_rejected(self):
        with self.assertRaises(CCError): normalize({'cc':'2','id':'test.empty','version':'1.0.0'})
        with self.assertRaises(CCError) as error:
            normalize({'cc':'2','id':'test.bad','version':'1.0.0','materials':{'x':{'path':'x','must_execute':True}}})
        self.assertEqual(error.exception.code, 'UNKNOWN_FIELD')

    def test_passive_content_is_not_an_implicit_tool(self):
        release = self.host.prepare(self.example)
        result = self.host.call(release, 'method', {})
        self.assertEqual(result['state'], 'blocked')
        self.assertEqual(result['reason'], 'UNKNOWN_CAPABILITY')


if __name__ == '__main__': unittest.main()
