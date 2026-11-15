"""Frozen workflow libraries remain data across portable replay.

The isolated transport fixture contains real retained files, not a product run.
No fixture assertion upgrades an older recording or dispatches an executor.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from jiuwenswarm.software_factory.contracts import Stage, StageFailure
from jiuwenswarm.software_factory.provenance import capture_recipe, verify_recipe
from jiuwenswarm.software_factory.recordings import RecordingsStore
from jiuwenswarm.software_factory.replay_export import ReplayExportError, load_recording
from jiuwenswarm.software_factory.workflow_recording import canonical_workflow_bytes, workflow_library_sha256

import test_recordings as fixtures


def never_execute(ctx, inputs):
    raise AssertionError('Frozen workflow transport tests must not execute a stage')


class WorkflowLibraryRecordingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.PortableRecordingsTests(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.stages = [
            Stage('construct', 'Construct source', 'construction', 'source_generation', {},
                  {'source': 'construction.cpp', 'package': 'construction.package'}, never_execute),
            Stage('inspect', 'Inspect source', 'verification', 'source_check', {'source': 'construction.cpp'},
                  {'verified': 'construction.cpp'}, never_execute),
        ]
        self.catalog = [stage.serializable() for stage in self.stages]
        definition = {'id': 'source-project', 'name': 'Source project', 'inputs': {}, 'stages': [
            {'id': 'construct', 'stage_id': 'construct', 'bindings': {}},
            {'id': 'inspect', 'stage_id': 'inspect',
             'bindings': {'source': {'source': 'construct', 'port': 'source'}}},
        ], 'outputs': {'package': {'source': 'construct', 'port': 'package'},
                      'verified': {'source': 'inspect', 'port': 'verified'}}}
        workflow = {'id': 'factory', 'name': 'Factory', 'inputs': {}, 'subworkflows': [
            {'id': 'build', 'definition': definition['id'], 'bindings': {}}
        ], 'outputs': {'package': {'source': 'build', 'port': 'package'}}}
        references = []
        for stage in self.stages:
            path = 'factory/build/' + stage.id
            sibling = 'factory/build/' + ('inspect' if stage.id == 'construct' else 'construct')
            origin = {'schema': 'factory.pool.origin.v1', 'full_ref': path, 'parent_ref': 'factory/build',
                      'canonical_stage_id': stage.id, 'parent_definition_id': definition['id'],
                      'parent_definition_hash': workflow_library_sha256(definition),
                      'selected_refs': [path], 'all_sibling_refs': [sibling], 'unselected_sibling_refs': [sibling]}
            references.append({'path': path, 'stage_id': stage.id, 'entrypoint': stage.serializable()['entrypoint'],
                               'inputs': stage.inputs, 'outputs': stage.outputs, 'pool_origin': origin})
        self.library = {'schema': 'factory.workflow.library.v1', 'workflows': [workflow],
                        'subworkflows': [definition], 'stage_refs': references}

    def retain(self, library=None):
        library = self.library if library is None else library
        run = self.fixture.run
        recipe = {key: value for key, value in run['recipe'].items()
                  if key not in {'manifest_path', 'manifest_sha256'}}
        catalog_raw = canonical_workflow_bytes(self.catalog)
        Path(recipe['catalog_path']).write_bytes(catalog_raw)
        recipe['catalog_sha256'] = fixtures.digest(catalog_raw)
        path = self.fixture.run_dir / 'recipe' / 'workflow-library.json'
        raw = canonical_workflow_bytes(library)
        path.write_bytes(raw)
        recipe.update(workflow_catalog_path=str(path), workflow_catalog_sha256=fixtures.digest(raw))
        manifest_path = self.fixture.run_dir / 'recipe' / 'manifest.json'
        manifest_raw = canonical_workflow_bytes(recipe)
        manifest_path.write_bytes(manifest_raw)
        run['recipe'] = {**recipe, 'manifest_path': str(manifest_path),
                         'manifest_sha256': fixtures.digest(manifest_raw)}
        run.update(workflow_catalog=deepcopy(library), workflow_catalog_sha256=fixtures.digest(raw))
        self.save()
        return path

    def attach_origin(self):
        run = self.fixture.run
        origin = deepcopy(self.library['stage_refs'][0]['pool_origin'])
        for node in [run['nodes'][0], self.fixture.events[0]['payload']['nodes'][0]]:
            node.update(workflow_path=origin['full_ref'], pool_origin=deepcopy(origin))
        self.save()

    def save(self):
        fixtures.write_json(self.fixture.run_dir / 'run.json', self.fixture.run)
        (self.fixture.run_dir / 'events.jsonl').write_text(
            ''.join(json.dumps(event) + '\n' for event in self.fixture.events))

    def test_capture_retains_full_canonical_library_and_rejects_changed_file(self):
        recipe = capture_recipe(self.fixture.root / 'captured-run', self.stages,
                                {'goals': ['construction.package']}, workflow_catalog=self.library)
        raw = Path(recipe['workflow_catalog_path']).read_bytes()
        self.assertEqual(raw, canonical_workflow_bytes(self.library))
        self.assertEqual(recipe['workflow_catalog_sha256'], hashlib.sha256(raw).hexdigest())
        verify_recipe(recipe)
        Path(recipe['workflow_catalog_path']).chmod(0o644)
        Path(recipe['workflow_catalog_path']).write_bytes(raw + b' ')
        with self.assertRaises(StageFailure):
            verify_recipe(recipe)

    def test_actual_production_library_is_retained_before_first_task_event(self):
        from jiuwenswarm.software_factory.catalog import stage_catalog
        from jiuwenswarm.software_factory.engine import Execution
        execution = Execution(self.fixture.root / 'pre-task', {'goals': []}, stage_catalog())
        snapshot = execution.result()
        self.assertEqual(snapshot['sequence'], 0)
        self.assertFalse(execution.events_path.exists())
        library = snapshot['workflow_catalog']
        self.assertEqual(library, execution.registry.snapshot())
        self.assertEqual(snapshot['workflow_catalog_sha256'], workflow_library_sha256(library))
        raw = Path(snapshot['recipe']['workflow_catalog_path']).read_bytes()
        self.assertEqual(raw, canonical_workflow_bytes(library))
        self.assertEqual(snapshot['recipe']['workflow_catalog_sha256'], snapshot['workflow_catalog_sha256'])
        parents = {row['id']: row for row in library['subworkflows']}
        for name in ('function_extraction-function_extraction', 'scalar_implementation-scalar_lowering',
                     'cooperative_implementation-cooperative_lowering'):
            self.assertGreaterEqual(len(parents[name]['stages']), 2)
        self.assertLessEqual(datetime.fromisoformat(snapshot['recipe']['captured_at']),
                             datetime.fromisoformat(snapshot['created_at']))

    def test_portable_library_exact_after_original_deleted_without_registry_or_execution(self):
        self.retain()
        with fixtures.no_factory_execution():
            self.fixture.export()
        shutil.rmtree(self.fixture.run_dir.parent)
        with fixtures.no_factory_execution(), patch(
                'jiuwenswarm.software_factory.workflow_definitions.WorkflowRegistry',
                side_effect=AssertionError('Replay consulted current workflow definitions')):
            store = RecordingsStore(self.fixture.store_dir)
            view = store.get(self.fixture.run_id, 'alice')
            self.assertEqual(view['workflow_catalog'], self.library)
            self.assertEqual(view['run']['workflow_catalog'], self.library)
            self.assertEqual(view['provenance']['workflow_catalog_sha256'], workflow_library_sha256(self.library))
            self.assertEqual(store.evidence(self.fixture.run_id, 'workflow-library.json', 'alice'),
                             canonical_workflow_bytes(self.library))

    def test_legacy_recording_never_gains_current_library(self):
        with fixtures.no_factory_execution():
            self.fixture.export()
            store = RecordingsStore(self.fixture.store_dir)
            self.assertNotIn('workflow_catalog', store.get(self.fixture.run_id, 'alice'))
            with self.assertRaises(FileNotFoundError):
                store.evidence(self.fixture.run_id, 'workflow-library.json', 'alice')
        self.fixture.run['workflow_catalog'] = self.library
        self.save()
        with self.assertRaises(ReplayExportError):
            load_recording(self.fixture.run_dir)

    def test_inline_and_retained_library_hashes_must_match(self):
        path = self.retain()
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaises(ReplayExportError):
            load_recording(self.fixture.run_dir)
        self.retain()
        self.fixture.run['workflow_catalog']['workflows'][0]['name'] = 'Rewritten'
        self.save()
        with self.assertRaises(ReplayExportError):
            load_recording(self.fixture.run_dir)

    def test_rehashed_invalid_stage_contracts_and_forward_bindings_fail_closed(self):
        for mutation in ('entrypoint', 'port-type', 'forward-binding', 'parent-hash'):
            with self.subTest(mutation=mutation):
                library = deepcopy(self.library)
                if mutation == 'entrypoint':
                    library['stage_refs'][0]['entrypoint'] = 'invented:executor'
                elif mutation == 'port-type':
                    library['stage_refs'][1]['inputs']['source'] = 'invented.kind'
                elif mutation == 'forward-binding':
                    library['subworkflows'][0]['stages'][0]['bindings'] = {'source': {'source': 'inspect', 'port': 'verified'}}
                else:
                    library['stage_refs'][0]['pool_origin']['parent_definition_hash'] = '0' * 64
                self.retain(library)
                with fixtures.no_factory_execution(), self.assertRaises(ReplayExportError):
                    load_recording(self.fixture.run_dir)

    def test_selected_and_unselected_sibling_receipts_cannot_be_spoofed(self):
        self.retain()
        self.attach_origin()
        self.fixture.run['nodes'][0]['pool_origin']['unselected_sibling_refs'] = []
        self.save()
        with self.assertRaises(ReplayExportError):
            load_recording(self.fixture.run_dir)

    def test_known_full_reference_cannot_lose_its_recorded_origin(self):
        self.retain()
        self.attach_origin()
        del self.fixture.run['nodes'][0]['pool_origin']
        self.save()
        with self.assertRaises(ReplayExportError):
            load_recording(self.fixture.run_dir)

    def test_claimed_selected_sibling_requires_actual_selection_scope(self):
        self.retain()
        self.attach_origin()
        origin = self.fixture.run['nodes'][0]['pool_origin']
        origin['selected_refs'].append('factory/build/inspect')
        origin['unselected_sibling_refs'] = []
        self.save()
        with self.assertRaises(ReplayExportError):
            load_recording(self.fixture.run_dir)

    def test_expanded_selection_matches_actual_node_and_declared_partial_scope(self):
        self.retain()
        self.attach_origin()
        node = self.fixture.run['nodes'][0]
        origin = node['pool_origin']
        graph = {'path': origin['full_ref'], 'instance_id': 'selected', 'inputs': {},
                 'nodes': [{'id': 'selected/' + origin['full_ref'], 'stage_id': node['stage_id'],
                            'workflow_path': origin['full_ref'], 'input_bindings': {},
                            'pool_origin': deepcopy(origin)}], 'edges': [], 'outputs': {}}
        receipt = {'path': graph['path'], 'instance_id': graph['instance_id'], 'pool_origin': deepcopy(origin)}
        node.update(workflow_selection=deepcopy(graph), workflow_selections=[receipt])
        payload = {'path': graph['path'], 'instance_id': graph['instance_id'], 'graph': graph,
                   'pool_origins': [{**deepcopy(origin), 'node_id': node['id']}],
                   'workflow_catalog_sha256': workflow_library_sha256(self.library)}
        self.fixture.events.insert(0, {'sequence': 1, 'time': self.fixture.events[0]['time'],
                                       'type': 'workflow.expanded', 'node_id': None, 'payload': payload})
        for index, event in enumerate(self.fixture.events, 1):
            event['sequence'] = index
        self.fixture.run['sequence'] = len(self.fixture.events)
        self.save()
        with fixtures.no_factory_execution():
            self.assertEqual(load_recording(self.fixture.run_dir)['workflow_catalog'], self.library)
        # A partial-import claim is not independently proven by its own list of
        # excluded siblings. Removing all selection observations must fail.
        original_events = deepcopy(self.fixture.events)
        original_node = deepcopy(node)
        self.fixture.events.pop(0)
        for index, event in enumerate(self.fixture.events, 1):
            event['sequence'] = index
        self.fixture.run['sequence'] = len(self.fixture.events)
        node.pop('workflow_selections')
        node.pop('workflow_selection')
        self.save()
        with self.assertRaises(ReplayExportError):
            load_recording(self.fixture.run_dir)
        self.fixture.events = original_events
        self.fixture.run['nodes'][0] = original_node
        self.fixture.run['sequence'] = len(original_events)
        payload = self.fixture.events[0]['payload']
        payload['pool_origins'][0]['selected_refs'].append('factory/build/inspect')
        payload['pool_origins'][0]['unselected_sibling_refs'] = []
        self.save()
        with self.assertRaises(ReplayExportError):
            load_recording(self.fixture.run_dir)


if __name__ == '__main__':
    unittest.main()
