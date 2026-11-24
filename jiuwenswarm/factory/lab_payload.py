"""The bytes of a result under test, shipped with a lab package.

A lab task names each subject by identity. When a subject says ``transfer: attach`` the
factory also ships its bytes: a container image as a ``docker save`` archive, or any
stored artifact (a native build tarball, a model file, a patch) as it is. The archive's
digest is sealed into the package, and a lab can check that an image archive holds the
image the package names before loading it, with or without Docker.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import tarfile
import hashlib

DOCKER_ARCHIVE = 'application/vnd.docker.image.archive+tar'


def _docker(argv, timeout):
    from .config import DOCKER_PREFIX
    prefix = shlex.split(os.environ.get('FACTORY_PAYLOAD_DOCKER_PREFIX', DOCKER_PREFIX))
    command = prefix + [shlex.join(argv)] if prefix else argv
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def _blob_digest(archive, name):
    member = archive.extractfile(name)
    if member is None:
        return None
    digest = hashlib.sha256()
    for block in iter(lambda: member.read(1 << 20), b''):
        digest.update(block)
    return 'sha256:' + digest.hexdigest()


def archive_image_ids(path):
    """Ids a ``docker save`` archive of one image answers to, each checked against its bytes.

    The classic image store names an image by its config digest (``manifest.json``); the
    containerd image store names it by the digest of its OCI index or manifest
    (``index.json``). Both are returned when present.
    """
    ids = []
    with tarfile.open(path) as archive:
        names = set(archive.getnames())
        try:
            manifest = json.load(archive.extractfile('manifest.json'))
        except (KeyError, ValueError, TypeError):
            manifest = None
        if isinstance(manifest, list) and len(manifest) == 1 and manifest[0].get('Config') in names:
            ids.append(_blob_digest(archive, manifest[0]['Config']))
        try:
            index = json.load(archive.extractfile('index.json'))
        except (KeyError, ValueError, TypeError):
            index = None
        entries = (index or {}).get('manifests') or []
        if len(entries) == 1:
            digest = entries[0].get('digest', '')
            blob = 'blobs/' + digest.replace(':', '/', 1)
            if blob in names and _blob_digest(archive, blob) == digest:
                ids.insert(0, digest)
    return [i for i in ids if i]


def archive_image_id(path):
    """The id Docker shows for the image in a ``docker save`` archive, or None."""
    ids = archive_image_ids(path)
    return ids[0] if ids else None


def save_image(image, destination, expected_id=None, timeout=3600):
    """``docker save`` one image to ``destination`` and return its image id."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    done = _docker(['docker', 'save', '-o', str(destination), image], timeout)
    if done.returncode != 0 or not destination.is_file():
        raise ValueError(f'docker save {image} failed: {(done.stderr or done.stdout).strip()[-400:]}')
    ids = archive_image_ids(destination)
    if not ids:
        raise ValueError(f'docker save {image} wrote an archive without one image manifest')
    if expected_id and expected_id not in ids:
        raise ValueError(f'docker save {image} holds {ids[0]}, not the subject image {expected_id}')
    return expected_id or ids[0]


def load_image(path, expected_id=None, timeout=3600):
    """``docker load`` an archive after checking it holds ``expected_id``; return the id."""
    ids = archive_image_ids(path)
    if not ids or (expected_id and expected_id not in ids):
        raise ValueError(f'image archive holds {ids[0] if ids else "no image"}, not {expected_id}')
    image_id = expected_id or ids[0]
    done = _docker(['docker', 'load', '-i', str(path)], timeout)
    if done.returncode != 0:
        raise ValueError(f'docker load failed: {(done.stderr or done.stdout).strip()[-400:]}')
    inspected = _docker(['docker', 'image', 'inspect', '--format', '{{.Id}}', image_id], 60)
    if inspected.returncode != 0 or inspected.stdout.strip() != image_id:
        raise ValueError(f'docker does not list {image_id} after loading')
    return image_id
