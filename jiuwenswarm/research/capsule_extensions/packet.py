"""Bounded interoperable file/data envelope; provenance can only accumulate."""
import copy
import hashlib
from pathlib import PurePosixPath

from ..contracts import ResearchError, validate
from ..runner import ProducedArtifact
from ..state import json_bytes

PACKET = 'urn:ai4r:work-packet:1.0.0'
MAX_BYTES = 1024 * 1024


def validate_packet(value):
    validate(PACKET, value)
    if len(json_bytes(value)) > MAX_BYTES:
        raise ResearchError('packet_limit', 'Packet exceeds 1 MiB')
    names = []
    for item in value['files']:
        name = item['path']
        if (not name or '\\' in name or ':' in name or name.startswith('/')
                or any(p in {'', '.', '..'} for p in name.split('/')) or PurePosixPath(name).is_absolute()):
            raise ResearchError('packet_path', 'Files must have normalized relative paths')
        names.append(name)
        if hashlib.sha256(item['text'].encode('utf-8')).hexdigest() != item['sha256']:
            raise ResearchError('packet_hash', 'File text does not match its digest')
    if len(set(names)) != len(names):
        raise ResearchError('packet_path', 'Duplicate file path')
    return value


def output_packet(original, *, data=None, files=None, low_trust=False, provenance=None, limitations=()):
    result = copy.deepcopy(validate_packet(original))
    if data is not None:
        result['data'] = copy.deepcopy(data)
    if files is not None:
        result['files'] = [{'path': f['path'], 'text': f['text'], 'sha256': hashlib.sha256(f['text'].encode()).hexdigest()} for f in files]
    if low_trust:
        result['trust'] = 'low'
    if provenance is not None and provenance not in result['provenance']:
        result['provenance'].append(copy.deepcopy(provenance))
    result['limitations'] = list(dict.fromkeys([*result['limitations'], *limitations]))
    return validate_packet(result)


def inherited(original, result):
    validate_packet(original)
    validate_packet(result)
    return ((original['trust'] != 'low' or result['trust'] == 'low')
            and all(p in result['provenance'] for p in original['provenance'])
            and all(p in result['limitations'] for p in original['limitations']))


def produced(value):
    return ProducedArtifact(json_bytes(validate_packet(value)), PACKET, 'application/json', 'result.json')
