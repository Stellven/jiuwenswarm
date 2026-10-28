import unittest

from jiuwenswarm.research.capsules.builder_agent import CLASSIFICATION_HARNESS, CLASSIFICATION_SYSTEM, SYSTEM, WORKSPACE_RULES, _public_task
from jiuwenswarm.research.pi_protocol import MAX_DIGITS, parse_pi_output, validate_pi_request


class BuilderAgentIntegrationTests(unittest.TestCase):
    def test_agent_context_is_limited_to_frozen_inputs_and_public_request(self):
        hidden = {'id': 'private', 'sha256': 'private-hash'}
        inputs = {
            'blueprint': {'id': 'frozen'},
            'lock': {'requirements_ref': {'id': 'requirements', 'sha256': 'h'}},
            'validation_resource': {'files': [{'artifact_ref': hidden}]},
            'baseline_resource': {'files': [{'artifact_ref': hidden}]},
        }
        public = {'schema': 'ai4r-pi-cases:1', 'digits': 8}
        task = _public_task(inputs, public, pi=True)
        self.assertEqual(set(task), {'blueprint', 'lock', 'public_validation', 'instructions', 'contract'})
        self.assertEqual(task['public_validation'], public)
        self.assertNotIn('private', repr(task))

    def test_public_pi_contract_bounds_and_closed_output(self):
        self.assertEqual(validate_pi_request({'schema': 'ai4r-pi-cases:1', 'digits': 0}), 0)
        self.assertEqual(validate_pi_request({'schema': 'ai4r-pi-cases:1', 'digits': MAX_DIGITS}), MAX_DIGITS)
        self.assertEqual(parse_pi_output('{"digits":4,"decimal":"3.1415"}', 4),
                         {'digits': 4, 'decimal': '3.1415'})
        for digits in (-1, MAX_DIGITS + 1, True):
            with self.assertRaises(ValueError):
                validate_pi_request({'schema': 'ai4r-pi-cases:1', 'digits': digits})
        with self.assertRaises(ValueError):
            parse_pi_output('{"digits":4,"decimal":"3.1415","extra":0}', 4)

    def test_instructions_exempt_tests_py_from_the_patch_file_limit(self):
        # r5g: the model read max_patch_files=1 as forbidding tests.py and stopped.
        for text in (SYSTEM, CLASSIFICATION_SYSTEM):
            self.assertIn(WORKSPACE_RULES, text)
        for needle in ('counts implementation files only', 'tests.py is a separate required development file',
                       'MUST write a nonempty tests.py', 'Do not call report_blocked because of max_patch_files'):
            self.assertIn(needle, WORKSPACE_RULES)

    def test_classification_instructions_state_the_statically_checked_harness_shape(self):
        self.assertIn(CLASSIFICATION_HARNESS, CLASSIFICATION_SYSTEM)
        self.assertIn('print(json.dumps({"predictions": predictions}, allow_nan=False))', CLASSIFICATION_SYSTEM)
        self.assertIn('requirements.txt is already in the workspace', CLASSIFICATION_SYSTEM)

    def test_pi_task_scope_does_not_forbid_tests_py(self):
        import inspect
        from jiuwenswarm.research import pi_task
        source = inspect.getsource(pi_task.capture_pi_task)
        self.assertIn('max_patch_files counts implementation files only', source)


if __name__ == '__main__':
    unittest.main()
