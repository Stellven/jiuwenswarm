import json
from importlib.resources import files
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research.local_profile import _screening_static_template, capture_local_profile


class ScreeningCampaignSelectionTests(unittest.TestCase):
    def test_immutable_template_changes_only_screening_pin_and_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            store = SQLiteRunStore(temp)
            try:
                original = files('jiuwenswarm.research_assets').joinpath('planner/static-template.json').read_bytes()
                self.assertEqual(store.read_blob(_screening_static_template(store,'m1-4')),original)
                old = json.loads(original)
                new = store.read_record(_screening_static_template(store,'m1-5'))
                for before, after in zip(old['nodes'],new['nodes']):
                    if before['node_id']=='screening':
                        expected=dict(before,cc=after['cc'])
                        self.assertEqual(expected,after)
                        self.assertEqual(after['cc']['cc_version'],'m1-5')
                    else:
                        self.assertEqual(before,after)
                self.assertNotEqual(old['id'],new['id'])
                for key in old.keys()-{'id','template_name','nodes'}:
                    self.assertEqual(old[key],new[key])
            finally:
                store.close()

    def test_invalid_selection_and_legacy_refresh_rejected_before_custody(self):
        for version in ('latest','m1-7',None,[]):
            with self.assertRaisesRegex(ResearchError,'Unsupported explicit Screening'):
                capture_local_profile(None,'unused',screening_version=version)
        with self.assertRaisesRegex(ResearchError,'Checking-only refresh'):
            capture_local_profile(None,'unused',screening_version='m1-5',legacy_checking_refresh=True)

    def test_capture_pins_selection_and_existing_directory_cannot_drift(self):
        # Custody is separately tested on Linux; adapt only OS identity/mode
        # checks here so actual immutable profile capture also runs on Windows.
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); inputs=root/'input';inputs.mkdir()
            store=SQLiteRunStore(root/'state',input_root=inputs)
            try:
                with patch('jiuwenswarm.research.local_profile.os.geteuid',return_value=inputs.stat().st_uid,create=True), patch('jiuwenswarm.research.local_profile.stat.S_IMODE',return_value=0o700), patch('jiuwenswarm.research.bootstrap_gateway._protected_file',side_effect=lambda p:Path(p).read_bytes()):
                    profile=root/'operator'/'screening5'
                    result=capture_local_profile(store,profile,input_root=inputs,screening_version='m1-5',allow_missing_science=True)
                    binding=store.read_record(result['binding_ref'])
                    self.assertEqual(binding['protected_options']['screening_version'],'m1-5')
                    config=store.read_record(binding['configuration_ref'])
                    template=store.read_record(config['cc']['static_template_ref'])
                    self.assertEqual(next(n for n in template['nodes'] if n['node_id']=='screening')['cc']['cc_version'],'m1-5')
                    self.assertEqual(capture_local_profile(store,profile,input_root=inputs,screening_version='m1-5',allow_missing_science=True),result)
                    with self.assertRaisesRegex(ResearchError,'Frozen Screening release changed'):
                        capture_local_profile(store,profile,input_root=inputs,allow_missing_science=True)
            finally:
                store.close()


if __name__=='__main__':
    unittest.main()
