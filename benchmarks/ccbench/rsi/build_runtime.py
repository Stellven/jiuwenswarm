"""Build a private T1 image from a local immutable base and exact partner tree.

No downloads, dependency installation, production tags or service activation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from export_selected import HERE, PARTNER, REPO, encoded, need, regular, sha
from run_t1_rsi import image_id, write_new


def build(args):
    source, out = args.partner_source.resolve(), args.out.resolve()
    need(not out.exists(), 'FRESH_IMAGE_BUILD_OUTPUT_REQUIRED')
    inspected = subprocess.run(['docker', 'image', 'inspect', args.base_image, '--format', '{{.Id}}'],
                               capture_output=True, text=True, check=True, timeout=60)
    need(inspected.stdout.strip() == args.base_image, 'LOCAL_IMMUTABLE_BASE_REQUIRED')
    tree = subprocess.run(['git', '-C', str(args.repository.resolve()), 'ls-tree', '-r', '-z', PARTNER,
                           '--', 'jiuwenswarm'], capture_output=True, check=True).stdout
    files = {}; total = 0
    for row in tree.split(b'\0'):
        if not row: continue
        header, name = row.split(b'\t', 1); mode, kind, blob = header.decode().split()
        name = name.decode('utf-8')
        need(kind == 'blob' and mode in ('100644', '100755')
             and name.startswith('jiuwenswarm/') and '..' not in Path(name).parts,
             'UNSUPPORTED_PARTNER_TREE_ENTRY')
        raw = regular(source / name); total += len(raw)
        need(total <= 512 * 1024 * 1024 and len(files) < 30000, 'PARTNER_PACKAGE_TOO_LARGE')
        actual = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        need(actual == blob, 'PARTNER_SOURCE_DIFFERS: ' + name)
        files[name] = {'sha256': sha(raw), 'git_blob': blob, 'mode': mode}
    need(bool(files) and 'jiuwenswarm/resources/.env.template' in files
         and 'jiuwenswarm/resources/config.yaml' in files, 'FULL_PARTNER_RESOURCES_REQUIRED')
    actual = {p.relative_to(source).as_posix() for p in (source / 'jiuwenswarm').rglob('*') if p.is_file()}
    need(actual == set(files), 'PARTNER_PACKAGE_EXTRA_OR_MISSING_FILES')
    out.mkdir(parents=True); context = out / 'context'; context.mkdir()
    for name, row in files.items():
        target = context / name; target.parent.mkdir(parents=True, exist_ok=True)
        raw = regular(source / name)
        need(sha(raw) == row['sha256'], 'PARTNER_SOURCE_CHANGED_DURING_BUILD')
        target.write_bytes(raw); target.chmod(0o755 if row['mode'] == '100755' else 0o644)
    # Docker COPY retains directory modes; worker traversal must not depend on host umask.
    for directory in (context, *[p for p in context.rglob('*') if p.is_dir()]):
        directory.chmod(0o755)
    recipe = regular(HERE / 'Dockerfile.runtime')
    (context / 'Dockerfile').write_bytes(recipe)
    manifest = {'schema': 'ai4r-t1-runtime-build:1', 'base_image_id': args.base_image,
                'partner_commit': PARTNER, 'files': files, 'recipe_sha256': sha(recipe),
                'network': 'none', 'dependency_installation': False, 'production_activation': False}
    write_new(out / 'build-manifest.json', manifest)
    command = ['docker', 'build', '--pull=false', '--network=none', '--iidfile', str(out / 'image-id'),
               '--build-arg', 'BASE_IMAGE=' + args.base_image, '--build-arg', 'PARTNER_COMMIT=' + PARTNER,
               '-f', str(context / 'Dockerfile'), str(context)]
    with (out / 'build.log').open('xb') as log:
        completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    need(completed.returncode == 0, 'PRIVATE_BENCHMARK_IMAGE_BUILD_FAILED')
    identity = image_id((out / 'image-id').read_text().strip())
    result = {'schema': 'ai4r-t1-runtime-image:1', 'image_id': identity,
              'base_image_id': args.base_image, 'partner_commit': PARTNER,
              'build_manifest_sha256': sha(regular(out / 'build-manifest.json')),
              'worker_python_unchanged_by_recipe': True}
    write_new(out / 'image.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--partner-source', type=Path, required=True)
    parser.add_argument('--repository', type=Path, default=REPO)
    parser.add_argument('--base-image', type=image_id, required=True)
    parser.add_argument('--out', type=Path, required=True)
    print(json.dumps(build(parser.parse_args()), indent=2))


if __name__ == '__main__': main()
