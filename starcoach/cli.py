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


def cmd_search(args: argparse.Namespace) -> int:
    from starcoach.db import connect
    from starcoach.search import search_products

    settings = get_settings()
    conn = connect(Path(args.db) if args.db else settings.db_path, readonly=True)
    result = search_products(conn, args.query, limit=args.limit)
    print(f"words={result['words']} mode={result['mode']} total={result.get('total', 0)}")
    for item in result["items"]:
        price = f"{item['min_price']:,}" if item["min_price"] else "-"
        print(f"{item['score']:7.2f}  shops={item['n_shops']:<3} min={price:>14}  {item['title']}  [{item['category']}]")
    return 0


def cmd_pack_db(args: argparse.Namespace) -> int:
    import gzip
    import hashlib
    import shutil

    settings = get_settings()
    src = Path(args.db) if args.db else settings.db_path
    out = Path(str(src) + ".gz")
    with open(src, "rb") as f_in, gzip.open(out, "wb", compresslevel=6) as f_out:
        shutil.copyfileobj(f_in, f_out, length=1 << 20)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    info = {"file": str(out), "mb": round(out.stat().st_size / 2**20, 1), "sha256": digest}
    print(json.dumps(info, indent=2))
    log_event(settings.log_dir, "runs", "pack_db", **info)
    return 0


def cmd_eval_intents(args: argparse.Namespace) -> int:
    from starcoach.db import connect
    from starcoach.evaluate import EVAL_NOW, baseline_parse, run_eval
    from starcoach.intent import Gazetteer, parse_request

    settings = get_settings()
    conn = connect(Path(args.db) if args.db else settings.db_path, readonly=True)
    g = Gazetteer.from_db(conn)
    parsers = {"baseline": baseline_parse, "rules": lambda t: parse_request(t, g, now=EVAL_NOW)}
    if args.with_llm:
        from starcoach.llm import refine_request

        parsers["rules+llm"] = lambda t: refine_request(t, parse_request(t, g, now=EVAL_NOW), settings, g, now=EVAL_NOW)
    report = {}
    for name, parse in parsers.items():
        report[name] = run_eval(Path(args.cases), parse, args.split)
        r = report[name]
        print(f"{name:<10} split={r['split']} cases={r['cases']} exact={r['exact_match']} slots={r['slot_accuracy']} {r['per_slot']}")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log_event(settings.log_dir, "runs", "eval_intents", split=args.split,
              **{k: {"exact": v["exact_match"], "slots": v["slot_accuracy"]} for k, v in report.items()})
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    from starcoach.smoke import run

    settings = get_settings()
    result = run(args.url, timeout=args.timeout)
    for c in result["checks"]:
        print(f"{'OK ' if c['ok'] else 'FAIL'} {c['name']:<8} status={c['status']} {c['ms']:>5} ms  {c['detail']}")
    print("SMOKE PASSED" if result["ok"] else "SMOKE FAILED")
    log_event(settings.log_dir, "smoke", "smoke", **result)
    return 0 if result["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="starcoach", description="Persian in-store shopping assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("build-db", help="build the SQLite DB from the Torob CSVs")
    p.add_argument("--data", default=None, help="folder with shops.csv, products.csv, offers.csv")
    p.add_argument("--db", default=None, help="output DB path")
    p.set_defaults(func=cmd_build_db)

    p = sub.add_parser("search", help="search products by a Persian query")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--db", default=None)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("stats", help="print counts from the built DB")
    p.add_argument("--db", default=None)
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("pack-db", help="gzip the DB and print its SHA256, for upload to a server")
    p.add_argument("--db", default=None)
    p.set_defaults(func=cmd_pack_db)

    p = sub.add_parser("eval-intents", help="score request parsing on labeled Persian requests")
    p.add_argument("--cases", default="tests/data/intents.jsonl")
    p.add_argument("--split", default="dev", choices=["dev", "test", "hard", "all"])
    p.add_argument("--with-llm", action="store_true", help="also score rules + LLM (needs LLM_* in .env)")
    p.add_argument("--out", default=None, help="write the full report as JSON")
    p.add_argument("--db", default=None)
    p.set_defaults(func=cmd_eval_intents)

    p = sub.add_parser("smoke", help="smoke test a running instance over HTTP")
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--timeout", type=float, default=15.0)
    p.set_defaults(func=cmd_smoke)

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
