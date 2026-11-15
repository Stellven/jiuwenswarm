"""Historical path ownership does not depend on the replay host operating system."""
from pathlib import PurePosixPath, PureWindowsPath
import unittest

from jiuwenswarm.software_factory.recorded_paths import (
    historical_basename, historical_child, historical_root, validate_historical_member,
)


class HistoricalPathTests(unittest.TestCase):
    def test_absolute_roots_keep_their_historical_platform_flavor(self):
        roots = [('/runs/r1', PurePosixPath),
                 (r'C:\runs\r1', PureWindowsPath),
                 ('C:/runs/r1', PureWindowsPath),
                 (r'\\server\share\runs\r1', PureWindowsPath)]
        for value, expected in roots:
            with self.subTest(value=value):
                root = historical_root(value)
                self.assertIsInstance(root, expected)
                self.assertTrue(root.is_absolute())

    def test_invalid_roots_are_rejected_without_host_filesystem_resolution(self):
        values = ['', 'runs/r1', '../runs/r1', '/runs/../r1',
                  r'C:relative', 'C:', r'\runs\r1',
                  r'C:\runs\..\r1', '/runs/\x00r1',
                  r'\\?\C:\runs\r1', r'\\.\C:\runs\r1']
        for value in values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                historical_root(value)

    def test_posix_owned_paths_and_relative_evidence_are_accepted(self):
        root = historical_root('/runs/r1')
        values = ['run.json', 'events.jsonl', 'recipe/source/stage.py',
                  '/runs/r1/stages/n1/output.cpp']
        for value in values:
            with self.subTest(value=value):
                result = validate_historical_member(root, value)
                self.assertIsInstance(result, PurePosixPath)
        self.assertEqual(str(root), '/runs/r1')

    def test_posix_outside_traversal_and_foreign_windows_anchors_are_rejected(self):
        values = ['/runs/r10/output.cpp', '/other/r1/output.cpp',
                  '../run.json', 'recipe/../run.json', '/runs/r1/a/../output.cpp',
                  r'C:\runs\r1\output.cpp', 'C:/runs/r1/output.cpp',
                  r'\\server\share\runs\r1\output.cpp', r'recipe\stage.py',
                  r'recipe\..\output.cpp']
        for value in values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_historical_member('/runs/r1', value)

    def test_windows_owned_paths_follow_windows_case_and_separator_rules(self):
        values = [r'C:\runs\r1\stages\output.cpp', 'c:/RUNS/r1/stages/output.cpp',
                  'run.json', r'recipe\source\stage.py', 'recipe/source/stage.py']
        for value in values:
            with self.subTest(value=value):
                result = validate_historical_member(r'C:\runs\r1', value)
                self.assertIsInstance(result, PureWindowsPath)

    def test_windows_outside_drive_relative_root_relative_and_ads_are_rejected(self):
        values = [r'D:\runs\r1\output.cpp', r'C:\runs\r10\output.cpp',
                  r'C:runs\r1\output.cpp', r'\runs\r1\output.cpp',
                  '/runs/r1/output.cpp', '../output.cpp', r'recipe\..\output.cpp',
                  r'C:\runs\r1\recipe\..\output.cpp',
                  'output.cpp:private', r'C:\runs\r1\output.cpp:private',
                  r'\\server\share\runs\r1\output.cpp',
                  r'\\?\C:\runs\r1\output.cpp']
        for value in values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_historical_member(r'C:\runs\r1', value)

    def test_unc_paths_require_the_original_server_share_and_owned_subtree(self):
        root = r'\\server\share\runs\r1'
        accepted = [r'\\server\share\runs\r1\artifact.zip',
                    r'\\SERVER\SHARE\RUNS\R1\artifact.zip', 'run.json']
        for value in accepted:
            with self.subTest(accepted=value):
                self.assertIsInstance(validate_historical_member(root, value), PureWindowsPath)
        rejected = [r'\\other\share\runs\r1\artifact.zip',
                    r'\\server\other\runs\r1\artifact.zip',
                    r'\\server\share\runs\r10\artifact.zip',
                    r'\runs\r1\artifact.zip', r'..\artifact.zip']
        for value in rejected:
            with self.subTest(rejected=value), self.assertRaises(ValueError):
                validate_historical_member(root, value)

    def test_license_join_and_download_basename_use_historical_flavor(self):
        cases = [('/runs/r1/source', '/runs/r1/source/LICENSE',
                  '/runs/r1/stages/huawei_native_strata.zip'),
                 (r'C:\runs\r1\source', r'C:\runs\r1\source\LICENSE',
                  r'C:\runs\r1\stages\huawei_native_strata.zip'),
                 (r'\\server\share\r1\source', r'\\server\share\r1\source\LICENSE',
                  r'\\server\share\r1\stages\huawei_native_strata.zip')]
        for source, license_path, artifact in cases:
            with self.subTest(source=source):
                self.assertEqual(historical_child(source, 'LICENSE'), license_path)
                self.assertEqual(historical_basename(artifact), 'huawei_native_strata.zip')

    def test_original_member_strings_are_not_mutated_by_lexical_validation(self):
        original = 'c:/RUNS/r1/stages/output.cpp'
        before = original.encode('utf-8')
        validate_historical_member(r'C:\runs\r1', original)
        self.assertEqual(original.encode('utf-8'), before)


if __name__ == '__main__':
    unittest.main()
