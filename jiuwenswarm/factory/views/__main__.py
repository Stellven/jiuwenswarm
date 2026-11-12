"""python -m jiuwenswarm.factory.views RUN_DIR_OR_TASK --out view.html"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .activity import load_activity
from .render import render_html
from ..store import FactoryError


def main(argv=None):
    parser = argparse.ArgumentParser(description='Offline expert activity and factory change evidence view')
    parser.add_argument('source', help='Recorded lab run directory or factory task ID')
    parser.add_argument('--out', type=Path, required=True, help='Self-contained HTML destination')
    parser.add_argument('--json-out', type=Path, help='Also write expert_activity/1 JSON')
    parser.add_argument('--home', type=Path, help='Factory home for task IDs (read-only; temp snapshot)')
    parser.add_argument('--trace', type=Path, help='Explicit CSV or expert_trace/2 JSONL for a run directory')
    parser.add_argument('--trace-run', help='Select one session from an appended trace')
    parser.add_argument('--mode', choices=('replay', 'live', 'synthetic'), default='replay',
                        help='Display label; live is an offline snapshot without polling')
    args = parser.parse_args(argv)
    try:
        homes = {Path('~/.jiuwenswarm-factory').expanduser().resolve(),
                 Path(args.home or os.environ.get('FACTORY_HOME', '~/.jiuwenswarm-factory')).expanduser().resolve()}
        input_dir = Path(args.source).expanduser().resolve()
        inputs = {p.resolve() for p in (args.trace,) if p is not None}
        if input_dir.is_dir():
            inputs.update(p.resolve() for p in input_dir.iterdir() if p.is_file())
        for destination in (args.out, args.json_out):
            if destination is None:
                continue
            path = destination.expanduser().resolve()
            if any(path == home or path.is_relative_to(home) for home in homes):
                raise ValueError('View outputs must be outside factory homes')
            if path in inputs:
                raise ValueError('View output must not overwrite input evidence')
        if args.json_out is not None and args.out.expanduser().resolve() == args.json_out.expanduser().resolve():
            raise ValueError('--out and --json-out must be different files')
        doc = load_activity(args.source, home=args.home, trace_path=args.trace, trace_run=args.trace_run, mode=args.mode)
        page = render_html(doc)
        args.out.expanduser().write_text(page, encoding='utf-8')
        if args.json_out:
            args.json_out.expanduser().write_text(json.dumps(doc, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    except (ValueError, OSError, FactoryError) as exc:
        parser.exit(2, f'views: {exc}\n')
    print(f'{args.out} · {doc["schema"]} · {len(doc["activity"]["events"])} trace rows · {doc["provenance"]["mode"]}')


if __name__ == '__main__':
    main()
