import json
from importlib.resources import files
from pathlib import Path
import tempfile
import unittest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.local_profile import _screening_static_template
from jiuwenswarm.research.screening_static_capture import capture_static_template
from jiuwenswarm.research.state import SQLiteRunStore


class StaticCaptureTests(unittest.TestCase):
    def test_actual_compiler_asset_preparation_retains_historical_planning_bytes(self):
        import asyncio
        import hashlib
        from jiuwenswarm.research.compiler import prepare_compiler_assets
        with tempfile.TemporaryDirectory() as temp:
            store=SQLiteRunStore(temp)
            try:
                assets=asyncio.run(prepare_compiler_assets(store))
                self.assertIn('planner',assets)
                current=Path('jiuwenswarm/research/planning.py').read_bytes()
                # This source SHA is the unchanged authored HEAD planning file,
                # not a newly accepted or updated historical release pin.
                self.assertEqual(hashlib.sha256(current).hexdigest(), 'c9efce387ee062bac8bf27f4d1acfee925dfeff7eba5cb99fe9d23cf12405ee2')
            finally:store.close()
    def test_selected_only_snapshot_matches_approved_ref_and_rejects_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            store=SQLiteRunStore(temp)
            try:
                selected_ref=_screening_static_template(store,'m1-5')
                selected=store.read_record(selected_ref)
                # Only the selected exact pins appear; no m1-4 Screening entry.
                entries=[dict(n['cc'],max_limits=dict(n['limits'])) for n in selected['nodes']]
                sentinel={'id':'snapshot','sha256':'a'*64}
                class Library:
                    def snapshot(self):return sentinel
                original_read=store.read_record
                store.read_record=lambda ref,**kw: {'entries':entries} if ref==sentinel else original_read(ref,**kw)
                self.assertEqual(capture_static_template(store,Library(),screening_version='m1-5',expected_ref=selected_ref),selected_ref)
                with self.assertRaisesRegex(ResearchError,'Approved configuration names another'):
                    capture_static_template(store,Library(),screening_version='m1-5',expected_ref={'id':'wrong','sha256':'b'*64})
                with self.assertRaisesRegex(ResearchError,'exact eligible aggregate'):
                    capture_static_template(store,Library())
                entries[1]['max_limits']['model_calls']=0
                with self.assertRaisesRegex(ResearchError,'exact eligible aggregate'):
                    capture_static_template(store,Library(),screening_version='m1-5')
            finally:store.close()

    def test_default_legacy_bytes_and_unknown_version(self):
        with tempfile.TemporaryDirectory() as temp:
            store=SQLiteRunStore(temp)
            try:
                raw=files('jiuwenswarm.research_assets').joinpath('planner/static-template.json').read_bytes()
                template=json.loads(raw);entries=[dict(n['cc'],max_limits=dict(n['limits'])) for n in template['nodes']]
                sentinel={'id':'snapshot','sha256':'a'*64}
                class Library:
                    def snapshot(self):return sentinel
                original_read=store.read_record
                store.read_record=lambda ref,**kw: {'entries':entries} if ref==sentinel else original_read(ref,**kw)
                self.assertEqual(store.read_blob(capture_static_template(store,Library())),raw)
                for version in ('latest',None,[]):
                    with self.assertRaisesRegex(ResearchError,'Unsupported explicit Screening'):
                        capture_static_template(store,Library(),screening_version=version)
            finally:store.close()


if __name__=='__main__':unittest.main()
