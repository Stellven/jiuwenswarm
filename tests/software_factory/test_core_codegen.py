"""Real production-source extraction and standalone C++ construction checks.

These exercise a source-derived CPU math module, not a full model or device.
Requires the acquired pinned STRATA repository and a real local C++ toolchain.
No model, device, compiler, process, or numerical-result test doubles are used.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import zipfile

SOURCE = Path(os.environ.get('STRATA_SOURCE', '/workspace/strata')).resolve()
PIN = '13eedf552417a6a791a7d13c6597e24300ee3a09'
TOOL = Path('/workspace/factory-runs/898700bb76154c07b9f60f48fe70adbf/stages/n19/1/toolchain/bin/cmake')


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def expected_router(logits, k, clamp=6.103515625e-05):
    """Independent oracle reproducing production float/double boundaries."""
    logits = [f32(value) for value in logits]
    maximum = max(logits)
    exponentials = [math.exp(float(value) - float(maximum)) for value in logits]
    total = 0.0
    for value in exponentials:
        total += value
    inverse = f32(1.0 / total)
    probabilities = [f32(value * inverse) for value in exponentials]
    ids = sorted(range(len(logits)), key=lambda index: (-probabilities[index], index))[:k]
    selected_sum = 0.0
    for index in ids:
        selected_sum += probabilities[index]
    denominator = max(selected_sum, clamp)
    return ids, [f32(probabilities[index] / denominator) for index in ids]


def command(argv, cwd=None):
    result = subprocess.run([str(value) for value in argv], cwd=cwd,
                            capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise AssertionError(f'Actual command failed ({result.returncode}): {argv!r}\n'
                             f'stdout:\n{result.stdout}\nstderr:\n{result.stderr}')
    return result


def build(project: Path, build_dir: Path):
    cmake = shutil.which('cmake') or (str(TOOL) if TOOL.is_file() else None)
    if not cmake:
        raise AssertionError('Actual CMake executable is required; no skipped build is a pass')
    command([cmake, '-S', project, '-B', build_dir, '-G', 'Unix Makefiles', '-DCMAKE_BUILD_TYPE=Release'])
    command([cmake, '--build', build_dir, '--parallel', '2'])
    binary = build_dir / 'strata_engine'
    if not binary.is_file() or binary.read_bytes()[:4] != b'\x7fELF':
        raise AssertionError('Generated project did not build a real strata_engine ELF')
    return binary


def execute(binary: Path, input_path: Path):
    result = command([binary, '--input', input_path])
    return json.loads(result.stdout)


def router_input(path: Path, logits, k):
    path.write_text(f'{len(logits)} {k}\n' + ' '.join(format(value, '.17g') for value in logits) + '\n')


class ProductionCoreConstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.is_dir():
            raise AssertionError(f'Actual acquired STRATA checkout is required: {SOURCE}')
        actual = command(['git', 'rev-parse', 'HEAD'], SOURCE).stdout.strip()
        if actual != PIN:
            raise AssertionError(f'Reviewed STRATA revision required: {PIN}, got {actual}')
        cls.core = importlib.import_module('jiuwenswarm.software_factory.core_codegen')
        cls.tmp = tempfile.TemporaryDirectory(prefix='factory-core-check-')
        cls.directory = Path(cls.tmp.name)
        cls.inventory = cls.core.extract_core(SOURCE, cls.directory / 'analysis', selected=['router'])
        cls.project = cls.directory / 'router-project'
        cls.metadata = cls.core.generate_project(cls.inventory, cls.project)
        cls.binary = build(cls.project, cls.directory / 'router-build')

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'tmp'):
            cls.tmp.cleanup()

    def test_extraction_binds_actual_production_source_and_hashes(self):
        value = self.inventory
        self.assertEqual(value['schema'], 'strata.core.ir.v1')
        self.assertEqual(value['commit_sha'], PIN)
        kernel = value['kernels']['router']
        path = SOURCE / kernel['path']
        self.assertEqual(kernel['path'], 'src/kernels/cuda/router_top10.cu')
        self.assertEqual(kernel['function'], 'router_top10_kernel')
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), kernel['source_sha256'])
        self.assertEqual(hashlib.sha256(kernel['source_code'].encode()).hexdigest(), kernel['function_sha256'])
        self.assertIn('exp((double) l[e] - (double) mx)', kernel['source_code'])
        self.assertIn('const float inv', kernel['source_code'])
        self.assertNotIn('expert_adapter_test.cpp', json.dumps(value))
        self.core.validate_core(value)

    def test_generated_source_contains_math_and_no_upstream_test_harness(self):
        generated = (self.project / 'src/strata_core.cpp').read_text()
        self.assertIn('exp(', generated)
        self.assertIn('6.103515625e-05', generated)
        for forbidden in ['expert_adapter_test.cpp', 'ReferenceOps', 's2_expert_scalar', 'max_abs_error', 'STRATA_SOURCE_DIR']:
            self.assertNotIn(forbidden, generated)
        self.assertNotIn(str(SOURCE), (self.project / 'CMakeLists.txt').read_text())

    def test_external_input_changes_actual_output_and_production_tie_order(self):
        path = self.directory / 'router.input'
        for logits, k in [([0.0] * 8, 3), ([1.0, 9.0, 9.0, -2.0], 2),
                          ([-11.0, -2.0, 0.5, 3.0, 4.0], 4),
                          ([0.0] * 511 + [1e-10], 1)]:
            with self.subTest(logits=len(logits), k=k):
                router_input(path, logits, k)
                result = execute(self.binary, path)
                ids, weights = expected_router(logits, k)
                self.assertEqual(result['ids'], ids)
                self.assertEqual(len(result['weights']), k)
                for actual, expected in zip(result['weights'], weights):
                    self.assertAlmostEqual(actual, expected, delta=2e-7)
        # Last expert has larger unrounded logits, but production probabilities tie as f32.
        router_input(path, [0.0] * 511 + [1e-10], 1)
        self.assertEqual(execute(self.binary, path)['ids'], [0])
        router_input(path, [0.0, 1.0, 2.0, 8.0], 1)
        self.assertEqual(execute(self.binary, path)['ids'], [3])

    def test_changed_source_hash_and_altered_extracted_body_fail_closed(self):
        changed_parameters = deepcopy(self.inventory['kernels']['router']['parameters'])
        changed_parameters[0]['name'] = 'tampered_binding'
        changed_extents = dict(self.inventory['kernels']['router']['tensor_extents'])
        changed_extents[next(iter(changed_extents))] = '1'
        for field, replacement in [('source_sha256', '0' * 64),
                                    ('function_sha256', '0' * 64),
                                    ('source_code', 'void router_top10_kernel() {}'),
                                    ('parameters', changed_parameters),
                                    ('tensor_extents', changed_extents),
                                    ('operation', 'rms_norm')]:
            with self.subTest(field=field):
                changed = deepcopy(self.inventory)
                changed['kernels']['router'][field] = replacement
                with self.assertRaises(ValueError):
                    self.core.generate_project(changed, self.directory / ('invalid-' + field))
        repository = self.directory / 'stale-source'
        command(['git', 'clone', '--shared', '--quiet', SOURCE, repository])
        inventory = self.core.extract_core(repository, self.directory / 'stale-analysis', selected=['router'])
        source = repository / 'src/kernels/cuda/router_top10.cu'
        source.write_text(source.read_text() + '\n// Real file changed after extraction.\n')
        with self.assertRaisesRegex(ValueError, 'Actual source/slice changed'):
            self.core.generate_project(inventory, self.directory / 'stale-project')

    def test_source_expression_change_changes_generated_math_and_result(self):
        repository = self.directory / 'changed-source'
        command(['git', 'clone', '--shared', '--quiet', SOURCE, repository])
        path = repository / 'src/kernels/cuda/router_top10.cu'
        original = path.read_text()
        needle = 'const double sc = fmax(s, 6.103515625e-05);'
        self.assertIn(needle, original)
        path.write_text(original.replace(needle, 'const double sc = fmax(s, 0.5);', 1))
        inventory = self.core.extract_core(repository, self.directory / 'changed-analysis', selected=['router'])
        project = self.directory / 'changed-project'
        self.core.generate_project(inventory, project)
        generated = (project / 'src/strata_core.cpp').read_text()
        self.assertIn('0.5', generated)
        self.assertNotEqual(generated, (self.project / 'src/strata_core.cpp').read_text())
        binary = build(project, self.directory / 'changed-build')
        input_path = self.directory / 'changed.input'
        router_input(input_path, [0.0] * 4, 1)
        result = execute(binary, input_path)
        self.assertEqual(result['ids'], [0])
        self.assertAlmostEqual(result['weights'][0], 0.5, delta=1e-7)
        self.assertAlmostEqual(execute(self.binary, input_path)['weights'][0], 1.0, delta=1e-7)

    def test_generated_package_rebuilds_without_upstream_source_or_old_build_tree(self):
        repository = self.directory / 'package-source'
        command(['git', 'clone', '--shared', '--quiet', SOURCE, repository])
        inventory = self.core.extract_core(repository, self.directory / 'package-analysis', selected=['router'])
        generated = self.directory / 'package-project'
        self.core.generate_project(inventory, generated)
        package = self.directory / 'source.zip'
        with zipfile.ZipFile(package, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path in generated.rglob('*'):
                if path.is_file():
                    archive.write(path, Path('standalone-source') / path.relative_to(generated))
        # Both the source checkout used for generation and the generated directory
        # disappear before compiling the extracted delivery package.
        shutil.rmtree(repository)
        shutil.rmtree(generated)
        extracted = self.directory / 'detached-package'
        extracted.mkdir()
        with zipfile.ZipFile(package) as archive:
            archive.extractall(extracted)
        project = extracted / 'standalone-source'
        # A self-contained project may only include its own headers/sources.
        for path in project.rglob('*'):
            if path.is_file() and path.suffix in {'.cpp', '.hpp', '.h', '.txt'}:
                self.assertNotIn(str(SOURCE), path.read_text())
                self.assertNotIn(str(repository), path.read_text())
                self.assertNotIn('add_subdirectory', path.read_text())
        binary = build(project, extracted / 'new-build')
        input_path = extracted / 'external.input'
        router_input(input_path, [3.0, 2.0, 1.0, 0.0], 2)
        result = execute(binary, input_path)
        self.assertEqual(result['ids'], [0, 1])
        self.assertTrue(all(math.isfinite(value) for value in result['weights']))

    def test_combined_production_scalar_math_consumes_external_tensors(self):
        inventory = self.core.extract_core(SOURCE, self.directory / 'combined-analysis')
        project = self.directory / 'combined-project'
        self.core.generate_project(inventory, project)
        generated = (project / 'src/strata_core.cpp').read_text()
        for name in ['swiglu', 'moe_combine']:
            # The actual production CUDA scalar body survives the index-to-loop transform.
            self.assertIn(inventory['kernels'][name]['semantic_ir']['scalar_body'], generated)
        binary = build(project, self.directory / 'combined-build')
        comparison = json.loads(command([binary.parent / 'strata_core_test']).stdout)
        self.assertGreater(comparison['outputs_compared'], 0)
        self.assertLessEqual(comparison['max_abs_error'], 1e-5)
        self.assertFalse(comparison['native_device_validated'])
        self.assertFalse(comparison['full_inference_validated'])
        logits, k, d = [1.0, 5.0, -2.0, 3.0], 2, 3
        gate = [-3.0, 0.0, 2.0, 1.0, -1.0, 0.25, 7.0, -0.1, 4.0, 0.5, 2.5, -4.0]
        up = [0.5, -1.0, 2.0, 3.0, 0.5, -2.0, 0.75, 4.0, 1.0, -0.5, 2.0, 1.25]
        shared = [0.2, -0.3, 0.4]
        ids, weights = expected_router(logits, k)
        parts = [f32(f32(float(f32(x)) / (1.0 + math.exp(-float(f32(x))))) * f32(y))
                 for x, y in zip(gate, up)]
        expected = []
        for j in range(d):
            total = 0.0
            for expert, weight in zip(ids, weights):
                total += float(weight) * float(parts[expert * d + j])
            expected.append(f32(total + f32(shared[j])))
        path = self.directory / 'combined.input'

        def write_input(shared_values):
            values = logits + gate + up + shared_values
            path.write_text(f'{len(logits)} {k} {d}\n' + ' '.join(format(x, '.17g') for x in values) + '\n')

        write_input(shared)
        actual = execute(binary, path)
        self.assertEqual(actual['ids'], ids)
        self.assertEqual(len(actual['output']), d)
        for value, reference in zip(actual['output'], expected):
            self.assertAlmostEqual(value, reference, delta=3e-7)
        write_input([value + 1.0 for value in shared])
        changed = execute(binary, path)
        for before, after in zip(actual['output'], changed['output']):
            self.assertAlmostEqual(after - before, 1.0, delta=3e-7)

    def test_production_arithmetic_and_selection_writes_are_actually_lowered(self):
        repository = self.directory / 'mutated-semantics'
        command(['git', 'clone', '--shared', '--quiet', SOURCE, repository])
        path = repository / 'src/kernels/cuda/router_top10.cu'
        source = path.read_text()
        mutations = [
            ('s_taken[ix] = 1;', 's_taken[ix] = 0;', 2, [0, 0], [0.5, 0.5]),
            ('weights[(size_t) t * k + i] / sc)', 'weights[(size_t) t * k + i] * sc)', 1, [0], [0.0625]),
        ]
        for index, (before, after, k, expected_ids, expected_weights) in enumerate(mutations):
            with self.subTest(source_change=after):
                self.assertIn(before, source)
                path.write_text(source.replace(before, after, 1))
                inventory = self.core.extract_core(repository, self.directory / f'mutated-analysis-{index}', selected=['router'])
                project = self.directory / f'mutated-project-{index}'
                self.core.generate_project(inventory, project)
                binary = build(project, self.directory / f'mutated-build-{index}')
                data = self.directory / f'mutated-{index}.input'
                router_input(data, [0.0] * 4, k)
                actual = execute(binary, data)
                self.assertEqual(actual['ids'], expected_ids)
                for value, expected in zip(actual['weights'], expected_weights):
                    self.assertAlmostEqual(value, expected, delta=1e-7)

    def test_renamed_production_router_is_discovered_and_executed(self):
        repository = self.directory / 'renamed-source'
        command(['git', 'clone', '--shared', '--quiet', SOURCE, repository])
        path = repository / 'src/kernels/cuda/router_top10.cu'
        path.write_text(path.read_text().replace('router_top10_kernel', 'factory_discovered_routing'))
        inventory = self.core.extract_core(repository, self.directory / 'renamed-analysis', selected=['factory_discovered_routing'])
        project = self.directory / 'renamed-project'
        self.core.generate_project(inventory, project)
        binary = build(project, self.directory / 'renamed-build')
        data = self.directory / 'renamed.input'
        router_input(data, [0.0] * 511 + [1e-10], 2)
        self.assertEqual(execute(binary, data)['ids'], [0, 1])

    def test_explicit_same_category_producers_invoke_distinct_lowered_functions(self):
        repository = self.directory / 'two-router-source'
        command(['git', 'clone', '--shared', '--quiet', SOURCE, repository])
        path = repository / 'src/kernels/cuda/router_top10.cu'
        alternate = self.inventory['kernels']['router']['source_code']
        alternate = alternate.replace('router_top10_kernel', 'factory_alternative_route', 1)
        alternate = alternate.replace('weights[(size_t) t * k + i] / sc)', 'weights[(size_t) t * k + i] * sc)', 1)
        path.write_text(path.read_text() + '\n' + alternate + '\n')
        inventory = self.core.extract_core(repository, self.directory / 'two-router-analysis',
                                           selected=['router_top10_kernel', 'factory_alternative_route'])
        self.assertEqual(len(inventory['kernels']), 2)
        project = self.directory / 'two-router-project'
        self.core.generate_project(inventory, project)
        binary = build(project, self.directory / 'two-router-build')
        data = self.directory / 'two-router.input'
        router_input(data, [0.0] * 4, 1)
        results = {}
        for name in ['router_top10_kernel', 'factory_alternative_route']:
            results[name] = json.loads(command([binary, '--operation', name, '--input', data]).stdout)
        self.assertAlmostEqual(results['router_top10_kernel']['weights'][0], 1.0, delta=1e-7)
        self.assertAlmostEqual(results['factory_alternative_route']['weights'][0], 0.0625, delta=1e-7)

    def construct_new_kernel(self, name, code):
        """Compile an isolated new source operation through live discovery."""
        repository = self.directory / (name + '-source')
        command(['git', 'clone', '--shared', '--quiet', SOURCE, repository])
        path = repository / 'src/kernels/cuda/factory_construction_test.cu'
        path.write_text(code)
        inventory = self.core.extract_core(repository, self.directory / (name + '-analysis'), selected=[name])
        self.assertTrue(any(record['function'] == name for record in inventory['kernels'].values()))
        project = self.directory / (name + '-project')
        self.core.generate_project(inventory, project)
        return inventory, build(project, self.directory / (name + '-build'))

    def test_new_affine_operation_is_discovered_from_source_and_consumes_scalars(self):
        name = 'fabric_affine_external'
        code = '''__global__ void fabric_affine_external(const float* x, float* y, int n, float scale, float bias) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;
    y[i] = x[i] * scale + bias;
}
'''
        inventory, binary = self.construct_new_kernel(name, code)
        self.assertEqual(inventory['cli']['mode'], 'elementwise')
        path = self.directory / 'affine.input'
        values = [float(index - 20) / 8.0 for index in range(67)]
        path.write_text('67 1.5 -0.25\n' + ' '.join(map(str, values)) + '\n')
        actual = execute(binary, path)['output']
        self.assertEqual(len(actual), len(values))
        for value, x in zip(actual, values):
            self.assertAlmostEqual(value, f32(f32(f32(x) * 1.5) - 0.25), delta=3e-7)
        path.write_text('67 -2.0 0.5\n' + ' '.join(map(str, values)) + '\n')
        changed = execute(binary, path)['output']
        self.assertNotEqual(actual, changed)
        for value, x in zip(changed, values):
            self.assertAlmostEqual(value, f32(f32(f32(x) * -2.0) + 0.5), delta=3e-7)

    def test_shared_memory_and_barriers_use_real_neighbor_values_and_block_isolation(self):
        _, binary = self.construct_new_kernel('fabric_neighbors', '''__global__ void fabric_neighbors(const float* x, float* y, int n) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    __shared__ float values[32];
    values[threadIdx.x] = i < n ? x[i] : 0.0f;
    __syncthreads();
    if (i < n) y[i] = values[(threadIdx.x + 1) & 31] - values[threadIdx.x];
}
''')
        path = self.directory / 'neighbors.input'
        for n in [64, 37]:
            values = [float(index * 3 + 1) for index in range(n)]
            path.write_text(str(n) + '\n' + ' '.join(map(str, values)) + '\n')
            actual = execute(binary, path)['output']
            expected = []
            for index, value in enumerate(values):
                neighbor = index // 32 * 32 + ((index + 1) % 32)
                expected.append((values[neighbor] if neighbor < n else 0.0) - value)
            self.assertEqual(actual, expected)

    def test_divergent_barrier_fails_instead_of_hanging_or_fabricating_output(self):
        bodies = {
            'partial': 'if (threadIdx.x < 16) __syncthreads(); if (i < n) y[i] = x[i];',
            'barrier_sites': 'if (threadIdx.x < 16) { __syncthreads(); } else { __syncthreads(); } if (i < n) y[i] = x[i];',
            'shuffle_sites': 'float v = x[i]; if (threadIdx.x < 16) { v = __shfl_down_sync(0xffffffffu, v, 1); } else { v = __shfl_down_sync(0xffffffffu, v, 1); } if (i < n) y[i] = v;',
        }
        for suffix, body in bodies.items():
            with self.subTest(collective=suffix):
                name = 'fabric_divergent_' + suffix
                _, binary = self.construct_new_kernel(name, f'''__global__ void {name}(const float* x, float* y, int n) {{
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    {body}
}}
''')
                path = self.directory / (name + '.input')
                path.write_text('32\n' + ' '.join(['1'] * 32) + '\n')
                actual = subprocess.run([str(binary), '--input', str(path)], capture_output=True, text=True, timeout=5)
                self.assertNotEqual(actual.returncode, 0)
                self.assertIn('divergent', actual.stderr.lower())
                self.assertEqual(actual.stdout, '')

    def test_unproven_global_tensor_extents_fail_at_real_runtime(self):
        for suffix, statement in [('read', 'y[i] = x[i + 1];'), ('write', 'y[i + 1] = x[i];')]:
            with self.subTest(violation=suffix):
                name = 'fabric_oob_' + suffix
                _, binary = self.construct_new_kernel(name, f'''__global__ void {name}(const float* x, float* y, int n) {{
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) {{ {statement} }}
}}
''')
                path = self.directory / (name + '.input')
                path.write_text('32\n' + ' '.join(['1'] * 32) + '\n')
                actual = subprocess.run([str(binary), '--input', str(path)], capture_output=True, text=True, timeout=5)
                self.assertNotEqual(actual.returncode, 0)
                self.assertTrue(actual.stderr.strip())
                self.assertEqual(actual.stdout, '')

    def test_unknown_device_helpers_are_not_silently_compiled_or_substituted(self):
        repository = self.directory / 'unknown-helper-source'
        command(['git', 'clone', '--shared', '--quiet', SOURCE, repository])
        (repository / 'src/kernels/cuda/factory_unknown_test.cu').write_text('''__global__ void fabric_unknown(const float* x, float* y, int n) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) y[i] = unavailable_device_helper(x[i]);
}
''')
        with self.assertRaisesRegex(ValueError, 'unavailable_device_helper'):
            self.core.extract_core(repository, self.directory / 'unknown-analysis', selected=['fabric_unknown'])

    def test_real_production_weighted_rms_norm_uses_float_shuffle_reduction(self):
        inventory = self.core.extract_core(SOURCE, self.directory / 'normalization-analysis', selected=['rms_norm_weighted_kernel'])
        project = self.directory / 'normalization-project'
        self.core.generate_project(inventory, project)
        binary = build(project, self.directory / 'normalization-build')
        rows, cols, epsilon = 3, 33, f32(1e-5)
        values = [f32(float((index * 17) % 37 - 18) / 7.0) for index in range(rows * cols)]
        weights = [f32(0.5 + float(index % 5) / 8.0) for index in range(cols)]
        expected = []
        for row in range(rows):
            lane_sums = [0.0] * 32
            for lane in range(32):
                for col in range(lane, cols, 32):
                    x = values[row * cols + col]
                    lane_sums[lane] = f32(lane_sums[lane] + f32(x * x))
            for offset in [16, 8, 4, 2, 1]:
                before = lane_sums[:]
                lane_sums = [f32(before[lane] + before[lane + offset if lane + offset < 32 else lane]) for lane in range(32)]
            mean_epsilon = f32(f32(lane_sums[0] / float(cols)) + epsilon)
            inverse = f32(1.0 / f32(math.sqrt(mean_epsilon)))
            expected.extend(f32(f32(values[row * cols + col] * weights[col]) * inverse) for col in range(cols))
        data = self.directory / 'normalization.input'
        data.write_text(f'{rows} {cols} {epsilon:.17g}\n' + ' '.join(format(x, '.17g') for x in values + weights) + '\n')
        actual = execute(binary, data)['output']
        self.assertEqual(len(actual), rows * cols)
        for value, reference in zip(actual, expected):
            self.assertAlmostEqual(value, reference, delta=3e-7)

    def test_malformed_runtime_input_is_an_actual_process_failure(self):
        path = self.directory / 'truncated.input'
        path.write_text('4 2\n0 1\n')
        result = subprocess.run([str(self.binary), '--input', str(path)], capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(result.stderr.strip())


if __name__ == '__main__':
    unittest.main()
