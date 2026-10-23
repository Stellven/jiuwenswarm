"""Prepare optional candidates and immutable requests, never self-activate."""
import argparse
import json
from pathlib import Path
from contextlib import closing

from .catalog import candidates
from ..capability_planning import capability_plan_policy
from ..state import SQLiteRunStore
from ..contracts import ResearchError


def prepare_requests(store, name, *, memory_mb=4096):
    available = candidates(store)
    if name not in available:
        raise ResearchError('extension_unavailable', 'No installed optional capsule with that name')
    asset, _ = available[name]
    declaration = store.read_record(asset['declaration_ref'])
    version = declaration['identity']['version_label']
    identity = asset['declaration_ref']['sha256']
    actions = {
        'associate-checks': {'declaration_ref': asset['declaration_ref'], 'bundle_ref': asset['bundle_ref'], 'profile_ref': asset['profile_ref'], 'evidence_refs': []},
        'admit': {'declaration_ref': asset['declaration_ref'], 'body_refs': asset['body_refs'], 'memory_mb': memory_mb, 'evidence_refs': []},
        'standing': {'name': name, 'version': version, 'to_standing': 'active', 'effect_scope': 'live_plans', 'reason': 'Explicit human activation of optional M1 capsule'},
    }
    requests = {command: store.put_blob(json.dumps(dict(value, schema='ai4r-library-action:1', id=identity + ':' + command), sort_keys=True).encode(), media_type='application/json') for command, value in actions.items()}
    return {'name': name, 'asset': asset, 'requests': requests,
        'policy_ref': store.put_record('plan-policy', capability_plan_policy()),
        'status': 'candidate_only', 'qualification': 'NOT_RUN',
        'next': 'Independent checking-asset calibration is required before admit/standing. Existing human Library commands enforce it.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['list', 'prepare'])
    parser.add_argument('--store', required=True)
    parser.add_argument('--name')
    args = parser.parse_args()
    with closing(SQLiteRunStore(Path(args.store), recover=False)) as store:
        result = sorted(candidates(store)) if args.command == 'list' else prepare_requests(store, args.name)
        print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
