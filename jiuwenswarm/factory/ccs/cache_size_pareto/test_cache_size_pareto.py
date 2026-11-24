import unittest

from cache_size_pareto import SCHEDULE, identity, summarize


def ref(key):
    return dict(artifact_id=key, sha256=identity(key))


def launch(name, budget, role, values):
    return dict(label=name, requested_mib=budget, allocated_mib=budget - 10, role=role,
                source_commit='1' * 40, binary_sha256='2' * 64, load_s=90,
                seed_startup=dict(seeds=100, initial_h2d_bytes=4096, init_us=1_200_000, charged_bound=8192) if role == 'on' else None,
                matching=dict(model_sha256='3' * 64, regions_sha256='4' * 64, prompts_sha256='5' * 64,
                              profile_family_sha256='6' * 64, common_argv=['-m', 'fixed.gguf'],
                              effective_settings={'n_ctx': 4096}, source_reset='file-specific DONTNEED',
                              scope_controls=dict(memory_max_bytes=100 * 1024**3, swap_max_bytes=0,
                                                  oom_group=1, cpu_max='800000 100000', affinity=list(range(8)))),
                receipts={key: ref(name + key) for key in ('start', 'stop', 'scope', 'protocol', 'conditioning', 'log', 'load')},
                samples=[dict(position=index, prompt_tokens=size, pair=pair, phase=phase, discard=phase == 'warmup',
                              ttft_s=200 if phase == 'warmup' else values[size][0], decode_tps=values[size][1],
                              greedy_hashes=['7' * 64, '8' * 64], result=ref(f'{name}-{index}'))
                         for index, (size, phase, pair) in enumerate(SCHEDULE, 1)])


def packet(*rows):
    return dict(schema='spark-cache-pareto-input/1', sources=[dict(analysis=ref('analysis'), verification=ref('verify'),
                                                                  scope_authority={'task_id': 'test'}, launches=list(rows))])


class ParetoTests(unittest.TestCase):
    def test_direction_per_size_and_extra_capacity(self):
        a = launch('stock', 30720, 'equivalent-stock', {512: (10, 9), 2048: (30, 8)})
        b = launch('on', 30720, 'on', {512: (8, 9), 2048: (28, 7)})
        c = launch('on60', 61440, 'on', {512: (9, 13), 2048: (20, 10)})
        row, = summarize(packet(a, b, c))['cohorts']
        stock, on, over = [cell['arm_id'] for cell in row['arms']]
        front_512, front_2048 = row['fronts']
        self.assertEqual(front_512['requested_sweep'], [on])
        self.assertEqual(front_512['all_measured'], [on, over])
        self.assertEqual(front_2048['requested_sweep'], [stock, on])
        self.assertEqual(front_2048['all_measured'], [over])
        self.assertEqual(row['arms'][1]['measurements']['512']['ttft_s'],
                         dict(count=5, minimum=8, median=8, maximum=8))
        self.assertEqual(row['arms'][1]['startup']['seed_init_s']['median'], 1.2)
        self.assertEqual([c['treatment_status'] for c in row['requested_capacity_coverage']], ['absent', 'measured', 'absent'])
        self.assertEqual(row['requested_capacity_coverage'][1]['same_allocation_controls'][0]['stock_ids'], [stock])
        self.assertEqual(row['requested_capacity_coverage'][1]['same_allocation_controls'][0]['off_status'], 'absent')

    def test_ties_and_observed_capacity(self):
        a = launch('on', 30720, 'on', {512: (8, 9), 2048: (28, 7)})
        b = launch('stock', 30720, 'equivalent-stock', {512: (8, 9), 2048: (28, 7)})
        b['allocated_mib'] -= 1
        row, = summarize(packet(a, b))['cohorts']
        self.assertEqual(len(row['fronts'][0]['requested_sweep']), 2)
        self.assertEqual(row['requested_capacity_coverage'][1]['same_allocation_controls'][0]['stock_status'], 'absent')

    def test_mismatched_runtime_and_invalid_receipts(self):
        a = launch('a', 15360, 'on', {512: (8, 9), 2048: (28, 7)})
        b = launch('b', 46080, 'on', {512: (8, 9), 2048: (28, 7)})
        b['matching']['effective_settings']['n_ctx'] = 5120
        self.assertEqual(len(summarize(packet(a, b))['cohorts']), 2)
        with self.assertRaisesRegex(ValueError, 'more than once'):
            summarize(packet(a, a))
        b['samples'][0]['discard'] = False
        with self.assertRaisesRegex(ValueError, 'warmup'):
            summarize(packet(b))


if __name__ == '__main__':
    unittest.main()
