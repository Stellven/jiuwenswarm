"""Prepared lock tests use reviewed literal pins, not live package resolution."""
import unittest
from jiuwenswarm.research.environment import EnvironmentError, parse_requirements, verify_inventory, verify_provisioned_inventory


class EnvironmentTests(unittest.TestCase):
    def test_source_package_receipt_requires_exact_installed_locked_and_verified_hash(self):
        expected = {'unit-pkg': '1.0'}
        row = {'name': 'unit-pkg', 'locked_version': '1.0', 'installed_version': '1.0', 'hash_verified': True}
        verify_provisioned_inventory(expected, [row])
        for changed in [dict(row, locked_version='2.0'), dict(row, installed_version='2.0'),
                        dict(row, hash_verified=False), {'name': 'unit-pkg', 'version': '1.0'}]:
            with self.assertRaises(EnvironmentError): verify_provisioned_inventory(expected, [changed])
        with self.assertRaises(EnvironmentError): verify_provisioned_inventory(expected, [row, row])

    def test_exact_pins_only_and_stdlib(self):
        self.assertEqual(parse_requirements(b'# stdlib only\n'), {})
        self.assertEqual(parse_requirements(b'numpy==2.0.0\n'), {'numpy': '2.0.0'})
        for text in [b'numpy>=2', b'numpy==2.*', b'x @ https://example.invalid/a',
                     b'--index-url https://example.invalid', b'x==1\nx==1', b'x==1; python_version>"3"']:
            with self.assertRaises(EnvironmentError):
                parse_requirements(text)

    def test_inventory_exact_not_subset(self):
        expected = {'numpy': '2.0.0'}
        verify_inventory(expected, [{'name': 'numpy', 'version': '2.0.0'}])
        for observed in [[], [{'name': 'numpy', 'version': '2.0.1'}],
                         [{'name': 'numpy', 'version': '2.0.0'}, {'name': 'evil', 'version': '1'}]]:
            with self.assertRaises(EnvironmentError):
                verify_inventory(expected, observed)
