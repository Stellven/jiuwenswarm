"""Read-only dispatch verification for the pinned Muse AQBC parent."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess

from jiuwenswarm.factory.ccs.weight_pack_compiler.helpers.gguf_pack import read_header

SCHEMA = 'factory.r10-dispatch-trace/1'
RAW = Path('lab/r10-aqbcd/dispatch')
LAB = Path('lab/r9-aqbc/measure-engine')
CASE_CONFIG = {
    'iq2_projection': ('iq2_xxs', 16, 1, 1, False),
    'q2_down': ('q2_k', 10, 8, 1, False),
    'iq2_gate_up_pair': ('iq2_xxs', 16, 1, 2, False),
    'iq2_adjacent_gate_up': ('iq2_xxs', 16, 1, 1, True),
}
SOURCES = {
    'src/models/muse-spark.cpp': ('build_moe_ffn(moe_inp', 'n_expert, n_expert_used'),
    'src/llama-graph.cpp': ('moe_cache->build_lookup', 'cached ? moe_cache->get_experts(w) : w',
                            'ggml_mul(ctx0, res, s)', 'ggml_reshape_3d(ctx0, cur, n_embd, 1, n_tokens)'),
    'src/llama-moe-cache.cpp': ('n_zero = cpu_share > 0.0f', 'ggml_view_3d(ctx, bank',
                                'pimpl->get_cpu_map', 'ggml_backend_supports_op(pimpl->backend(il)',
                                'the callback reads the selected experts, uploads the missing ones'),
    'ggml/src/ggml-cuda/ggml-cuda.cu': ('if (!use_mmq_few && ne2 <= MMVQ_MAX_BATCH_SIZE)',
                                         'ggml_cuda_mul_mat_vec_q(ctx, src0, src1, ids, dst);',
                                         'mul_mat_id_glu_ops', 'GGML_ASSERT(ggml_cuda_mul_mat_id_needs_sync'),
    'ggml/src/ggml-cuda/mmq-few.cu': ('return type == GGML_TYPE_IQ4_XS || type == GGML_TYPE_IQ4_NL ? 8 : 2;',),
    'ggml/src/ggml-cuda/mmvq.cu': ('const uint32_t channel_dst = shared_expert ? 0 : blockIdx.y',
                                   'const int64_t nchannels_dst      = ids ? ne1  : ne2;',
                                   'const int64_t ncols_dst          = ids ? ne2  : ne1;',
                                   'ids ? make_uint3(0, 0, 0)', 'ids ? ids[channel_dst]',
                                   'quantize_row_q8_1_cuda',
                                   'const dim3 block_nums(nblocks, nchannels_dst, nsamples_or_ntokens);'),
}
STAGE = 'native CC execution'


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def checked(root, ref):
    path = (root / ref['path']).resolve()
    require(path.is_relative_to(root) and sha(path) == ref['sha256'], f'Source did not match its digest: {path.name}')
    return path


def ref(root, path):
    return {'path': path.relative_to(root).as_posix(), 'sha256': sha(path)}


def git(source, *args):
    return subprocess.check_output(['git', '-C', str(source), *args], timeout=15)


def source_links(source, build_dir, commit, tree):
    require(re.fullmatch(r'[0-9a-f]{40}', commit) and re.fullmatch(r'[0-9a-f]{40}', tree), 'Invalid source pin')
    require(git(source, 'rev-parse', commit + '^{tree}').decode().strip() == tree, 'Pinned source tree differs')
    links = {}
    for name, terms in SOURCES.items():
        expected = git(source, 'show', commit + ':' + name)
        frozen = (build_dir / 'frozen-source' / name).read_bytes()
        require(expected == frozen, f'Frozen build source differs from commit: {name}')
        lines = expected.decode().splitlines()
        anchors = []
        for term in terms:
            line = next((i + 1 for i, text in enumerate(lines) if term in text), None)
            require(line is not None, f'Dispatch predicate absent from pinned source: {name}')
            anchors.append({'line': line, 'source': lines[line - 1].strip()})
        links[name] = {'sha256': hashlib.sha256(expected).hexdigest(), 'anchors': anchors}
    return links


def pack_shapes(pack, manifest, root):
    entries = load(manifest)['files']
    require(len(entries) == pack['shard_count'] == 11 and entries[0]['sha256'] == pack['first_shard_sha256'],
            'Unexpected split pack manifest')
    require(sum(row['bytes'] for row in entries) == pack['bytes'], 'Split pack byte count differs')
    shards, tensors = [], {}
    metadata = None
    for index, entry in enumerate(entries):
        require(Path(entry['name']).name == entry['name'], 'Invalid shard path')
        path = manifest.parent / entry['name']
        require(path.stat().st_size == entry['bytes'], 'Shard size differs from manifest')
        header = read_header(path)
        require(header['metadata'].get('split.no') == index, 'Split pack index differs')
        if index == 0:
            metadata = header['metadata']
            require(path.resolve() == Path(pack['first_shard']).resolve(), 'Unexpected first shard')
        shards.append({'path': path.relative_to(root).as_posix(), 'header_sha256': header['header_sha256'],
                       'header_bytes_with_padding': header['data_start'], 'manifest_shard_sha256': entry['sha256']})
        for tensor in header['tensors']:
            name = tensor['name']
            if re.fullmatch(r'blk\.\d+\.ffn_(?:gate|up|down|gate_up)_exps\.(?:weight|scale|input_scale)', name):
                require(name not in tensors, f'Duplicate routed tensor: {name}')
                tensors[name] = tensor
    require(metadata['general.architecture'] == 'muse-spark', 'Unexpected pack architecture')
    require([metadata['muse-spark.' + key] for key in (
        'block_count', 'expert_count', 'expert_used_count', 'moe_latent_size', 'expert_feed_forward_length',
    )] == [62, 256, 8, 4096, 4096], 'Unexpected routed decode dimensions')
    shapes = {}
    for projection, dtype, channels in [('gate', 'iq2_xxs', 1), ('up', 'iq2_xxs', 1), ('down', 'q2_k', 8)]:
        prefix = 'ffn_' + projection + '_exps'
        weights = [tensors.get(f'blk.{i}.{prefix}.weight', {}) for i in range(62)]
        require(all(t.get('shape') == [4096, 4096, 256] and t['type'] == dtype for t in weights),
                f'Unexpected routed weights for {projection}')
        scales = [i for i in range(62) if f'blk.{i}.{prefix}.scale' in tensors]
        require(len(scales) == 60, f'Unexpected scale layout for {projection}')
        shapes[projection] = {'weights_ne': [4096, 4096, 256], 'type': dtype, 'layers': len(weights),
                              'f32_activations_ne': [4096, channels, 1], 'i32_selected_slots_ne': [8, 1],
                              'f32_outputs_ne': [4096, 8, 1], 'post_weight_scale_layers': scales,
                              'unscaled_layers': sorted(set(range(62)) - set(scales))}
    require(not any('ffn_gate_up_exps.weight' in name for name in tensors), 'Unexpected combined gate-up weight')
    require(shapes['gate']['post_weight_scale_layers'] == shapes['up']['post_weight_scale_layers'],
            'Unexpected asymmetric gate-up scales')
    return shapes, shards


def fixture_rows(root, proof):
    require(not (root / RAW / 'gpu-inventory-before.csv').read_text().strip(), 'GPU slot was not empty')
    require((root / RAW / 'gpu-target.csv').read_text().strip().startswith('NVIDIA GB10,') and
            (root / RAW / 'gpu-target.csv').read_text().strip().endswith(', 12.1'), 'Wrong fixture CUDA target')
    cases = {}
    for name, (dtype, type_id, channels, matvecs, fused) in CASE_CONFIG.items():
        log = root / RAW / (name + '.log')
        output, = (json.loads(line) for line in log.read_text().splitlines() if line.startswith('{"case"'))
        row_bytes = 16 * (66 if dtype == 'iq2_xxs' else 84)
        require(output['case'] == name and output['weight_type'].lower() == dtype and output['zero_output_guard'] is True and
                [output[k] for k in ('k', 'n', 'routes', 'tokens', 'operand_channels', 'bank_slots', 'row_bytes', 'expert_bytes')]
                == [4096, 4096, 8, 1, channels, 8, row_bytes, row_bytes * 4096],
                f'Wrong fixture operands: {name}')
        db = root / RAW / (name + '.sqlite')
        with sqlite3.connect(db.as_uri() + '?mode=ro&immutable=1', uri=True) as conn:
            raw = conn.execute("""
                SELECT s.value, d.value, k.gridX, k.gridY, k.gridZ, k.blockX, k.blockY, k.blockZ, k.graphNodeId
                FROM CUPTI_ACTIVITY_KIND_KERNEL k
                JOIN StringIds s ON s.id = k.shortName JOIN StringIds d ON d.id = k.demangledName
                ORDER BY k.start
            """).fetchall()
        launches = [{'name': short, 'demangled': full, 'grid': list(dims[:3]), 'block': list(dims[3:6]),
                     'graph_node_id': dims[6]} for short, full, *dims in raw]
        expected = ['quantize_q8_1', 'mul_mat_vec_q'] * matvecs
        if name == 'iq2_gate_up_pair':
            expected += ['unary_gated_op_kernel']
        require([row['name'] for row in launches] == expected and all(row['graph_node_id'] for row in launches),
                f'Unexpected replayed CUDA kernel sequence: {name}')
        for row in launches:
            if row['name'] == 'mul_mat_vec_q':
                template = f'mul_mat_vec_q<(ggml_type){type_id}, (int)1, (bool){int(fused)},'
                require(template in row['demangled'] and row['grid'] == [4096, 8, 1] and row['block'] == [32, 4, 1],
                        f'Kernel did not batch all selected routes: {name}')
        cases[name] = {'operands': output, 'launches': launches, 'launch_count': len(launches),
                       'matvec_launch_count': matvecs, 'gate_up_fused': fused,
                       'log': ref(root, log), 'sqlite': ref(root, db),
                       'nsys_report': ref(root, root / RAW / (name + '.nsys-rep'))}
    return {'run_kind': 'pre-graph no-model CUDA fixture', 'source_sha256': proof['fixture_source_sha256'],
            'executable_sha256': proof['fixture_executable_sha256'],
            'tool': 'NVIDIA Nsight Systems 2025.3.2, CUDA graph node capture',
            'cases': cases}


def dispatch_trace(request, proof, fixture_source):
    parent_path = Path(request['parent']['path']).resolve()
    root = parent_path.parent.parent
    require(parent_path == root / 'r10/parent-reference.json', 'Unexpected parent pin location')
    require(sha(parent_path) == request['parent']['sha256'] == proof['parent_sha256'], 'Parent receipt digest differs')
    require(sha(fixture_source) == proof['fixture_source_sha256'], 'Fixture source differs from acquisition pin')
    for name, expected in proof['inputs'].items():
        checked(root, {'path': name, 'sha256': expected})
    parent = load(parent_path)
    require(parent['parent'] == 'AQBC' and parent['format'] == 'muse-r10-parent-reference/1', 'Unexpected parent receipt')
    build_path = checked(root, parent['evidence']['engine_build'])
    require(load(build_path)['source'] == parent['engine_source'], 'AQBC upstream build source pin differs')
    load_path = checked(root, parent['evidence']['lab_load'])
    lab = load(load_path)
    manifest_record = load(root / LAB / 'measurements.json')
    image = load(root / RAW / 'image-file-receipt.json')
    require(lab['image']['image_id'] == image['image_id'] == parent['image_id'] and image['same_rootfs'] is True and
            lab['image']['llama_server_sha256'] == image['image_file_sha256']['llama-server'] == parent['binary_sha256'] and
            lab['image']['launch_config_sha256'] == parent['launch_config_sha256'] and
            lab['image']['launch_config'] == parent['launch_config'] and
            manifest_record['files']['load.json'] == sha(load_path), 'AQBC runtime identity differs')
    require(image['source_commit'] == parent['engine_source']['commit'] and
            image['cmd'] == parent['launch_config']['args'], 'Pinned image source or launch options differ')
    for name, expected in image['image_file_sha256'].items():
        require(sha(build_path.parent / 'image/app' / name) == expected, f'Pinned image file mismatch: {name}')
    require('--cpu-moe' in image['cmd'] and image['cmd'][image['cmd'].index('--moe-cache-cpu-share') + 1] == '0' and
            parent['launch_config']['request']['cache_prompt'] is True and lab['observed']['n_seq_max'] == 1,
            'AQBC is not the single-slot, zero CPU share route configuration')
    pack = manifest_record['identity']['pack']
    manifest = Path(pack['manifest']).resolve()
    require(manifest.is_relative_to(root) and sha(manifest) == pack['manifest_sha256'] == parent['pack_manifest_sha256'],
            'AQBC pack manifest differs')
    shapes, shards = pack_shapes(pack, manifest, root)
    source_root = Path(request['source_root']).resolve()
    require(source_root == root / 'graph-r8/agent-workspace/llama.cpp-muse', 'Unexpected retained source root')
    lines = source_links(source_root, build_path.parent, **parent['engine_source'])
    log = root / LAB / 'server.log'
    require(manifest_record['files']['server.log'] == sha(log), 'AQBC runtime log digest differs')
    raw_log = log.read_text()
    match = re.findall(r'^.*(?:compute capability 12\.1|CUDA0 MoE cache size|62 layers, q2_K:|tg bs=1|\(0 on the CPU\)|muse-spark\.expert_used_count).*$', raw_log, re.M)
    require(any('0% of the misses on the CPU' in x for x in match) and any('4625 slots' in x for x in match) and
            any('tg bs=1' in x for x in match) and sum('(0 on the CPU)' in x for x in match) == 2,
            'Lab evidence did not establish the recorded CUDA MoE cache path')
    fixture = fixture_rows(root, proof)
    return {
        'format': SCHEMA, 'eligibility': 'already_batched', 'may_build': False,
        'identity': {'image_id': parent['image_id'], 'binary_sha256': parent['binary_sha256'],
                     'cuda_library_sha256': image['image_file_sha256']['libggml-cuda.so.1'],
                     'source_commit': parent['engine_source']['commit'], 'source_tree': parent['engine_source']['tree'],
                     'pack_manifest_sha256': parent['pack_manifest_sha256'],
                     'launch_config_sha256': parent['launch_config_sha256'], 'launch_config': parent['launch_config']},
        'shapes': shapes, 'shards': shards, 'source_paths': lines, 'fixture': fixture,
        'input_evidence': dict(ref(root, parent_path), files=proof['inputs']),
        'runtime_path': {
            'cache_slots': 4625, 'stored_experts_per_layer': 256, 'selected_routes_per_token': 8,
            'log': ref(root, log), 'log_lines': match,
            'description': 'Host-mapped experts stream into the CUDA MoE cache. Slot lookup remaps selected IDs, and CUDA receives the cached bank via MUL_MAT_ID.',
            'dispatch_predicate': 'GB10 few-row MMQ starts at two tokens for these types; one-token IQ2_XXS and Q2_K use MMVQ. In the IDs branch, the grid uses output route channels, independent of bank depth. The kernel indexes bank slices using slot IDs.',
            'fusion': 'External post-weight scales prevent the plain adjacent IQ2_XXS gate/up fusion. A compatible adjacent pair can fuse; the separate and fused implementations both cover all eight routes per matvec.',
        },
        'limits': ['Fixture acquired before the graph using the parent library, no Muse weights or load.',
                   'Eight synthetic slots preserve selected route count, per-slot stride, types, K and N. The production bank has 4625 slots plus a pad.',
                   'Only the one-token, single-slot routed decode path is qualified. Prefill, uploads, full model timing and alternative optimizations are outside this trace.'],
    }


def result(request, proof, fixture_source):
    try:
        raw = dispatch_trace(request, proof, fixture_source)
        root = Path(request['parent']['path']).resolve().parent.parent
        actual = root / RAW / 'dispatch-trace.json'
        require(actual.read_bytes() == canonical(raw), 'Retained trace differs from independent rederivation')
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, subprocess.SubprocessError) as exc:
        return {'done': False, 'decision': 'unresolved',
                'dispatch_trace': {'format': SCHEMA, 'eligibility': 'unresolved', 'may_build': False},
                'checks': [{'name': 'pinned_dispatch_trace', 'status': 'fail', 'stage': STAGE, 'detail': str(exc)}]}
    checks = {
        'parent_and_runtime_binding': 'Pinned AQBC source, image and library hashes agree with the recorded one-slot CUDA MoE cache path.',
        'complete_decode_shape_census': 'Read all 11 shard headers. All 62 layers use 4096-by-4096 IQ2_XXS gate/up and Q2_K down over eight selected routes.',
        'observed_cuda_dispatch': 'Reparsed four Nsight SQLite captures. Each quantized projection already dispatches all eight routes together; the compatible adjacent gate/up pair also fuses.',
    }
    return {'done': True, 'decision': raw['eligibility'],
            'checks': [{'name': key, 'status': 'pass', 'stage': STAGE, 'detail': value} for key, value in checks.items()],
            'dispatch_trace': dict(raw, raw_trace=ref(root, actual))}
