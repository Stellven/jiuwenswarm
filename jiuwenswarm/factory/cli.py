"""Native factory CLI. Service imports are lazy; help and status stay offline."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .migration import check_legacy_config_or_exit


def format_status(value):
    decision = value['latest_decision'] or {}
    lines = [f"Task: {value['task_id']}", f"Objective: {value['objective']}",
             f"Outcome: {value['outcome'] or 'in progress'}",
             f"Decision rev: {decision.get('rev', 0)}; action: {decision.get('action', {})}",
             f"Reason for change: {decision.get('reason_for_change', '')}"]
    for key in ('active_jobs', 'artifacts', 'evaluations', 'readiness', 'budget_used',
                'pending_attempts', 'pending_questions'):
        lines.append(f"{key}: {json.dumps(value[key], ensure_ascii=False)}")
    return '\n'.join(lines)


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
        if name == 'show':
            command.add_argument('id', nargs='?', help='evidence record ID; omit to show all records')
    sub.add_parser('login', help='sign in under the factory data directory')
    sub.add_parser('auth-status', help='show factory account status without tokens')
    args = parser.parse_args(argv)
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
            print(format_status(scrub(result)))
        elif args.command == 'status':
            result = scrub(controller.status(args.task_id))
            print(json.dumps(result, indent=2) if args.json else format_status(result))
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
