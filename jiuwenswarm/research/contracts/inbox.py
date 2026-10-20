"""Read-only original-byte inbox adapter; no imports from RSI or side records."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat

from . import ResearchError, validate


class SignedInboxReader:
    MAX_BYTES = 4 * 1024 * 1024  # Existing private original-byte transport limit.

    def __init__(self, root, *, custodian_uid=12002, custodian_gid=13000):
        self.root = Path(root)
        self.uid, self.gid = custodian_uid, custodian_gid
        if os.name != 'posix' or not self.root.is_absolute() or '..' in self.root.parts:
            raise ResearchError('rsi_custody', 'A literal absolute Linux custodian inbox is required')

    def _root_fd(self):
        descriptor = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in self.root.parts[1:]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                os.close(descriptor); descriptor = child
            info = os.fstat(descriptor)
            if (info.st_uid != self.uid or info.st_gid != self.gid or info.st_mode & 0o022
                    or not stat.S_ISDIR(info.st_mode)):
                raise ResearchError('rsi_custody', 'Inbox has an unexpected owner, group or writer')
            return descriptor
        except BaseException:
            os.close(descriptor); raise

    def _read(self, root_fd, name):
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=root_fd)
        try:
            info = os.fstat(descriptor)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != self.uid
                    or info.st_gid != self.gid or info.st_mode & 0o022 or info.st_size > self.MAX_BYTES):
                raise ResearchError('rsi_custody', 'Original-byte custody or transport size is invalid')
            with os.fdopen(descriptor, 'rb', closefd=False) as stream:
                raw = stream.read(self.MAX_BYTES + 1)
            if len(raw) > self.MAX_BYTES:
                raise ResearchError('rsi_custody', 'Original-byte transport size is invalid')
            return raw
        finally:
            os.close(descriptor)

    def read(self, ref):
        validate('Ref', ref)
        descriptor = None
        try:
            descriptor = self._root_fd()
            index = json.loads(self._read(descriptor, 'original-byte-index.json').decode('utf-8'))
            if (not isinstance(index, dict) or set(index) != {'schema', 'refs'}
                    or index['schema'] != 'ai4r-original-bytes:1' or not isinstance(index['refs'], dict)
                    or index['refs'].get(ref['id']) != ref['sha256']):
                raise ResearchError('rsi_refs', 'Opaque original-byte identity is not published in the inbox')
            raw = self._read(descriptor, ref['sha256'] + '.bytes')
            if hashlib.sha256(raw).hexdigest() != ref['sha256']:
                raise ResearchError('rsi_refs', 'Published original bytes do not match the exact immutable Ref')
            return raw
        except (OSError, ValueError, UnicodeError) as error:
            raise ResearchError('rsi_custody', 'Protected original-byte inbox is unavailable or invalid') from error
        finally:
            if descriptor is not None: os.close(descriptor)
