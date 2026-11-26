"""Read-only inspection of packs pinned by host replay receipts."""
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re

from .ccs.weight_pack_compiler.helpers import gguf_pack

REGISTRY_ENV = 'FACTORY_CAPPED_REPLAY_REGISTRY'
REGISTRY_SCHEMA = 'factory.capped-replay-registry/1'
SHA256 = re.compile(r'[0-9a-f]{64}')
COMMIT = re.compile(r'[0-9a-f]{40}')


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _read_doc(path):
    raw = path.read_bytes()
    return json.loads(raw), _digest(raw)


def _pack_file(directory, name):
    _require(isinstance(name, str) and bool(name) and Path(name).name == name
             and name not in {'.', '..'}, 'recipe or receipt file names must be basenames')
    path = directory / name
    _require(path.is_file() and not path.is_symlink(), f'missing or linked pack file: {path}')
    return path


def manifest_path(first):
    stem = re.sub(r'-00001-of-\d{5}$', '', first.stem)
    return first.with_name(f'{stem}.manifest.json')


def _manifest_rows(first, manifest_path):
    manifest, manifest_sha256 = _read_doc(manifest_path)
    _require(manifest.get('format') == 'factory.pack-manifest/1', 'unsupported pack manifest format')
    paths = gguf_pack.shard_paths(first)
    _require(bool(paths) and first == paths[0], 'pack must name its first GGUF shard')
    rows = manifest.get('files')
    _require(isinstance(rows, list) and len(rows) == len(paths), 'pack manifest shard count mismatch')
    for path, row in zip(paths, rows):
        _require(path.name == row.get('name'), 'pack manifest shard names mismatch')
        _pack_file(path.parent, path.name)
        size = row.get('bytes')
        _require(type(size) is int and size > 0 and size == path.stat().st_size,
                 f'pack shard size mismatch: {path.name}')
        _require(SHA256.fullmatch(str(row.get('sha256'))), f'pack manifest has no digest for {path.name}')
    total = sum(row['bytes'] for row in rows)
    _require(manifest.get('bytes', manifest.get('total_bytes')) == total, 'pack manifest total size mismatch')
    return rows, manifest_sha256


def _source_checkpoint(checkpoint, pin_path, rehash):
    pins, digest = _read_doc(pin_path)
    _require(pins.get('format') == 'muse-pins/1', 'checkpoint manifest must be muse-pins/1')
    source = pins['checkpoint']
    _require(Path(source['root']).resolve() == checkpoint, 'checkpoint manifest root differs from task checkpoint')
    shards = source['shards']
    _require(bool(shards) and set(shards) == {p.name for p in checkpoint.glob('*.safetensors')},
             'checkpoint manifest shard names differ from the checkpoint')
    for name, row in shards.items():
        path = _pack_file(checkpoint, name)
        _require(path.stat().st_size == row['bytes'] and SHA256.fullmatch(row['sha256']),
                 f'checkpoint shard metadata mismatch: {name}')
        if rehash:
            _require(gguf_pack.sha256_file(path) == row['sha256'], f'checkpoint shard digest mismatch: {name}')
    for name, expected in source['small_files_sha256'].items():
        path = _pack_file(checkpoint, name)
        _require(gguf_pack.sha256_file(path) == expected, f'checkpoint metadata digest mismatch: {name}')
    return digest


def parse_quantize_argv(argv):
    from .ccs.weight_pack_compiler.helpers import stock_quantize

    return stock_quantize.parse_argv(argv)


def quantize_argv_digest(argv):
    """Name tool, source, output and imatrix separately from the exact quantization arguments."""
    call = parse_quantize_argv(argv)
    _require(call['output'] and '--dry-run' not in call['flags'], 'quantize replay requires a production recipe')
    normalized = list(argv)
    normalized[0] = '<tool>'
    # A full recipe ends with input, output, ftype and an optional thread count.
    position = len(argv) - (4 if argv[-1].isdigit() else 3)
    normalized[position:position + 2] = ['<input>', '<output>']
    if '--imatrix' in argv:
        _require(argv.count('--imatrix') == 1, 'quantize replay requires a single imatrix argument')
        normalized[argv.index('--imatrix') + 1] = '<imatrix>'
    return _digest(json.dumps(normalized, separators=(',', ':')).encode())


