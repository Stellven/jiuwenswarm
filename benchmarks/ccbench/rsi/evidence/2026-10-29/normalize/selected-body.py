import copy
import hashlib
from pathlib import PurePosixPath

from ...contracts import ResearchError, validate
from ...runner import ProducedArtifact
from ...state import json_bytes
from ..packet import MAX_BYTES, PACKET
from ..table_normalize.worker import normalize


def _produced(value):
    validate(PACKET, value)
    encoded = json_bytes(value)
    if len(encoded) > MAX_BYTES:
        raise ResearchError('packet_limit', 'Packet exceeds 1 MiB')
    names = []
    for item in value['files']:
        name = item['path']
        if (not name or '\\' in name or ':' in name or name.startswith('/')
                or any(p in {'', '.', '..'} for p in name.split('/'))
                or PurePosixPath(name).is_absolute()):
            raise ResearchError('packet_path', 'Files must have normalized relative paths')
        names.append(name)
        if hashlib.sha256(item['text'].encode('utf-8')).hexdigest() != item['sha256']:
            raise ResearchError('packet_hash', 'File text does not match its digest')
    if len(set(names)) != len(names):
        raise ResearchError('packet_path', 'Duplicate file path')
    return ProducedArtifact(encoded, PACKET, 'application/json', 'result.json')


async def execute(ctx, inputs):
    packet = inputs['packet']
    data = dict(packet['data'], table=normalize(packet))
    result = copy.deepcopy(dict(packet, data=data))
    result['limitations'] = list(dict.fromkeys(result['limitations']))
    return {'result': _produced(result)}
