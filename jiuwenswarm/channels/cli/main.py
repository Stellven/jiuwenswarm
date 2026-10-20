# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.

"""Root ``jiuwenswarm`` CLI entry point."""

from __future__ import annotations

import logging
import os
import sys


logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "research":
        from jiuwenswarm.channels.cli.research import main as research_main

        sys.exit(research_main(sys.argv[2:]))
    if os.environ.get('JIUWENSWARM_M1_PROFILE') == '1':
        # The protected profile has one native TUI client. Never fall through
        # to the legacy chat transport when its frozen launcher is missing.
        try:
            from jiuwenswarm_tui.app import main as tui_main
        except ImportError:
            logging.error('The installed native research TUI is unavailable. Inspect the frozen installation.')
            raise SystemExit(3) from None
        if len(sys.argv) > 1 and sys.argv[1] == 'chat':
            sys.argv = [sys.argv[0], *sys.argv[2:]]
        try:
            tui_main()
        except KeyboardInterrupt:
            raise SystemExit(130) from None
        return
    # 启动阶段（模块导入、YAML 配置加载、日志 handler 创建、dotenv 解析、
    # 参数解析）被 Ctrl+C 中断时，避免抛出裸 KeyboardInterrupt 堆栈——与
    # run_chat 内部的优雅退出语义（exit 130）保持一致。
    try:
        from jiuwenswarm.dotenv_early import parse_dotenv_early
        parse_dotenv_early("jiuwenswarm")

        from jiuwenswarm.channels.cli.chat import build_parser as build_chat_parser
        from jiuwenswarm.channels.cli.chat import run_chat
    except KeyboardInterrupt:
        logging.warning("Interrupted during startup. Exiting.")
        sys.exit(130)

    if os.environ.get("JIUWENSWARM_SKIP_DOTENV", "").strip() != "1":
        try:
            from dotenv import load_dotenv
            from jiuwenswarm.common.utils import get_env_file

            load_dotenv(dotenv_path=get_env_file(), override=False)
        except ImportError:
            pass
        except KeyboardInterrupt:
            logging.warning("Interrupted during startup. Exiting.")
            sys.exit(130)

    argv = sys.argv[1:]
    if argv and argv[0] == "chat":
        argv = argv[1:]

    try:
        chat_parser = build_chat_parser()
        chat_args = chat_parser.parse_args(argv)
    except KeyboardInterrupt:
        logging.warning("Interrupted during startup. Exiting.")
        sys.exit(130)
    sys.exit(run_chat(chat_args))


if __name__ == "__main__":
    main()