def _shard_identity(rows):
    return [{key: row[key] for key in ('name', 'bytes', 'sha256')} for row in rows]


def _inspect_pack(first, files, rehash):
    pack = gguf_pack.load_pack(first, hash_files=rehash)
    for actual, expected in zip(pack['files'], files):
        _require(actual['header_sha256'] == expected['header_sha256'],
                 f"pack header mismatch: {actual['name']}")
        _require(actual['bytes'] == expected['bytes'], f"pack shard size mismatch: {actual['name']}")
        if rehash:
            _require(actual['sha256'] == expected['sha256'], f"pack shard digest mismatch: {actual['name']}")
    return pack


def _source_pack(first, source, rehash, inspect):
    manifest = _pack_file(first.parent, manifest_path(first).name)
    manifest_rows, _ = _manifest_rows(first, manifest)
    files = source['files']
    _require(_shard_identity(files) == _shard_identity(manifest_rows),
             'quantize recipe source differs from its pack manifest')
    _require(bool(files) and all(SHA256.fullmatch(str(row.get('header_sha256'))) for row in files),
             'quantize recipe source lacks header digests')
    digest = gguf_pack.pack_digest(files)
    _require(digest == source['digest'], 'quantize recipe source digest mismatch')
    if inspect:
        _inspect_pack(first, files, rehash)
    return digest


def _receipt(home, recipe, job_id):
    configured = os.environ.get(REGISTRY_ENV)
    _require(configured, f'host replay registry is unavailable ({REGISTRY_ENV})')
    registry = Path(configured).expanduser()
    _require(registry.is_absolute(), 'host replay registry path must be absolute')
    registry = registry.resolve()
    _require(not registry.is_relative_to(home.resolve()), 'host replay registry must be outside FACTORY_HOME')
    _require(registry.is_file(), 'host replay registry is not an existing file')
    document, _ = _read_doc(registry)
    _require(document.get('schema') == REGISTRY_SCHEMA, 'unsupported host replay registry schema')
    receipt = document['receipts'].get(job_id)
    _require(isinstance(receipt, dict) and receipt.get('recipe') == recipe,
             'no host replay receipt matches this job id and recipe')
    duration = receipt['duration_seconds']
    _require(isinstance(receipt['run_id'], str) and bool(receipt['run_id']) and
             type(duration) in {int, float} and math.isfinite(duration) and duration >= 0,
             'invalid replay receipt provenance')
    date = datetime.fromisoformat(receipt['recorded_at'].replace('Z', '+00:00'))
    _require(date.tzinfo is not None, 'replay receipt date needs a timezone')
    return receipt


def _output_dir(home, name, receipt):
    out_dir = (home / 'packs' / name).resolve()
    _require(Path(receipt['output']['pack_dir']) == out_dir, 'requested output directory differs from the replay receipt')
    return out_dir


def _output(out_dir, args, receipt, verify):
    output = receipt['output']
    first = _pack_file(out_dir, output['first_shard'])
    _require(first.suffix == '.gguf', 'replay output must be GGUF')
    manifest = _pack_file(out_dir, output['manifest'])
    _require(manifest == manifest_path(first), 'replay receipt names the wrong manifest')
    rows, digest = _manifest_rows(first, manifest)
    _require(digest == output['manifest_sha256'], 'replay output manifest digest mismatch')
    total = sum(row['bytes'] for row in rows)
    _require(total == output['bytes'], 'replay output byte total differs from receipt')
    _require(_shard_identity(output['files']) == _shard_identity(rows),
             'replay output manifest shard identity differs from receipt')
    result = dict(first_shard=str(first), out_dir=str(out_dir), manifest=str(manifest), manifest_sha256=digest,
                  bytes=total, files=output['files'])
    if verify:
        pack = _inspect_pack(first, output['files'], args['replay'].get('rehash', False))
        tensors = len(pack['tensors'])
        census = gguf_pack.census(pack['tensors'])
        _require(tensors > 0 and tensors == output['tensors'] and census == output['census'],
                 'replay output tensor census differs from receipt')
        result.update(tensors=tensors, census=census)
    return result


