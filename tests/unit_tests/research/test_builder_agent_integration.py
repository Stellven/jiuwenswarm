import unittest

from jiuwenswarm.research.capsules.builder_agent import _public_task
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


if __name__ == '__main__':
    unittest.main()
