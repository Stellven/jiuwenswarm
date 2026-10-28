import asyncio
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from jiuwenswarm.research.compiler import prepare_compiler_assets,register_compiler_capsules
from jiuwenswarm.research.library import LibraryService
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import SQLiteRunStore


class RequirementsReleaseTests(unittest.TestCase):
    def test_real_registration_path_with_controlled_eligibility_no_model_dispatch(self):
        from jiuwenswarm.research.runner import Registry
        from jiuwenswarm.research.checks import CheckRegistry
        from jiuwenswarm.research.contracts import Principal
        from tests.unit_tests.research.controlled_assets import ControlledLibraryService
        with tempfile.TemporaryDirectory() as temp:
            store=SQLiteRunStore(temp)
            try:
                library=ControlledLibraryService(store)
                actor=Principal('operator',operations=frozenset({'verifier_assets','library_admit','library_standing'}))
                selected=asyncio.run(prepare_compiler_assets(store,requirements_version='m1-9'))
                installed=asyncio.run(register_compiler_capsules(Registry(),CheckRegistry(),library,store,actor,
                    activate=True,prepared_assets=selected,requirements_version='m1-9'))
                self.assertEqual(installed['requirements']['pin']['cc_version'],'m1-9')
            finally:store.close()

    def test_actual_preparation_association_and_exact_registration_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            store=SQLiteRunStore(temp)
            try:
                old=asyncio.run(prepare_compiler_assets(store))
                selected=asyncio.run(prepare_compiler_assets(store,requirements_version='m1-9'))
                new=selected['requirements'];base=old['requirements']
                self.assertEqual(base['declaration_ref']['sha256'],'dbebf7805ce253ca8cf1c44a291c50d032b2339d6a447ddd2559c416095e8475')
                self.assertEqual(new['declaration']['identity']['version_label'],'m1-9')
                self.assertEqual(new['runner_ref'],base['runner_ref'])
                self.assertEqual(new['bundle']['checks'],base['bundle']['checks'])
                LibraryService(store)._validate_association(new['declaration_ref'],new['bundle_ref'],new['profile_ref'])
                checked=asyncio.run(register_compiler_capsules(None,None,None,store,None,prepare_only=True,prepared_assets=selected,requirements_version='m1-9'))
                self.assertEqual(checked['requirements'],selected['requirements'])
                for stage in selected:
                    for key in ('declaration_ref','body_refs','runner_ref','profile_ref','bundle_ref'):
                        self.assertEqual(checked[stage][key],selected[stage][key])
                self.assertEqual(selected['intent'],old['intent'])
                self.assertEqual(selected['planner'],old['planner'])
                text=store.read_blob(new['body_refs']['research_assets/compiler/requirements_m1_9.txt']).decode()
                self.assertIn('WHOLE attributable object',text)
                self.assertIn('automatic_retries is a protected host execution rule',text)
                tampered=copy.deepcopy(selected);tampered['requirements']['runner_ref']=base['declaration_ref']
                with self.assertRaisesRegex(ResearchError,'differs from exact explicit release'):
                    asyncio.run(register_compiler_capsules(None,None,None,store,None,prepare_only=True,prepared_assets=tampered,requirements_version='m1-9'))
                with self.assertRaises(ResearchError):
                    asyncio.run(register_compiler_capsules(None,None,None,store,None,prepare_only=True,prepared_assets=selected))
            finally:store.close()

    def test_unknown_selection_rejected_and_old_carrier_prompt_pins_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            store=SQLiteRunStore(temp)
            try:
                for version in ('latest',None,[]):
                    with self.assertRaises(ResearchError):asyncio.run(prepare_compiler_assets(store,requirements_version=version))
                catalog=json.loads(Path('jiuwenswarm/research_assets/catalog.json').read_text())
                for row in catalog['capsules']['requirements']['body']:
                    self.assertEqual(hashlib.sha256((Path('jiuwenswarm')/row['path']).read_bytes()).hexdigest(),row['sha256'])
            finally:store.close()


if __name__=='__main__':unittest.main()
