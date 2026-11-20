"""Real declaration examples plus isolated invalid-contract mutations."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from jiuwenswarm.software_factory.shared_pool import (
    normalize_cc, reference, validate_pool,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / 'docs/code/Missions/software-factory/shared-schema/pool.json'


class SharedPoolTests(unittest.TestCase):
    def setUp(self):
        self.pool = json.loads(EXAMPLES.read_text())
        self.index = {e['id']: e for e in self.pool['entries']}

    def test_actual_workflow_and_cc_declarations_share_one_schema(self):
        validate_pool(self.pool)
        self.assertEqual({e['origin']['system'] for e in self.pool['entries']}, {'workflow', 'cc'})
        self.assertEqual(sum(e['kind'] == 'collection' for e in self.pool['entries']), 16)

    def test_partial_extraction_parent_retains_both_real_children(self):
        parent = self.index['workflow:subworkflow/function_extraction-function_extraction']
        self.assertEqual([n['id'] for n in parent['composition']['nodes']], ['discover', 'extract'])
        self.assertEqual(parent['composition']['nodes'][1]['bindings']['discovery'],
                         {'node': 'discover', 'port': 'discovery'})
        stage = self.index['workflow:stage/source.bind_operation']
        self.assertIn(':bind_operation', stage['implementation']['entrypoint'])
        self.assertEqual(stage['inputs']['discovery']['semantic_type'], 'source.operations')
        self.assertFalse(stage['inputs']['discovery']['schema_known'])

    def test_material_only_cc_is_not_an_executable_graph(self):
        cc = self.index['cc:factory.components.expert_fill']
        self.assertEqual(cc['kind'], 'collection')
        self.assertNotIn('composition', cc)
        for ref in cc['members']:
            material = self.index[ref['id']]
            self.assertEqual(material['kind'], 'material')
            self.assertNotIn('implementation', material)
            self.assertEqual(len(material['material']['sha256']), 64)

    def test_cc_tool_retains_binding_effects_optional_ports_and_opaque_json(self):
        tool = self.index['cc:factory.builder/tool/submit']
        self.assertEqual(tool['implementation']['binding']['kind'], 'native')
        self.assertIn('{python}', tool['implementation']['binding']['command'])
        self.assertIn('process.exec', tool['requirements']['effects'])
        self.assertFalse(tool['inputs']['node_id']['required'])
        self.assertEqual(tool['inputs']['request']['transport'], 'value')
        self.assertFalse(tool['inputs']['request']['schema_known'])

    def test_duplicate_and_dangling_pinned_references_fail(self):
        self.pool['entries'].append(deepcopy(self.pool['entries'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            validate_pool(self.pool)
        self.pool['entries'].pop()
        self.index['cc:factory.builder']['members'][0]['version'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'Unknown pinned'):
            validate_pool(self.pool)

    def test_raw_declaration_tampering_fails(self):
        self.pool['entries'][0]['origin']['original']['name'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            validate_pool(self.pool)

    def test_artifact_kind_rename_cannot_satisfy_input(self):
        self.index['workflow:stage/source.bind_operation']['inputs']['discovery']['semantic_type'] = 'ascend.ops'
        with self.assertRaisesRegex(ValueError, 'Incompatible'):
            validate_pool(self.pool)

    def test_material_cannot_be_inserted_as_an_executable_child(self):
        parent = self.index['workflow:subworkflow/function_extraction-function_extraction']
        material = self.index['cc:factory.components.expert_fill/material/component']
        parent['composition']['nodes'][0]['capability'] = reference(material)
        with self.assertRaisesRegex(ValueError, 'not executable'):
            validate_pool(self.pool)

    def test_recursive_composition_is_rejected(self):
        parent = self.index['workflow:workflow/source_acquisition']
        parent['composition']['nodes'][0]['capability'] = reference(parent)
        with self.assertRaisesRegex(ValueError, 'cycle'):
            validate_pool(self.pool)

    def test_optional_output_cannot_guarantee_required_input(self):
        stage = self.index['workflow:stage/source.discover']
        stage['outputs']['discovery']['required'] = False
        for entry in self.pool['entries']:
            if entry['kind'] == 'composite':
                for port in entry['outputs'].values():
                    if port['semantic_type'] == 'source.operations':
                        port['required'] = False
        with self.assertRaisesRegex(ValueError, 'Optional output'):
            validate_pool(self.pool)

    def test_invalid_cc_binding_is_rejected_by_shared_schema(self):
        from jsonschema import ValidationError
        tool = self.index['cc:factory.builder/tool/submit']
        tool['implementation']['binding']['command'] = []
        with self.assertRaises(ValidationError):
            validate_pool(self.pool)

    def test_cc_defs_are_resolved_without_losing_optional_metadata(self):
        raw = deepcopy(self.index['cc:factory.builder']['origin']['original'])
        raw['defs'] = {'request': {'kind': 'json', 'optional': True, 'schema': {'type': 'object'}}}
        raw['capabilities']['submit']['takes']['request'] = '$request'
        origin = {k: v for k, v in self.index['cc:factory.builder']['origin'].items()
                  if k not in {'original', 'declaration_sha256'}}
        converted = normalize_cc(raw, origin, lambda path: b'unused')
        tool = next(e for e in converted if e['id'].endswith('/tool/submit'))
        self.assertFalse(tool['inputs']['request']['required'])
        self.assertTrue(tool['inputs']['request']['schema_known'])
        raw['defs']['request'] = '$request'
        with self.assertRaisesRegex(ValueError, 'cyclic'):
            normalize_cc(raw, origin, lambda path: b'unused')


if __name__ == '__main__':
    unittest.main()
