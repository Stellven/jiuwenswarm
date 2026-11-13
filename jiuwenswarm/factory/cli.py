"""Native factory CLI. Service imports are lazy; help and status stay offline."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .migration import check_legacy_config_or_exit


def format_status(value, plain=False, evidence=None):
    from .story import duration, evaluation_summary, paint, wrap
    import time
    decision = value.get('latest_decision') or {}
    used = value.get('budget_used', {})
    task = (evidence or {}).get('tasks', [{}])[0]
    limit = task.get('budget', value.get('budget', {}))
    lines = wrap(f"Task: {value['task_id']} · {value.get('outcome') or 'in progress'} · rev {decision.get('rev', 0)}")
    lines += wrap(f"Budget: {used.get('turns', 0)}/{limit.get('max_turns', '?')} turns · "
                  f"{duration(used.get('wall_clock_s', 0))}/{duration(limit['wall_clock_s']) if 'wall_clock_s' in limit else '?'}")
    action = decision.get('action', {})
    def compact(text):
        parts = wrap(text, '  ')
        if len(parts) > 3:
            return parts[:2] + [parts[2][:98] + ' …']
        return parts
    lines += ['Now']
    lines += compact(f"{action.get('type', 'awaiting decision')}: " +
                  str(action.get('next_bounded_operation', '')))
    lines += compact(decision.get('reason_for_change', ''))
    lines += ['Jobs']
    jobs = value.get('active_jobs', [])
    for job in jobs[:5]:
        history = job.get('history', [])
        since = job.get('started') or (history[0].get('created') if history else time.time())
        lines += wrap(f"{job.get('kind', '?')} · {job.get('state', '?')} · age {duration(time.time() - since)}", '  ')
    if len(jobs) > 5:
        lines += [f'  +{len(jobs) - 5} more jobs']
    if not jobs:
        lines += ['  idle']
    artifacts = value.get('artifacts', [])
    lines += ['Evidence']
    if evidence:
        counts = ', '.join(f'{k} {len(v)}' for k, v in evidence.items()
                           if isinstance(v, list) and k != 'events')
    else:
        counts = f"artifacts {len(artifacts)}, evaluations {len(value.get('evaluations', []))}"
    lines += wrap(counts + f" · {sum(a.get('size', 0) for a in artifacts)} bytes", '  ')
    lines += ['Last evaluation']
    evaluations = value.get('evaluations', [])
    lines += wrap(evaluation_summary(max(evaluations, key=lambda e: e.get('created', 0)))
                  if evaluations else 'none', '  ')
    lines += wrap('Readiness: ' + ' · '.join(f"{'✓' if ready else '✗'} {key}"
                  for key, ready in value.get('readiness', {}).items()))
    return '\n'.join(paint(line, plain) for line in lines)


def readonly_status(data):
    """Match Controller.status without initializing or mutating the live store."""
    from .story import ACTIVE
    import time
    task = data['tasks'][0]
    state = data['_meta'].get('controller_state', {})
    latest = max(data.get('decisions', []), key=lambda d: d['rev'], default=None)
    active = [a for a in data.get('attempts', []) if a['state'] in ACTIVE]
    return dict(task_id=task['task_id'], objective=task['objective'],
                outcome=state.get('outcome'), latest_decision=latest, active_jobs=active,
                artifacts=[{k: a[k] for k in ('artifact_id', 'media_type', 'size')}
                           for a in data.get('artifacts', [])], evaluations=data.get('evaluations', []),
                readiness=dict(decision_published=latest is not None, jobs_idle=not active,
                               evaluations_present=bool(data.get('evaluations'))),
                budget_used=dict(turns=state.get('turns', 0), wall_clock_s=state['active_s'] if 'active_s' in state else max(0,
                    (state.get('finished') or time.time()) - state['started']) if state.get('started') is not None else 0),
                pending_attempts=state.get('pending_attempts', []), pending_questions=state.get('pending_questions', []))


async def auth(command, home):
    from .controller import configure_agent, scrub
    configure_agent({'task_id': 'auth', 'allowed_effects': []}, home=home)
    from jiuwenswarm.server.runtime.codex_subscription.service import get_service
    service = get_service()
    try:
        if command == 'login':
            started = await service.login()
            # Sign-in URL is intentionally shown; no auth tokens are printed.
            print('Open this URL to sign in:\n' + started['auth_url'], flush=True)
            for _ in range(180):
                await asyncio.sleep(2)
                result = await service.status()
                if result.get('state') not in {'signing_in', 'signed_out'}:
                    break
            else:
                raise ValueError('Timed out waiting for sign-in')
        else:
            result = await service.status()
        print(json.dumps(scrub(result), indent=2))
    finally:
        await service.transport.close()


def main(argv=None):
    check_legacy_config_or_exit()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', help='factory home (default FACTORY_HOME or ~/.jiuwenswarm-factory)')
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init', help='initialize an operator task JSON')
    init.add_argument('task_file')
    for name in ('run', 'resume', 'status', 'show', 'cancel'):
        command = sub.add_parser(name)
        command.add_argument('task_id')
        if name in {'run', 'resume'}:
            command.add_argument('--grant', action='append', default=[], help='operator grant (repeatable; default none)')
        if name in {'status', 'show'}:
            command.add_argument('--json', action='store_true')
        command.add_argument('--plain', action='store_true')
        if name == 'show':
            command.add_argument('id', nargs='?', help='evidence record ID; omit to show all records')
    baseline = sub.add_parser('baseline-import', help='operator: link the existing plain-engine build into a task (no rebuild)')
    baseline.add_argument('task_id')
    baseline.add_argument('--from-task', default='operator-bare-build')
    baseline.add_argument('--attempt')
    plan = sub.add_parser('plan', help='show revisable task graph and decision-linked history')
    plan.add_argument('task_id')
    plan.add_argument('--rev', type=int)
    plan.add_argument('--home', default=argparse.SUPPRESS)
    plan_format = plan.add_mutually_exclusive_group()
    plan_format.add_argument('--dot', action='store_true')
    plan_format.add_argument('--json', action='store_true')
    story = sub.add_parser('story', help='tell a task evidence story')
    story.add_argument('source')
    story.add_argument('--follow', action='store_true')
    story.add_argument('--plain', action='store_true')
    story.add_argument('--json', action='store_true')
    story.add_argument('--demo', action='store_true', help='presentation view: reasons shown, job/upload noise hidden, colour-coded claims')
    capsules = sub.add_parser('capsules', help='list factory Capability Capsules')
    capsules.add_argument('--plain', action='store_true')
    export = sub.add_parser('export', help='export a read-only sanitized evidence bundle')
    export.add_argument('task_id')
    export.add_argument('--out', required=True)
    export.add_argument('--extra-file', action='append', default=[])
    sub.add_parser('login', help='sign in under the factory data directory')
    sub.add_parser('auth-status', help='show factory account status without tokens')
    telemetry = sub.add_parser('telemetry', help='summarize capsule and controller telemetry')
    telemetry.add_argument('task_id', nargs='?')
    telemetry.add_argument('--json', action='store_true')
    telemetry.add_argument('--since')
    monitor = sub.add_parser('monitor', help='serve the read-only live factory monitor')
    monitor.add_argument('--port', type=int, default=8787)
    monitor.add_argument('--bind', default='127.0.0.1')
    for command in (telemetry, monitor):
        command.add_argument('--home', default=argparse.SUPPRESS)
    from .demo import add_parser as add_demo_parser
    add_demo_parser(sub)
    args = parser.parse_args(argv)
    if args.command == 'demo':
        from .demo import main as demo_main
        demo_main(args)
        return
    if args.command == 'telemetry':
        from .telemetry import show
        show(args.home, args.task_id, args.since, args.json)
        return
    if args.command == 'monitor':
        from .monitor import serve
        serve(args.home, args.bind, args.port)
        return
    if args.command == 'export':
        from .export import main as export_main
        export_main([args.task_id, '--out', args.out] + (['--home', args.home] if args.home else [])
                    + [arg for path in args.extra_file for arg in ('--extra-file', path)])
        return
    if args.command in {'story', 'capsules', 'status', 'plan'}:
        from .store import FactoryError
        import sqlite3
        try:
            if args.command == 'plan':
                from .story import load_source
                from .taskgraph import from_records, render_text, to_dot, to_json
                from .redact import sanitize
                graph = sanitize(from_records(load_source(args.task_id, args.home), args.rev))
                print(json.dumps(to_json(graph), indent=2) if args.json else
                      to_dot(graph) if args.dot else render_text(graph))
            elif args.command == 'story':
                from .story import show_story
                show_story(args.source, args.home, args.plain, args.json, args.follow, demo=args.demo)
            elif args.command == 'capsules':
                from .capsules import capsule_rows, format_capsules
                print(format_capsules(capsule_rows(), args.plain))
            else:
                from .story import load_source
                from .controller import scrub
                data = scrub(load_source(args.task_id, args.home))
                result = readonly_status(data)
                print(json.dumps(result, indent=2) if args.json else format_status(result, args.plain, data))
        except KeyboardInterrupt:
            raise SystemExit(130) from None
        except (FactoryError, ValueError, OSError, sqlite3.Error) as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(2) from None
        return
    from .controller import Controller, factory_home, scrub
    from .store import FactoryError
    home = args.home or factory_home()
    controller = None
    try:
        if args.command in {'login', 'auth-status'}:
            asyncio.run(auth(args.command, home))
            return
        controller = Controller(home, grants=getattr(args, 'grant', []))
        if args.command == 'init':
            print(controller.init_task(args.task_file))
        elif args.command in {'run', 'resume'}:
            result = asyncio.run(getattr(controller, args.command)(args.task_id))
            print(format_status(scrub(result), args.plain, controller._snapshot(args.task_id)))
        elif args.command == 'baseline-import':
            print(json.dumps(controller.import_baseline(args.task_id, args.from_task, args.attempt), indent=2))
        elif args.command == 'show':
            result = (controller.store.read(args.task_id, args.id) if args.id
                      else controller.store.dump(args.task_id))
            print(json.dumps(scrub(result), indent=2, ensure_ascii=False))
        elif args.command == 'cancel':
            print(json.dumps(scrub(controller.cancel(args.task_id)), indent=2))
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except (FactoryError, ValueError, OSError) as exc:
        print(scrub(str(exc)), file=sys.stderr)
        raise SystemExit(2) from None
    finally:
        if controller:
            controller.store.close()


if __name__ == '__main__':
    main()
