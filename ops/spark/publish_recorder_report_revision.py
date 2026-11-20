#!/usr/bin/env python3
"""Attach reviewed copy-budget evidence to the existing C1 iteration."""
import argparse
import json
from pathlib import Path

from jiuwenswarm.factory.store import Store

from import_evidence import append_once, safe_bytes

TASK = 'spark-star-observability-event-recorder'
ITERATION = 'spark-c1-functional'


def publish(base, analysis_artifacts, method):
    home = base / 'factory-runs/star-observability_event_recorder'
    output = base / 'OPS/iterations' / ITERATION
    with Store(home) as store:
        existing = store.read(TASK, ITERATION + ':report')
        record = existing['values']
        base_report = record['report']['artifact_id']
        for artifact in analysis_artifacts:
            store.read_artifact(TASK, artifact)
        original = store.artifact_bytes(TASK, base_report)
        addendum = safe_bytes(output / 'copy-budget-addendum.md')
        data = original.rstrip() + b'\n\n' + addendum.rstrip() + b'\n'
        report_id = ITERATION + '/report-v2.md'
        updated = store.put_artifact(TASK, report_id, data, 'text/markdown', None)
        record['report'].update(artifact_id=report_id, sha256=updated['sha256'], supersedes_artifact_id=base_report,
                                supersedes_observation_id=existing['obs_id'], revision=2)
        record['analysis']['output_artifact_ids'].extend(analysis_artifacts)
        if method and method not in record['analysis']['ccs']:
            record['analysis']['ccs'].append(method)
        attachments = list(dict.fromkeys([*existing['source_artifacts'], report_id, base_report, *analysis_artifacts]))
        append_once(store, TASK, dict(obs_id=ITERATION + ':report-v2', kind='factory_iteration_report_revision',
                    values=record, source_artifacts=attachments))
        (output / 'report-v2.md').write_bytes(data)
        (output / 'iteration-v2.json').write_text(json.dumps(record, indent=2) + '\n')
        return dict(home=str(home), task_id=TASK, artifact_id=report_id, sha256=updated['sha256'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=Path.home() / 'predemo-spark')
    parser.add_argument('--analysis-artifact', action='append', required=True)
    parser.add_argument('--analysis-method', type=Path, help='JSON with id, version and sealed release of analysis capsule')
    args = parser.parse_args()
    method = json.loads(safe_bytes(args.analysis_method)) if args.analysis_method else None
    print(json.dumps(publish(args.base.resolve(), args.analysis_artifact, method), indent=2))
