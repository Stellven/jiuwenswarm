#!/usr/bin/env python3
"""Reject unsupported tool flags using cached image-specific help."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[2]
STATE = Path(os.environ.get('FACTORY_LAB_STATE', '~/.jiuwenswarm-factory/lab')).expanduser()
FLAG = re.compile(r'(?<![\w-])(--?[A-Za-z][A-Za-z0-9_-]*)(?![\w-])')


def docker_help(image, tool):
    command = ['docker', 'run', '--rm', '--runtime', 'nvidia', '--entrypoint',
               '/app/' + tool, image, '--help']
    prefix = shlex.split(os.environ.get('DOCKER_CMD_PREFIX', ''))
    if prefix:
        command = prefix + [shlex.join(command)]
    completed = subprocess.run(command, capture_output=True, text=True, check=True)
    return completed.stdout + '\n' + completed.stderr


def get_help(image, tool, runner=None, cache_dir=None):
    cache = Path(cache_dir or os.environ.get('ABRUN_PREFLIGHT_CACHE_DIR', STATE / 'preflight'))
    key = hashlib.sha256((image + '\0' + tool).encode()).hexdigest()
    path = cache / (key + '.txt')
    if path.exists():
        return path.read_text()
    if runner is None:
        override = os.environ.get('ABRUN_PREFLIGHT_RUNNER')
        if override:
            def runner(image, tool):
                return subprocess.run(shlex.split(override) + [image, tool, '--help'],
                                      capture_output=True, text=True, check=True).stdout
        else:
            runner = docker_help
    help_text = runner(image, tool)
    if not isinstance(help_text, str) or not help_text.strip():
        raise ValueError('empty help response')
    cache.mkdir(parents=True, exist_ok=True)
    path.write_text(help_text)
    return help_text


def check(image, tool, argv, runner=None, cache_dir=None):
    help_text = get_help(image, tool, runner, cache_dir)
    supported = set(FLAG.findall(help_text))
    offending = []
    for arg in argv:
        if arg == '--':
            break
        if not re.match(r'^--?[A-Za-z]', arg):
            continue
        flag = arg.split('=', 1)[0]
        if flag not in supported and flag not in offending:
            offending.append(flag)
    if offending:
        raise ValueError('unsupported flags: ' + ', '.join(offending))
    return help_text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image')
    parser.add_argument('tool')
    parser.add_argument('argv', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.argv[1:] if args.argv[:1] == ['--'] else args.argv
    try:
        check(args.image, args.tool, argv)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'preflight: {exc}\n')
    print('preflight: ok')


if __name__ == '__main__':
    main()
