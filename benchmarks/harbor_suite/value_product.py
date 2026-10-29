"""Prepare the existing sequential runner without dispatching model work.

This separates public upload/intake from submission so the campaign coordinator
can reserve a whole protected run bound against the *actual persisted request
ID*. Execute afterward with the existing benchmark-runner resume command; all
submission, reconciliation, cancellation and collection remain its authority.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path


async def prepare(args):
    from jiuwenswarm.research_sidecar.client import ResearchClient
    from jiuwenswarm.research_sidecar.sequential import create_campaign, SequentialRunner, campaign_lock
    folder, campaign = create_campaign(args.cases, args.inputs, args.output,
        campaign_id=args.campaign_id, endpoint=args.endpoint,
        expected_build=args.expected_build, http_authority=args.http_authority)
    client = ResearchClient(args.endpoint, args.token_file, http_authority=args.http_authority)
    runner = SequentialRunner(client, folder, campaign)
    try:
        with campaign_lock(folder):
            await runner.readiness()
            rows = list(runner.rows())
            for case, row in rows:
                if case['setup'] or case['steps'] or case['collection']:
                    raise ValueError('value preparation permits public inputs only; no host commands')
                if not await runner.prepare(case, row):
                    raise ValueError('intake preparation blocked; retain the original campaign')
            return {'schema': 'ai4r-value-product-preparation:1', 'campaign_dir': str(folder),
                'model_calls': 0, 'submitted': False,
                'requests': [{'request_id': r['request_id'], 'run_id': r['run_id'],
                    'submission': r['submission'], 'input_inventory': r['inputs']} for _, r in rows],
                'next_step': 'Reserve each exact request ID and verified protected call bound before benchmark-runner resume.'}
    finally:
        runner.close()
        await client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('cases', 'inputs', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--campaign-id', required=True)
    for name in ('endpoint', 'token-file', 'expected-build', 'http-authority'):
        parser.add_argument('--' + name, default=os.environ.get('AI4R_' + name.upper().replace('-', '_')))
    args = parser.parse_args()
    if not all((args.endpoint, args.token_file, args.expected_build)):
        parser.error('explicit endpoint, credential file and actual build pin required')
    print(json.dumps(asyncio.run(prepare(args)), ensure_ascii=False))


if __name__ == '__main__':
    main()