def admit(home, task, recipe, args, readable, verify=False, expected_receipt_sha256=None):
    """Re-derive replay identity from scoped inputs and check it against the host registry."""
    replay = args.get('replay')
    _require(isinstance(replay, dict) and set(replay) <= {'job_id', 'rehash'} and
             isinstance(replay.get('job_id'), str) and bool(replay['job_id']) and
             type(replay.get('rehash', False)) is bool, 'replay takes {job_id, rehash?}')
    commit = args['commit']
    _require(isinstance(commit, str) and COMMIT.fullmatch(commit), 'replay requires the full original producer commit')
    receipt = _receipt(home, recipe, replay['job_id'])
    receipt_sha256 = _digest(json.dumps(receipt, sort_keys=True, separators=(',', ':')).encode())
    if expected_receipt_sha256 is not None:
        _require(receipt_sha256 == expected_receipt_sha256, 'host replay receipt changed after submission')
    out_dir = _output_dir(home, args['name'], receipt)
    rehash = verify and replay.get('rehash', False)
    identity = dict(producer_commit=commit)
    if recipe == 'convert':
        checkpoint_dir = (task.get('resources') or {}).get('checkpoint_dir')
        _require(checkpoint_dir, 'the task names no resources.checkpoint_dir to convert')
        checkpoint = readable(checkpoint_dir, 'checkpoint', 'dir')
        pins = readable(args['checkpoint_manifest'], 'checkpoint manifest')
        identity.update(outtype=args.get('outtype', 'bf16'), split_max_size=args.get('split_max_size', '50G'),
                        checkpoint_manifest_sha256=_source_checkpoint(checkpoint, pins, rehash))
        details = dict(checkpoint=str(checkpoint))
    else:
        path = readable(args['recipe'], 'quantize recipe')
        plan, _ = _read_doc(path)
        _require(plan.get('format') == 'factory.pack-recipe/1', 'quantize replay requires factory.pack-recipe/1')
        argv = plan['argv']
        _require(isinstance(argv, list) and all(isinstance(arg, str) for arg in argv), 'invalid quantize recipe argv')
        call = parse_quantize_argv(argv)
        source = readable(call['input'], 'source pack')
        imatrix = readable(call['imatrix'], 'imatrix') if call['imatrix'] else None
        imatrix_sha256 = gguf_pack.sha256_file(imatrix) if imatrix else None
        _require((plan.get('imatrix') or {}).get('sha256') == imatrix_sha256, 'quantize imatrix digest mismatch')
        first = _pack_file(out_dir, receipt['output']['first_shard'])
        output_name = manifest_path(first).name.removesuffix('.manifest.json') + '.gguf'
        _require(Path(call['output'] or '').resolve() == first.with_name(output_name),
                 'quantize recipe output differs from the replay receipt')
        target = gguf_pack.canonical_target(plan['target'])
        _require(gguf_pack.parse_target(target) == gguf_pack.parse_target(plan['target']),
                 'quantize recipe target differs from its canonical target')
        identity.update(target=target, argv_sha256=quantize_argv_digest(argv),
                        source_digest=_source_pack(source, plan['source'], rehash, verify), imatrix_sha256=imatrix_sha256)
        details = dict(probe=False, recipe=str(path), argv=argv)
    _require(identity == receipt['inputs'], 'replay recipe inputs differ from the historical job receipt')
    result = _output(out_dir, args, receipt, verify)
    result.update(details, name=args['name'], commit=commit, rehash=replay.get('rehash', False), verified_inputs=identity)
    provenance = dict(job_id=replay['job_id'], **{key: receipt[key] for key in ('run_id', 'recorded_at', 'duration_seconds')})
    return provenance, receipt_sha256, result
