"""Command line: one subcommand per capability."""

import argparse
import sys

from starcoach.config import get_settings
from starcoach.logs import log_event


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from starcoach.app import create_app

    settings = get_settings()
    host = args.host or settings.host
    port = args.port or settings.port
    log_event(settings.log_dir, "runs", "serve", host=host, port=port)
    uvicorn.run(create_app(settings), host=host, port=port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="starcoach", description="Persian in-store shopping assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("serve", help="run the web app and API")
    p.add_argument("--host", default=None)
    p.add_argument("--port", type=int, default=None)
    p.set_defaults(func=cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
