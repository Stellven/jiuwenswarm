"""Deterministically envelope a structured paper summary without asserting its truth."""
import hashlib
import json
from pathlib import Path

from ...contracts import ResearchError, validate
from ..assets_v2 import prepare as prepare_asset
from ..packet import output_packet, produced

SUMMARY = 'urn:ai4r:paper-summary:1.0.0'


def convert(summary):
    validate(SUMMARY, summary)
    document_refs = [row['source_ref'] for row in summary['documents']]
    refs = [summary['brief_ref'], summary['documents_ref'], *document_refs]
    # Preserve stable order while avoiding duplicate provenance keys.
    provenance = list({(ref['id'], ref['sha256']): ref for ref in refs}.values())
    text = json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    packet = {'schema_version': '1.0.0', 'data': {'paper_summary': summary,
        'source_refs': document_refs, 'brief_ref': summary['brief_ref'], 'documents_ref': summary['documents_ref'],
        'report': {'path': 'converted/paper-summary.md', 'title': summary['title'],
            'sections': [{'heading': name.title(), 'text': summary['sections'][name]['text']}
                for name in ('problem', 'method', 'results', 'contributions', 'limitations')],
            'data_keys': ['paper_summary', 'source_refs']}},
        'files': [{'path': 'paper_summary.json', 'text': text,
                   'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()}],
        'trust': 'low', 'provenance': provenance,
        'limitations': ['This envelope preserves the supplied summary and source references; it does not verify scientific claims.']}
    return packet


async def execute(ctx, inputs):
    try:
        return {'result': produced(convert(inputs['summary']))}
    except (KeyError, TypeError) as error:
        raise ResearchError('summary_adapter_input', 'Malformed paper summary input') from error


def prepare(store):
    return prepare_asset(store, Path(__file__).parent,
        name='utility.summary_to_packet', version='m1-1',
        summary='Deterministically preserve a structured paper summary and all source refs in a low-trust work packet',
        input_name='summary', input_type='paper_summary', input_schema=SUMMARY)
