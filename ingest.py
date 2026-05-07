"""CLI for populating the database.

Examples:
    python ingest.py seed              # write synthetic Tacoma listings
    python ingest.py html data/raw     # parse all *.html in data/raw/
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cartracker import db, parse, seed


def cmd_seed(args: argparse.Namespace) -> int:
    records = seed.generate(n=args.n)
    with db.connect() as conn:
        n = db.upsert_vehicles(conn, records)
    print(f"seeded {n} synthetic Tacoma listings")
    return 0


def cmd_html(args: argparse.Namespace) -> int:
    dir_path = Path(args.dir)
    if not dir_path.is_dir():
        print(f"not a directory: {dir_path}", file=sys.stderr)
        return 1
    records = parse.parse_directory(dir_path)
    if not records:
        print(f"no listings found in {dir_path}", file=sys.stderr)
        return 1
    with db.connect() as conn:
        n = db.upsert_vehicles(conn, records)
    print(f"ingested {n} listings from {dir_path}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Populate the cartracker database.")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_seed = sub.add_parser("seed", help="Insert synthetic Tacoma listings.")
    p_seed.add_argument("--n", type=int, default=200)
    p_seed.set_defaults(func=cmd_seed)

    p_html = sub.add_parser("html", help="Parse saved listing pages (HTML / HAR / JSON).")
    p_html.add_argument("dir", help="Directory containing saved .html files")
    p_html.set_defaults(func=cmd_html)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
