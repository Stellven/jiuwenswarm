"""Validate timestamp and identity checks and the difference between missing and zero."""
from copy import deepcopy
import unittest

from fault_io import analyze


class FaultIOTest(unittest.TestCase):
    def setUp(self):
        base = {
            'monotonic_ns': 0, 'end_monotonic_ns': 100,
            'memory_stat': {'pgfault': 16, 'pgmajfault': 4, 'file': 8192},
            'io_stat': {},
            'processes': {'42': {'comm': 'llama-server', 'starttime_ticks': 111, 'minflt': 44, 'majflt': 12,
                                 'io': {'read_bytes': 0}}},
            'host_disks': {'nvme0n1': {'dev': '259:0', 'read_bytes': 4096, 'reads': 8, 'sectors_read': 8}},
            'errors': {'/scope/io.stat': 'Unavailable'},
        }
        first = deepcopy(base)
        first['monotonic_ns'], first['end_monotonic_ns'] = 2 * 10**9, 2 * 10**9 + 200
        first['memory_stat'].update(pgfault=24, file=4096)
        first['processes']['42']['io']['read_bytes'] = 8192
        first['host_disks']['nvme0n1'].update(read_bytes=12288, reads=10, sectors_read=24)
        end = deepcopy(first)
        end['monotonic_ns'], end['end_monotonic_ns'] = 4 * 10**9, 4 * 10**9 + 200
        self.counters = {'schema': 'spark-request-resources/1', 'cgroup': '/scope',
                         'snapshots': {'start': base, 'first_token': first, 'end': end}}
        self.request = {'arm': 'A', 'ttft_s': 2, 'resource_windows_sha256': 'a' * 64}
        self.hashes = {'counters': 'a' * 64, 'request': 'b' * 64}

    def report(self):
        return analyze(self.counters, self.request, self.hashes)

    def test_scopes_and_normalization(self):
        report = self.report()
        rows = {(row['source'], row['counter']): row for row in report['rows']}
        self.assertEqual(rows['cgroup.memory.stat', 'pgfault']['per_ttft_second'], 4)
        self.assertEqual(rows['cgroup.memory.stat', 'pgmajfault']['delta'], 0)
        self.assertIsNone(rows['cgroup.memory.stat', 'workingset_refault_file']['delta'])
        self.assertEqual(rows['cgroup.memory.stat', 'file']['delta'], -4096)
        self.assertIsNone(rows['cgroup.memory.stat', 'file']['per_ttft_second'])
        self.assertEqual(rows['host.diskstats', 'read_bytes']['delta'], 8192)
        self.assertEqual(rows['process.io', 'read_bytes']['delta'], 8192)
        self.assertNotIn(('cgroup.io.stat', 'rbytes'), rows)
        self.assertFalse(report['windows']['to_first_token']['source_presence']['cgroup.io.stat']['start'])

    def test_replaced_pid_and_counter_decline(self):
        first = self.counters['snapshots']['first_token']
        first['processes']['42']['starttime_ticks'] += 1
        first['memory_stat']['pgfault'] = 3
        rows = {(row['source'], row['counter']): row for row in self.report()['rows']}
        self.assertEqual(rows['process.io', 'read_bytes']['status'], 'identity_changed')
        self.assertIsNone(rows['process.io', 'read_bytes']['delta'])
        self.assertEqual(rows['cgroup.memory.stat', 'pgfault']['status'], 'decreased')

    def test_missing_first_token_keeps_whole_request(self):
        del self.counters['snapshots']['first_token']
        self.request['ttft_s'] = None
        report = self.report()
        self.assertEqual(report['windows']['to_first_token']['status'], 'boundary_unavailable')
        self.assertEqual(report['windows']['whole_request']['status'], 'observed')
        self.assertEqual(report['rows'], [])

    def test_rejects_mismatched_digest_and_overlap(self):
        self.request['resource_windows_sha256'] = 'c' * 64
        with self.assertRaisesRegex(ValueError, 'same captured'):
            self.report()
        self.request['resource_windows_sha256'] = self.hashes['counters']
        self.counters['snapshots']['start']['end_monotonic_ns'] = 3 * 10**9
        with self.assertRaisesRegex(ValueError, 'overlap'):
            self.report()


if __name__ == '__main__':
    unittest.main()
