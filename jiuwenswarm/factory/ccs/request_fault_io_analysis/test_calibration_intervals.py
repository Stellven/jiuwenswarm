"""Check exact progress matching, request resets, and process identity."""
import json
import unittest

from calibration_intervals import analyze


def sample(clock, progress, rate, tick=123):
    return {
        'schema': 'spark-tuner-decode-diagnostic/1',
        'last_logged_n_gen': progress, 'reported_tok_s': rate,
        'counters': {
            'utc': str(clock), 'monotonic_ns': clock * 10**9, 'end_monotonic_ns': clock * 10**9 + 10,
            'memory_stat': {'pgmajfault': clock}, 'io_stat': {}, 'host_disks': {}, 'errors': {},
            'processes': {'42': {'comm': 'llama-server', 'starttime_ticks': tick,
                                 'majflt': clock, 'io': {'read_bytes': clock * 4096}}},
        },
    }


def run(samples, progress):
    trace = b'\n'.join(json.dumps(row).encode() for row in samples)
    engine_log = '\n'.join(f'slot print_timing: id  0 | task {task} | n_gen = {count}, tg = {rate} t/s'
                           for task, count, rate in progress)
    return analyze(trace, engine_log, {})


class CalibrationIntervalTest(unittest.TestCase):
    def test_only_engine_matched_same_request_progress(self):
        samples = [sample(0, 100, 2), sample(30, 200, 3), sample(60, 75, 2.5), sample(90, 125, 4)]
        report = run(samples, [(0, 100, 2), (0, 200, 3), (2050, 75, 2.5), (2050, 125, 4)])
        self.assertEqual([row['task_id'] for row in report['rows']], [0, 2050])
        self.assertEqual(report['rows'][0]['process_read_bytes_per_logged_token'], 1228.8)
        self.assertEqual(report['excluded_intervals'][0]['snapshot_start'], 1)
        self.assertIsNone(report['ttft_s'])

    def test_ambiguous_and_pid_change_fail_closed(self):
        samples = [sample(0, 100, 2), sample(30, 200, 3), sample(60, 300, 4, tick=999)]
        with self.assertRaisesRegex(ValueError, 'No unambiguous intervals'):
            run(samples, [(0, 100, 2), (0, 200, 3), (0, 300, 4), (22, 100, 2)])


if __name__ == '__main__':
    unittest.main()
