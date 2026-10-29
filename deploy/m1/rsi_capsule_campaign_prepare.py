"""Prepare one fresh bounded live capsule campaign revision, without model calls.

Installation inputs supply existing isolated authority, never a new Core. All
per-run configurations and limits are derived by rsi_capsule_slot; the launcher
must be invoked separately to dispatch the prepared session.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import subprocess
import time

from deploy.m1 import rsi_capsule_slot as slot


def read(path):
    return json.loads(slot.custody(path).read_bytes())


def selected_declaration(target):
    # Use the selected release's real asset preparation, in memory only.
    from jiuwenswarm.research_rsi.targets.capsules import _SourceStore, release_binding
    binding = release_binding(target)
    store = _SourceStore()
    release = importlib.import_module(
        'jiuwenswarm.research.capsule_extensions.' + binding['release_module'] + '.release')
    asset = release.prepare(store)
    declaration = store.read_record(asset['declaration_ref'])
    slot.need(slot.sha(slot.encoded(declaration)) == binding['declaration_sha256'],
              'EXACT_SELECTED_RELEASE_DECLARATION_REQUIRED')
    return declaration


def installation_template(args):
    if args.base_template:
        return read(args.base_template)
    slot.need(all((args.base_run, args.base_prepare, args.base_launcher,
                   args.base_publication, args.image)), 'INSTALLATION_INPUTS_REQUIRED')
    run, prep, launcher, publication = (
        read(path) for path in (args.base_run, args.base_prepare,
                               args.base_launcher, args.base_publication))
    composition = run['composition']
    return {
        'composition': {**{key: composition[key] for key in (
            *slot.SHARED_COMPOSITION, 'principal', 'exact_binding_refs', 'work_capsule_refs')},
            'account_id': prep['account_id']},
        'evaluator': {'metadata': run['evaluator']['metadata']},
        'grant': {'limits': run['session']['grant']['limits'],
                  'iterations': run['session']['grant']['iterations'], 'horizon_s': 7 * 24 * 3600},
        'launcher': {key: launcher[key]['path'] for key in ('restore', 'seccomp')},
        'publication': {'meta': publication['meta'],
                        'publication_directory': publication['publication_directory']},
        'container': {'image': args.image, 'step_timeout_s': 900},
    }


def make_template(args):
    from jiuwenswarm.research_rsi.targets.capsules import registered_capsule
    from jiuwenswarm.research_rsi.targets.capsule_runtime import verify_runtime
    source = slot.custody(args.source_root, directory=True)
    slot.need(Path(__file__).resolve().parents[2] == source
              and Path(slot.__file__).resolve().parents[2] == source,
              'EXECUTE_HELPER_FROM_CAPTURED_SOURCE_ROOT')
    runtime = slot.custody(args.runtime_root, directory=True)
    manifest = read(args.runtime_manifest)
    slot.need(manifest.get('schema') == 'ai4r-rsi-capsule-runtime:2', 'CURRENT_RUNTIME_V2_REQUIRED')
    verify_runtime(runtime, manifest)
    target = registered_capsule(args.target)
    slot.need(target.public_evaluation_available, 'REGISTERED_EVALUATED_CAPSULE_REQUIRED')
    declaration = selected_declaration(args.target)
    parent = runtime / 'source/jiuwenswarm' / target.carrier_path
    source_parent = source / 'jiuwenswarm' / target.carrier_path
    slot.need(parent.read_bytes() == source_parent.read_bytes(), 'CAPTURED_PARENT_SOURCE_DIFFERS')
    base = installation_template(args)
    if args.utility_bindings:
        scoped = read(args.utility_bindings)
        need_scope = scoped.get('scope', {})
        slot.need(scoped.get('schema') == 'ai4r-utility-rsi-preparation-bindings:1'
                  and need_scope.get('targets') == ['utility.calculate', 'utility.table_normalize']
                  and need_scope.get('product_eligible') is False
                  and args.target in need_scope['targets'], 'EXACT_UTILITY_PREPARATION_BINDINGS_REQUIRED')
        base['composition'] = dict(scoped['composition'], account_id=scoped['account_id'])
    root = slot.custody(args.campaign_root, directory=True)
    identity = args.run_id
    slot.need(identity and '/' not in identity and '\\' not in identity
              and identity not in ('.', '..'), 'FRESH_RUN_ID_REQUIRED')
    template = {
        'schema': slot.TEMPLATE, 'target_id': args.target, 'slot_id': identity,
        'state_root': str(root / 'slots' / identity),
        'roots': {key: str(root / leaf) for key, leaf in (
            ('namespace', 'sessions'), ('control', 'control'), ('evidence', 'evidence'))},
        'composition': base['composition'],
        'evaluator': {**base['evaluator'], 'runtime_root': str(runtime),
                      'manifest_path': str(slot.custody(args.runtime_manifest)),
                      'cgroup_root': '/sys/fs/cgroup/ai4r-rsi-host/jobs/' + identity},
        'grant': {**base['grant'], 'limits': dict(base['grant']['limits'], wall_s=args.wall_s)},
        'loop': {'model_backend': {'kind': 'host-codex'}, 'max_iterations': args.max_iterations,
                 'max_no_progress': args.max_no_progress, 'trials': 3, 'per_call_s': 120,
                 'wall_s': args.wall_s,
                 'benchmark': {'repetitions': 11, 'warmups': 2, 'per_job_s': args.per_job_s}},
        'prepare': {'source_root': str(source), 'parent_declaration': declaration,
                    'request_text': 'Improve ' + args.target + ' implementation under the frozen declaration and mutation grant. Preserve exact behavior; seek measured latency improvement.',
                    'observed_symptom': 'No improvement is established. Diagnose the selected parent and use measured iteration feedback.'},
        'run': {'source_root': str(source), 'runner': str(source / 'runner.py'),
                'composition_path': str(source / 'deploy/m1/rsi_development_run.py')},
        'launcher': {**base['launcher'],
                     **{key: str(source / 'deploy/m1' / filename) for key, filename in (
                         ('launcher', 'rsi_capsule_launcher.py'),
                         ('publisher', 'rsi_capsule_publication.py'),
                         )}, 'projection': str(source / 'jiuwenswarm/server/rsi/cc_rsi_projection.py')},
        'publication': {'meta': {**base['publication']['meta'], 'target_id': args.target,
                               'target_name': args.target, 'mutable_path': target.carrier_path},
                        'publication_directory': str(root / 'publications')},
        'container': base['container'],
    }
    slot.custody(source / 'runner.py')
    slot.need((source / 'runner.py').read_bytes() ==
              (source / 'deploy/m1/rsi_capsule_run.py').read_bytes(), 'EXACT_CAPTURED_RUNNER_REQUIRED')
    slot.validate_template(template)
    # Validate inherited job limits/metadata through the same grant owner before
    # writing a template or consuming any preparation claim.
    slot.derive_grant(template, identity, manifest, now=int(time.time()),
                      loop=slot.revision_loop(template))
    return template


def delegate_run_group(configuration):
    """Provision one fresh, owned job delegation from its exact prepared config."""
    from jiuwenswarm.research_rsi.targets.cgroup_lifecycle import check_capacity
    path = slot.custody(configuration['path'])
    raw = path.read_bytes()
    slot.need(slot.sha(raw) == configuration['sha256'], 'EXACT_DELEGATION_CONFIGURATION_REQUIRED')
    cfg = json.loads(raw)
    slot.need(cfg.get('schema') in ('ai4r-rsi-capsule-run-configuration:1',
                                   'ai4r-rsi-capsule-run-configuration:2'), 'CAPSULE_CONFIGURATION_REQUIRED')
    slot.need(not Path(cfg['claim_path']).exists(), 'CONSUMED_RUN_CANNOT_BE_DELEGATED')
    group = Path(cfg['evaluator']['cgroup_root'])
    parent = slot.custody('/sys/fs/cgroup/ai4r-rsi-host/jobs', directory=True)
    slot.need(group.parent == parent and group.name == cfg['session']['id'],
              'EXACT_RUN_DELEGATION_REQUIRED')
    controllers = {'cpu', 'memory', 'pids'}
    slot.need(controllers <= set((parent / 'cgroup.subtree_control').read_text().split()),
              'HOST_JOB_CONTROLLERS_UNAVAILABLE')
    # Both the fresh delegation and its first worker must fit.
    capacity = check_capacity(parent, required=2)
    group.mkdir(mode=0o700)  # Existing/partially provisioned groups are never adopted.
    (group / 'cgroup.subtree_control').write_text(' '.join('+' + item for item in sorted(controllers)))
    slot.need(not (group / 'cgroup.procs').read_text().strip()
              and controllers <= set((group / 'cgroup.subtree_control').read_text().split()),
              'EMPTY_DELEGATED_RUN_GROUP_REQUIRED')
    job_capacity = check_capacity(group)
    return slot.write_exclusive(path.parent / 'cgroup-delegation.json', {
        'schema': 'ai4r-rsi-run-cgroup-delegation:1', 'run_id': cfg['session']['id'],
        'configuration': configuration, 'path': str(group), 'inode': group.stat().st_ino,
        'device': group.stat().st_dev, 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'controllers': sorted(controllers), 'capacity_before': capacity,
        'job_capacity': job_capacity,
        'helper_sha256': slot.sha(Path(__file__).read_bytes()), 'model_calls': 0})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('operation', choices=('template', 'prepare'))
    for name in ('source-root', 'runtime-manifest', 'runtime-root', 'target', 'campaign-root', 'run-id'):
        parser.add_argument('--' + name, required=True)
    for name in ('base-template', 'base-run', 'base-prepare', 'base-launcher', 'base-publication', 'image'):
        parser.add_argument('--' + name)
    parser.add_argument('--utility-bindings')
    parser.add_argument('--max-iterations', type=int, default=5)
    parser.add_argument('--max-no-progress', type=int, default=3)
    parser.add_argument('--wall-s', type=int, default=3600)
    parser.add_argument('--per-job-s', type=int, default=6)
    args = parser.parse_args(argv)
    slot.need(os.name == 'posix' and os.geteuid() == 0, 'ROOT_CAMPAIGN_PREPARATION_REQUIRED')
    template = make_template(args)
    root = Path(args.campaign_root)
    fresh_publication_directory = not (root / 'publications').exists()
    for path in (*map(Path, template['roots'].values()), root / 'slots', root / 'templates',
                 root / 'publications', root / 'receipts'):
        if not path.exists():
            path.mkdir(mode=0o711)
        slot.custody(path, directory=True)
    publication_directory = root / 'publications'
    if fresh_publication_directory:
        os.chown(publication_directory, 0, 10001)
        publication_directory.chmod(0o750)
    public_meta = publication_directory.stat()
    slot.need(public_meta.st_uid == 0 and public_meta.st_gid == 10001
              and public_meta.st_mode & 0o777 == 0o750, 'ROOT_PUBLIC_DIRECTORY_REQUIRED')
    # The completed publisher appends to a validated prior state. This fresh
    # campaign has no measured baseline yet; its loop will publish the actual
    # parent measurement. Never copy older-release baseline nodes into it.
    publication_path = root / 'publications' / 'publication.json'
    projection_path = Path(template['launcher']['projection'])
    projection_spec = importlib.util.spec_from_file_location('_campaign_projection', slot.custody(projection_path))
    projection = importlib.util.module_from_spec(projection_spec)
    projection_spec.loader.exec_module(projection)
    workspace = template['publication']['meta']['workspace_id']
    if publication_path.exists():
        projection.validate_publication(read(publication_path), workspace_id=workspace)
    else:
        initial = {'workspace_id': workspace,
                   'snapshot': projection.unavailable('No campaign run has completed.'),
                   'candidates': []}
        projection.validate_publication(initial, workspace_id=workspace)
        slot.write_exclusive(publication_path, initial)
    template_path = root / 'templates' / (args.run_id + '.json')
    if args.operation == 'template':
        pin = slot.write_exclusive(template_path, template)
        loop = slot.revision_loop(template)
        print(json.dumps({'status': 'TEMPLATE_NOT_PREPARED', 'template': pin,
                          'loop': loop, 'deadline_s': slot.run_deadline_s(template['grant'], loop),
                          'model_calls': 0}))
        return
    # An existing template must be byte-identical; no edits or adoption of claims.
    if template_path.exists():
        slot.need(read(template_path) == template, 'CAMPAIGN_TEMPLATE_DIFFERS')
    else:
        slot.write_exclusive(template_path, template)
    restore = slot.file_pin(template['launcher']['restore'])['path']
    def docker(*docker_args):
        return subprocess.run(
            ['/usr/bin/python3', '-B', restore, 'client', '/usr/bin/docker', '--host',
             'unix:///run/ai4r-rsi-docker/docker.sock', *docker_args],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45,
            env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'}).stdout
    steps = slot.ContainerSteps(template, template['roots']['control'], docker)
    result = slot.prepare_revision(template, 1, args.run_id, run_step=steps)
    result['cgroup_delegation'] = delegate_run_group(result['configuration'])
    receipt = slot.write_exclusive(root / 'receipts' / (args.run_id + '.json'), result)
    print(json.dumps({'status': 'PREPARED_NOT_DISPATCHED', 'receipt': receipt, **result}))


if __name__ == '__main__':
    main()
