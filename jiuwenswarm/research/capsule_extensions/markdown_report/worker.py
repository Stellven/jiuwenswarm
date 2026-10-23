import hashlib
import html
import json
import re

from ...contracts import ResearchError
from ..packet import output_packet, produced, validate_packet


def plain(text):
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
        blocks = ['# ' + plain(request['title']), 'Trust: ' + packet['trust']]
        for section in sections:
            if (type(section) is not dict or set(section) != {'heading', 'text'} or type(section['heading']) is not str
                    or not section['heading'].strip() or len(section['heading']) > 200 or any(c in section['heading'] for c in '\r\n')
                    or type(section['text']) is not str or len(section['text']) > 262144):
                raise ValueError('bounded heading and text required')
            blocks.append('## ' + plain(section['heading']) + '\n\n' + plain(section['text']))
        for key in keys:
            if type(key) is not str or key not in packet['data'] or key in {'report', 'report_manifest'} or len(key) > 200 or any(c in key for c in '\r\n'):
                raise ValueError('explicit existing data field required')
            blocks.append('## ' + plain(key) + '\n\n```json\n' + json.dumps(packet['data'][key], ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n```')
        if packet['limitations']:
            blocks.append('## Limitations\n\n' + '\n'.join('- ' + plain(x) for x in packet['limitations']))
        text = '\n\n'.join(blocks) + '\n'
        path = request['path']
        if any(f['path'] == path for f in packet['files']):
            raise ValueError('report would overwrite an input artifact')
        report = {'path': path, 'text': text}
        manifest = {'path': path, 'sha256': hashlib.sha256(text.encode()).hexdigest(), 'size_bytes': len(text.encode()),
            'data_keys': keys, 'input_files': [{'path': f['path'], 'sha256': f['sha256']} for f in packet['files']],
            'trust': packet['trust'], 'provenance': packet['provenance']}
        return output_packet(packet, data=dict(packet['data'], report_manifest=manifest), files=[*packet['files'], report])
    except (KeyError, ValueError, TypeError) as error:
        raise ResearchError('report_input', str(error)[:200]) from error


async def execute(ctx, inputs):
    return {'result': produced(render(inputs['packet']))}
