"""Rebuild expected report from original content and verify every retained byte."""
import hashlib
import html
import json

from ...contracts import ResearchError
from ..packet import validate_packet


def escape(text):
    special = set('\\`*_{}[]()#+-.!|>')
    return ''.join('\\' + c if c in special else c for c in html.escape(text, quote=False))


def check(ctx, inputs, outputs):
    schema = integrity = False
    try:
        source, result = inputs['packet'], outputs['result']
        validate_packet(source)
        validate_packet(result)
        schema = True
        report = source['data']['report']
        if set(report) != {'path', 'title', 'sections', 'data_keys'}: raise ValueError('request')
        title = report['title']
        if type(title) is not str or not title.strip() or len(title) > 200 or any(c in title for c in '\r\n'): raise ValueError('title')
        sections, keys = report['sections'], report['data_keys']
        if type(sections) is not list or len(sections) > 16 or type(keys) is not list or len(keys) > 16 or len(set(keys)) != len(keys): raise ValueError('sections')
        parts = ['# ' + escape(title), 'Trust: ' + source['trust']]
        for section in sections:
            if (type(section) is not dict or set(section) != {'heading', 'text'} or type(section['heading']) is not str
                    or not section['heading'].strip() or len(section['heading']) > 200 or any(c in section['heading'] for c in '\r\n')
                    or type(section['text']) is not str or len(section['text']) > 262144): raise ValueError('section')
            parts.append('## ' + escape(section['heading']) + '\n\n' + escape(section['text']))
        for key in keys:
            if type(key) is not str or key not in source['data'] or key in {'report', 'report_manifest'} or len(key) > 200 or any(c in key for c in '\r\n'): raise ValueError('data key')
            parts.append('## ' + escape(key) + '\n\n```json\n' + json.dumps(source['data'][key], ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n```')
        if source['limitations']:
            parts.append('## Limitations\n\n' + '\n'.join('- ' + escape(x) for x in source['limitations']))
        text = '\n\n'.join(parts) + '\n'
        path = report['path']
        if any(f['path'] == path for f in source['files']): raise ValueError('overwrite')
        digest = hashlib.sha256(text.encode()).hexdigest()
        manifest = {'path': path, 'sha256': digest, 'size_bytes': len(text.encode()), 'data_keys': keys,
            'input_files': [{'path': f['path'], 'sha256': f['sha256']} for f in source['files']],
            'trust': source['trust'], 'provenance': source['provenance']}
        expected = dict(source, data=dict(source['data'], report_manifest=manifest),
            files=[*source['files'], {'path': path, 'text': text, 'sha256': digest}])
        integrity = result == expected
    except (ResearchError, KeyError, ValueError, TypeError):
        pass
    return [{'check_id': key, 'outcome': 'PASS' if ok else 'FAIL', 'reason': reason, 'evidence_refs': list(ctx.output_refs.values())}
        for key, ok, reason in [('packet_schema', schema, 'Bounded file paths, envelope and SHA-256 digests'),
            ('packet_integrity', integrity, 'Original prose, selected data, input files, manifest and low-trust label preserved')]]
