"""Command line: one subcommand per capability."""

import argparse
import json
import sys
from pathlib import Path

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


def cmd_build_db(args: argparse.Namespace) -> int:
    from starcoach.build import build

    settings = get_settings()
    data_dir = Path(args.data) if args.data else settings.data_dir
    db_path = Path(args.db) if args.db else settings.db_path
    counts = build(data_dir, db_path, settings.log_dir)
    print(json.dumps(counts, ensure_ascii=False, indent=2))
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    from starcoach.build import stats

    settings = get_settings()
    db_path = Path(args.db) if args.db else settings.db_path
    print(json.dumps(stats(db_path), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="starcoach", description="Persian in-store shopping assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("build-db", help="build the SQLite DB from the Torob CSVs")
    p.add_argument("--data", default=None, help="folder with shops.csv, products.csv, offers.csv")
    p.add_argument("--db", default=None, help="output DB path")
    p.set_defaults(func=cmd_build_db)

    p = sub.add_parser("stats", help="print counts from the built DB")
    p.add_argument("--db", default=None)
    p.set_defaults(func=cmd_stats)

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
