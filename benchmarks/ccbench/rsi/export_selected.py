"""Export final RSI selections for the historical T1 benchmark, without model calls.

Requires completed session result + immutable record references. This is a
benchmark export, not production admission or activation. Never uses the
result's diagnostic candidate_ref to choose the worker.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PARTNER = '2dd6ef196da1b6cc43ff9c50031ebe078115c4f9'
FAMILIES = {'utility.calculate': ('calculate', 'calc_tool.py', 'calc_reference'),
            'utility.table_normalize': ('table_normalize', 'table_tool.py', 'table_reference')}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def git_bytes(path):
    return subprocess.run(['git', '-C', str(REPO), 'show', PARTNER + ':' + path],
                          check=True, capture_output=True).stdout


def regular(path):
    path = Path(path)
    need(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)), 'REAL_ARTIFACT_FILE_REQUIRED')
    return path.read_bytes()


def record(root, ref):
    need(isinstance(ref, dict) and set(ref) == {'id', 'sha256'}
         and isinstance(ref['sha256'], str) and re.fullmatch('[0-9a-f]{64}', ref['sha256']), 'EXACT_RECORD_REF_REQUIRED')
    raw = regular(Path(root) / (ref['sha256'] + '.json'))
    need(sha(raw) == ref['sha256'], 'RECORD_DIGEST_DIFFERS')
    return raw


def final_selection(configuration):
    cfg_raw = regular(configuration)
    cfg = json.loads(cfg_raw)
    need(cfg['schema'] == 'ai4r-rsi-capsule-run-configuration:2', 'FINAL_RUN_CONFIGURATION_REQUIRED')
    session, roots = cfg['session'], Path(cfg['composition']['record_root'])
    result_raw = regular(cfg['result_path'])
    result = json.loads(result_raw)
    need(result['schema'] == 'ai4r-rsi-capsule-session-result:1' and result['id'] == session['id']
         and result['capsule_name'] == session['capsule_name'], 'FINAL_SESSION_IDENTITY_DIFFERS')
    need(json.loads(record(roots, result['session_ref'])) == session, 'FINAL_SESSION_REF_DIFFERS')
    # result_ref captures the terminal record before its own ref is appended.
    original = dict(result); original.pop('result_ref')
    need(json.loads(record(roots, result['result_ref'])) == original, 'FINAL_RESULT_REF_DIFFERS')
    loop = json.loads(record(roots, result['loop_ref']))
    need(loop == result['loop'] and bool(loop['stop_reason']) and loop['stop_reason'] != 'error',
         'SUCCESSFUL_TERMINAL_LOOP_REQUIRED')
    need(isinstance(result.get('parent_visible'), dict) and result['parent_visible'].get('passed') is True,
         'QUALIFIED_PARENT_CONTROL_REQUIRED')
    selection = json.loads(record(roots, result['selection_ref']))
    need(selection == result['selection'] and selection['schema'] == 'ai4r-rsi-capsule-selection:1',
         'FINAL_SELECTION_REF_DIFFERS')
    parent = session['parent_body_ref']
    if selection['role'] == 'parent':
        need(loop['best'] is None and selection['iteration'] == 0 and selection['body_ref'] == parent,
             'PARENT_SELECTION_LINEAGE_DIFFERS')
        chosen = None
    else:
        need(selection['role'] == 'candidate' and isinstance(loop['best'], dict)
             and result['status'] == 'VISIBLE_EVALUATED_UNQUALIFIED', 'FINAL_SELECTION_ROLE_INVALID')
        best = loop['best']
        need(best['iteration'] == selection['iteration'] and best['candidate_ref'] == selection['body_ref'],
             'BEST_CHILD_SELECTION_DIFFERS')
        matches = [row for row in loop['iterations'] if row['iteration'] == selection['iteration']]
        need(len(matches) == 1, 'SELECTED_ITERATION_NOT_UNIQUE')
        chosen = matches[0]
        need(chosen['kept'] is True and chosen['candidate_ref'] == selection['body_ref']
             and chosen['visible'] is not None and chosen['score']['regressed'] is False
             and chosen['selection']['score']['regressed'] is False, 'SELECTED_CHILD_DID_NOT_QUALIFY')
        binding = json.loads(record(roots, chosen['binding_ref']))
        need(binding['candidate_ref'] == selection['body_ref'] and binding['run_id'] == session['id']
             and binding['capsule_name'] == session['capsule_name'] and binding['parent_sha256'] == parent['sha256']
             and binding['grant_sha256'] == sha(encoded(session['grant'])), 'SELECTED_CHILD_BINDING_DIFFERS')
    body = record(roots, selection['body_ref'])
    manifest = cfg['evaluator']['manifest']
    need(manifest['schema'] == 'ai4r-rsi-capsule-runtime:2'
         and sha(encoded(manifest)) == session['grant']['runtime_manifest_sha256'], 'FROZEN_RUNTIME_BINDING_DIFFERS')
    binding = manifest['target_bindings'][session['capsule_name']]
    worker = 'source/jiuwenswarm/' + binding['carrier_path']
    source = next(row for row in manifest['files'] if row['path'] == worker)
    need(source['sha256'] == parent['sha256'] == session['grant']['parent_sha256'], 'FROZEN_PARENT_LINEAGE_DIFFERS')
    if chosen is not None:
        candidate_binding = json.loads(record(roots, chosen['binding_ref']))
        need(candidate_binding['mutable_path'] == binding['carrier_path']
             and candidate_binding['runtime_manifest_sha256'] == sha(encoded(manifest)), 'MUTABLE_CARRIER_DIFFERS')
    runtime_source = 'jiuwenswarm/research_rsi/targets/capsule_runtime.py'
    source_raw = regular(Path(cfg['source_root']) / runtime_source)
    need(sha(source_raw) == cfg['source_pins'][runtime_source], 'BOOTSTRAP_SOURCE_PIN_DIFFERS')
    tree = ast.parse(source_raw)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_child_main')
    bootstrap = (ast.get_source_segment(source_raw.decode(), function) + '\n').encode()
    provenance = {'configuration_sha256': sha(cfg_raw), 'result_sha256': sha(result_raw),
                  'session_ref': result['session_ref'], 'result_ref': result['result_ref'],
                  'selection_ref': result['selection_ref'], 'loop_ref': result['loop_ref'],
                  'run_id': session['id'], 'terminal_status': result['status'], 'selection': selection, 'parent_ref': parent,
                  'release_binding': binding, 'stop_reason': loop['stop_reason'],
                  'model_calls': result['model_calls'], 'production_admission': 'UNKNOWN',
                  'activation': 'NOT_REQUESTED', 'benchmark_decision': None if chosen is None else chosen['benchmark_decision']}
    return cfg, manifest, body, bootstrap, provenance


def copy_runtime(source, destination, manifest):
    """Copy only pinned code/dependencies, never evaluator fixtures or records."""
    source = Path(source)
    need(source.is_absolute() and source.is_dir() and not source.is_symlink(), 'FROZEN_RUNTIME_ROOT_REQUIRED')
    expected = {row['path']: row for row in manifest['files']}
    need(len(expected) == len(manifest['files']) <= 30000, 'BOUNDED_RUNTIME_INVENTORY_REQUIRED')
    actual = {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
    need(actual == set(expected), 'RUNTIME_INVENTORY_DIFFERS')
    total = 0
    for name, entry in expected.items():
        path = PurePosixPath(name)
        need(not path.is_absolute() and path.parts[0] in ('source', 'dependencies')
             and all(part not in ('..', '.', 'fixtures', '__pycache__') for part in path.parts)
             and '\\' not in name and ':' not in name, 'RUNTIME_PATH_INVALID')
        raw = regular(source / name); total += len(raw)
        need(total <= 512 * 1024 * 1024 and len(raw) == entry['size_bytes'] and sha(raw) == entry['sha256'],
             'RUNTIME_FILE_PIN_DIFFERS')
        target = destination / name
        if target.exists():
            need(regular(target) == raw, 'SHARED_RUNTIME_DIFFERS')
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)


def wrapper(family, filename, spec_sha, bridge_sha):
    return ("import importlib.util\nfrom pathlib import Path\nimport hashlib\nimport sys\n"
            "_root = Path(__file__).resolve().parent / 'rsi_bundle'\n"
            "_bridge = _root / 'bridge.py'\n"
            "if hashlib.sha256(_bridge.read_bytes()).hexdigest() != " + repr(bridge_sha) + ":\n"
            "    raise RuntimeError('RSI bridge digest differs')\n"
            "_spec = importlib.util.spec_from_file_location('_ai4r_t1_rsi_bridge', _bridge)\n"
            "_module = importlib.util.module_from_spec(_spec)\n_spec.loader.exec_module(_module)\n"
            "def run(payload):\n    return _module.invoke(payload, directory=_root, specification=" + repr(filename)
            + ", specification_sha256=" + repr(spec_sha) + ")\n"
            "if __name__ == '__main__':\n    sys.exit(_module.main(sys.argv[1:], run, " + repr(family) + "))\n").encode()


def export(configurations, out):
    out = Path(out).resolve()
    need(not out.exists(), 'FRESH_EXPORT_DIRECTORY_REQUIRED')
    selected = [final_selection(Path(path)) for path in configurations]
    names = [cfg['session']['capsule_name'] for cfg, *_ in selected]
    need(bool(names) and len(names) == len(set(names)) and set(names) <= set(FAMILIES),
         'UNIQUE_SUPPORTED_FINAL_RESULTS_REQUIRED')
    bundle = out / 'rsi_bundle'; bundle.mkdir(parents=True)
    declarations = git_bytes('benchmarks/ccbench/admission/declarations.json')
    (bundle / 'declarations.json').write_bytes(declarations)
    bridge = regular(HERE / 'served_tool.py'); (bundle / 'bridge.py').write_bytes(bridge)
    rows = []
    for cfg, manifest, body, bootstrap, provenance in selected:
        name = cfg['session']['capsule_name']; family, tool, reference = FAMILIES[name]
        manifest_raw = encoded(manifest); runtime = 'runtime-' + sha(manifest_raw)
        copy_runtime(cfg['evaluator']['runtime_root'], bundle / runtime, manifest)
        bootstrap_path = bundle / 'bootstrap.py'
        if bootstrap_path.exists():
            need(regular(bootstrap_path) == bootstrap, 'CAPSULE_BOOTSTRAP_SOURCES_DIFFER')
        else:
            bootstrap_path.write_bytes(bootstrap)
        manifest_name, body_name = family + '-manifest.json', family + '-body.py'
        (bundle / manifest_name).write_bytes(manifest_raw); (bundle / body_name).write_bytes(body)
        reference_raw = git_bytes('benchmarks/ccbench/nativeadmit/items/' + reference + '/public/' + tool)
        spec = {'schema': 'ai4r-t1-rsi-tool:1', 'capsule_name': name, 'family': family,
                'manifest': manifest_name, 'manifest_sha256': sha(manifest_raw), 'runtime': runtime,
                'body': body_name, 'selection': provenance['selection'], 'bootstrap_sha256': sha(bootstrap),
                'declarations_sha256': sha(declarations), 'provenance': provenance,
                'historical_reference_sha256': sha(reference_raw),
                'comparability': {'historical_contract_test_definition_unchanged': True,
                    'full_input_domain_equivalence': 'NOT_ESTABLISHED',
                    'adapter_limits': {'packet_bytes': 1048576, 'wrapped_input_bytes': 1048576,
                                       'file_text_characters': 262144, 'output_bytes': 2097152},
                    'validation_scope': 'Finite frozen declaration-derived cases and selected T1 items only.',
                    'same_worker_implementation': False,
                    'historical_tool_interface': 'standalone run(payload)', 'selected_interface': 'frozen packet worker',
                    'runtime_adapter_added': True, 'isolated_RSI_causal_claim_supported': False,
                    'reason': 'Historical reference is standalone; selected release/runtime/adapter differ and packet size limits narrow the input domain.'}}
        spec_name = family + '.json'; spec_raw = encoded(spec); (bundle / spec_name).write_bytes(spec_raw)
        tool_raw = wrapper(family, spec_name, sha(spec_raw), sha(bridge)); (out / tool).write_bytes(tool_raw)
        rows.append({'capsule_name': name, 'tool_file': tool, 'tool_sha256': sha(tool_raw),
                     'specification': spec_name, 'specification_sha256': sha(spec_raw),
                     'selection': provenance['selection'], 'comparability': spec['comparability']})
    result = {'schema': 'ai4r-t1-rsi-export:1', 'partner_commit': PARTNER, 'tools': rows,
              'families': [FAMILIES[name][0] for name in names],
              'deferred_families': [FAMILIES[name][0] for name in FAMILIES if name not in names],
              'benchmark_contract_validation': 'PENDING', 'production_admission': 'UNKNOWN'}
    (out / 'export.json').write_bytes(encoded(result))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', type=Path, action='append', required=True,
                        help='Final run configuration for each requested family; omit deferred families.')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.configuration, args.out), indent=2))
