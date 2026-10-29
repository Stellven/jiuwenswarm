"""Render only explicitly selected packet content into one escaped Markdown file."""
import hashlib
import html
import json
from pathlib import Path
import re

from ...contracts import ResearchError
from ..assets_v2 import prepare as prepare_asset
from ..packet import output_packet, produced, validate_packet


def escape(text):
    return re.sub(r'([\\`*_{}\[\]()#+\-.!|>])', r'\\\1', html.escape(text, quote=False))


def render(packet):
    validate_packet(packet)
    try:
        request = packet['data']['report']
        if set(request) != {'path', 'title', 'sections', 'data_keys'}:
            raise ValueError('explicit report path, title, sections and data_keys required')
        if type(request['title']) is not str or not request['title'].strip() or '\n' in request['title'] or '\r' in request['title'] or len(request['title']) > 200:
            raise ValueError('bounded single-line title required')
        sections, keys = request['sections'], request['data_keys']
        if type(sections) is not list or len(sections) > 16 or type(keys) is not list or len(keys) > 16 or len(set(keys)) != len(keys):
            raise ValueError('bounded sections and unique data_keys required')
        blocks = ['# ' + escape(request['title']), 'Trust: ' + packet['trust']]
        for section in sections:
            if (type(section) is not dict or set(section) != {'heading', 'text'} or type(section['heading']) is not str
                    or not section['heading'].strip() or len(section['heading']) > 200 or any(c in section['heading'] for c in '\r\n')
                    or type(section['text']) is not str or len(section['text']) > 262144):
                raise ValueError('bounded heading and text required')
            blocks.append('## ' + escape(section['heading']) + '\n\n' + escape(section['text']))
        for key in keys:
            if type(key) is not str or key not in packet['data'] or key in {'report', 'report_manifest'} or len(key) > 200 or any(c in key for c in '\r\n'):
                raise ValueError('explicit existing data field required')
            blocks.append('## ' + escape(key) + '\n\n```json\n' + json.dumps(packet['data'][key], ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n```')
        if packet['limitations']:
            blocks.append('## Limitations\n\n' + '\n'.join('- ' + escape(item) for item in packet['limitations']))
        text = '\n\n'.join(blocks) + '\n'
        path = request['path']
        if any(item['path'] == path for item in packet['files']):
            raise ValueError('report would overwrite an input artifact')
        digest = hashlib.sha256(text.encode()).hexdigest()
        manifest = {'path': path, 'sha256': digest, 'size_bytes': len(text.encode()), 'data_keys': keys,
            'input_files': [{'path': item['path'], 'sha256': item['sha256']} for item in packet['files']],
            'trust': packet['trust'], 'provenance': packet['provenance']}
        result = output_packet(packet, data=dict(packet['data'], report_manifest=manifest),
            files=[*packet['files'], {'path': path, 'text': text}])
        return result
    except (KeyError, TypeError, ValueError) as error:
        raise ResearchError('report_input', str(error)[:200]) from error


async def execute(ctx, inputs):
    return {'result': produced(render(inputs['packet']))}


def prepare(store):
    return prepare_asset(store, Path(__file__).parent,
        name='utility.packet_report', version='m1-1',
        summary='Render explicitly selected packet content into an escaped Markdown report without adding research claims')
