"""Root authoring of small ML examples; no measurements or acceptance are invented."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import secrets
import sqlite3
import stat
import subprocess
import sys

from .contracts import ResearchError
from .local_science import SAMPLE_REQUEST
from .state import json_bytes
from .trusted_scoring import PRIVATE_PATH, parse_public_dataset


def _root():
    if os.name != 'posix' or os.geteuid() != 0:
        raise ResearchError('ml_pilot', 'ML private task authoring requires Linux root')


def _write(path, raw, mode):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ResearchError('ml_pilot', 'Task path may not contain symlinks')
    with path.open('xb') as stream:
        os.fchmod(stream.fileno(), mode)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def task_bytes(kind, seed):
    """Pure deterministic generator. Production seeds remain root-private."""
    if kind not in {'signal', 'no-signal'}:
        raise ResearchError('ml_pilot', 'Unknown ML task kind')
    generator = random.Random(seed)
    task_id = hashlib.sha256(str(seed).encode()).hexdigest()[:24]
    train, test, labels = [], [], []
    for split, count in [('train', 96), ('test', 48)]:
        order = list(range(count)); generator.shuffle(order)
        for i in order:
            label = i % 2 if kind == 'signal' else int(i % 4 == 0)
            features = [round(generator.gauss(2 if label else -2, .8), 6) for _ in range(2)] if kind == 'signal' else [0.0, 0.0]
            row_id = hashlib.sha256(f'{task_id}:{split}:{i}'.encode()).hexdigest()[:24]
            row = {'id': row_id, 'features': features}
            if split == 'train':
                row['label'] = 'class_' + str(label); train.append(row)
            else:
                test.append(row); labels.append({'id': row_id, 'label': 'class_' + str(label)})
    public = json_bytes({'schema': 'ai4r-classification-data:1', 'dataset_id': task_id,
        'feature_names': ['feature_0', 'feature_1'], 'classes': ['class_0', 'class_1'], 'train': train, 'test': test})
    parse_public_dataset(public)
    holdout = json_bytes({'schema': 'ai4r-classification-holdout:1', 'dataset_id': task_id,
        'public_data_sha256': hashlib.sha256(public).hexdigest(), 'labels': labels})
    return task_id, public, holdout


def prepare_tasks(public_directory, private_directory):
    _root()
    public_directory, private_directory = Path(public_directory), Path(private_directory)
    if not public_directory.is_absolute() or not private_directory.is_absolute():
        raise ResearchError('ml_pilot', 'Task roots must be absolute')
    if (any(p.is_symlink() for path in (public_directory, private_directory) for p in (path, *path.parents))
            or private_directory.is_relative_to(public_directory) or public_directory.is_relative_to(private_directory)):
        raise ResearchError('ml_pilot', 'Public/private task roots must be separate nonsymlink directories')
    public_directory.mkdir(mode=0o755, parents=True, exist_ok=False)
    private_directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    result = {'schema': 'ai4r-ml-pilot-tasks:1', 'purpose': 'Informal functional examples, not official benchmark cases', 'tasks': []}
    scorer_path = Path(__file__).with_name('trusted_scoring.py')
    for kind in ('signal', 'no-signal'):
        seed = secrets.randbits(128)
        task_id, public, holdout = task_bytes(kind, seed)
        visible = public_directory / task_id; visible.mkdir(mode=0o755)
        hidden = private_directory / task_id; hidden.mkdir(mode=0o700)
        _write(visible / 'data.json', public, 0o644)
        _write(visible / 'request.txt', (SAMPLE_REQUEST + '\n').encode(), 0o644)
        pins = {'holdout_sha256': hashlib.sha256(holdout).hexdigest(),
                'scorer_sha256': hashlib.sha256(scorer_path.read_bytes()).hexdigest()}
        _write(visible / 'scoring-pins.json', json_bytes(pins), 0o644)
        _write(hidden / 'holdout.json', holdout, 0o600)
        _write(hidden / 'generation.json', json_bytes({'kind': kind, 'seed': seed,
            'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}), 0o600)
        result['tasks'].append({'task_id': task_id, 'kind': kind, 'public_path': str(visible / 'data.json'),
            'pins_path': str(visible / 'scoring-pins.json'), 'request_path': str(visible / 'request.txt'),
            'private_holdout_path': str(hidden / 'holdout.json'), **pins})
    _write(private_directory / 'tasks.json', json_bytes(result), 0o600)
    return result


def select_task(manifest_path, task_id, state_root):
    """Publish the fixed existing scorer path only while execution is quiescent."""
    _root()
    manifest_path = Path(manifest_path)
    if any(p.is_symlink() for p in (manifest_path, *manifest_path.parents)):
        raise ResearchError('ml_pilot', 'Task manifest custody is invalid')
    info = manifest_path.stat()
    if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
        raise ResearchError('ml_pilot', 'Task manifest must be root-private')
    rows = json.loads(manifest_path.read_bytes())['tasks']
    row = next((row for row in rows if row['task_id'] == task_id), None)
    if row is None:
        raise ResearchError('ml_pilot', 'Task is outside the immutable task manifest')
    db_path = Path(state_root) / 'state/research.sqlite3'
    if db_path.exists():
        db = sqlite3.connect('file:' + str(db_path) + '?mode=ro', uri=True)
        try:
            if db.execute("SELECT COUNT(*) FROM runs WHERE state IN ('running','pending')").fetchone()[0]:
                raise ResearchError('ml_pilot', 'Stop or reconcile active research before switching private tasks')
        finally:
            db.close()
    for status in Path('/proc').glob('[0-9]*/status'):
        try:
            lines = status.read_text().splitlines()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if any(line.startswith('Uid:') and '10002' in line.split()[1:] for line in lines):
            raise ResearchError('ml_pilot', 'An executor process still exists; task switch is blocked')
    public = Path(row['public_path']).read_bytes()
    holdout_path = Path(row['private_holdout_path'])
    if any(p.is_symlink() for p in (holdout_path, *holdout_path.parents)):
        raise ResearchError('ml_pilot', 'Private task path custody changed')
    metadata = holdout_path.stat()
    if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise ResearchError('ml_pilot', 'Private task must remain root-owned and private')
    holdout = holdout_path.read_bytes()
    if hashlib.sha256(holdout).hexdigest() != row['holdout_sha256']:
        raise ResearchError('ml_pilot', 'Private task bytes changed')
    private = json.loads(holdout)
    if private['public_data_sha256'] != hashlib.sha256(public).hexdigest():
        raise ResearchError('ml_pilot', 'Public and private tasks differ')
    destination = Path(PRIVATE_PATH)
    if any(p.is_symlink() for p in (destination, *destination.parents)) or destination.parent.stat().st_uid != 0 or stat.S_IMODE(destination.parent.stat().st_mode) != 0o700:
        raise ResearchError('ml_pilot', 'Original scorer private directory custody is invalid')
    if destination.exists():
        old = destination.read_bytes(); archive = manifest_path.parent / ('previous-' + hashlib.sha256(old).hexdigest() + '.json')
        if not archive.exists():
            _write(archive, old, 0o600)
    temporary = destination.with_name('holdout-select-' + secrets.token_hex(8))
    _write(temporary, holdout, 0o600)
    os.replace(temporary, destination)
    return {k: v for k, v in row.items() if k != 'private_holdout_path'}


def capture_profile(manifest_path, task_id, profile_directory, state_root):
    """Select a root holdout, then capture the ordinary app-owned ML configuration."""
    row = select_task(manifest_path, task_id, state_root)
    # Permanent child credentials: no saved root identity or supplementary groups.
    completed = subprocess.run([sys.executable, '-m', 'jiuwenswarm.research.ml_pilot', 'capture-public',
        '--public-path', row['public_path'], '--pins-path', row['pins_path'],
        '--profile-directory', str(profile_directory), '--state-root', str(state_root)],
        user=10001, group=10001, extra_groups=[], check=True, capture_output=True, text=True)
    return {'task': row, 'capture': json.loads(completed.stdout), 'qualification_claimed': False,
            'limitation': 'Functional synthetic ML task; no measured result or admission invented'}


def capture_public_profile(public_path, pins_path, profile_directory, state_root):
    if os.getuid() != 10001 or os.geteuid() != 10001 or os.getgid() != 10001 or os.getgroups():
        raise ResearchError('ml_pilot', 'Public profile capture requires permanent app credentials without extra groups')
    from .local_profile import capture_local_profile
    from .state import SQLiteRunStore
    store = SQLiteRunStore(state_root, input_root='/workspace/input', recover=False)
    try:
        return capture_local_profile(store, profile_directory,
            public_dataset_path=public_path, scoring_pins=json.loads(Path(pins_path).read_bytes()),
            requested_model='gpt-6-luna', evidence_aware_review=True)
    finally:
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    prepare = sub.add_parser('prepare'); prepare.add_argument('--public-directory', type=Path, required=True)
    prepare.add_argument('--private-directory', type=Path, required=True)
    select = sub.add_parser('select'); select.add_argument('--manifest', type=Path, required=True)
    select.add_argument('--task-id', required=True); select.add_argument('--state-root', type=Path, default=Path('/var/lib/ai4r'))
    capture = sub.add_parser('capture'); capture.add_argument('--manifest', type=Path, required=True)
    capture.add_argument('--task-id', required=True); capture.add_argument('--profile-directory', type=Path, required=True)
    capture.add_argument('--state-root', type=Path, default=Path('/var/lib/ai4r'))
    public = sub.add_parser('capture-public', help=argparse.SUPPRESS)
    public.add_argument('--public-path', required=True); public.add_argument('--pins-path', required=True)
    public.add_argument('--profile-directory', type=Path, required=True)
    public.add_argument('--state-root', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare_tasks(args.public_directory, args.private_directory)
    elif args.action == 'capture':
        result = capture_profile(args.manifest, args.task_id, args.profile_directory, args.state_root)
    elif args.action == 'capture-public':
        result = capture_public_profile(args.public_path, args.pins_path, args.profile_directory, args.state_root)
    else:
        result = select_task(args.manifest, args.task_id, args.state_root)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
