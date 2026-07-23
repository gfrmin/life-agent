# src/life_agent/trips/cli.py
"""The `trips` command line — importers + queries over the itinerary ledger.

`import-kayak` lays down the tier-3 history; `ingest <path>` upgrades a single record from a
filed email (the mailbox-scale selection is Plan 2); `list`/`show`/`search` read the
projection. Every write goes through commands.* -> the append-only ledger, exactly like GTD.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from email import message_from_bytes, policy
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from life_agent.trips import commands, kayak, seeder, store
from life_agent.trips.extract import extract


def _fmt(row: dict[str, Any]) -> str:
    when = (row.get("start_iso") or "?")[:16]
    route = f"{row.get('dep_iata') or ''}->{row.get('arr_iata') or ''}".strip("->")
    label = route or row.get("title") or row.get("res_type")
    flags = " [CANCELLED]" if row.get("cancelled") else ""
    return f"{when}  {row.get('res_type'):24} {label}  <{row.get('fidelity')}>{flags}"


def _cmd_import_kayak(args: argparse.Namespace) -> int:
    stats = kayak.import_export(Path(args.path))
    print(f"imported {stats['reservations']} reservations across {stats['trips']} trips "
          f"({stats['skipped']} skipped)")
    return 0


def _cmd_import_ics(args: argparse.Namespace) -> int:
    stats = seeder.import_ics(Path(args.path))
    print(f"imported {stats['reservations']} reservations across {stats['trips']} trips")
    return 0


def _cmd_ingest(args: argparse.Namespace) -> int:
    path = Path(args.path)
    raw = path.read_bytes()
    try:
        msg = message_from_bytes(raw, policy=policy.default)
        ctx = parsedate_to_datetime(msg["Date"]) if msg["Date"] else datetime.now()
    except Exception:
        ctx = datetime.now()
    n = 0
    for jsonld in extract(raw, ctx):
        commands.observe(jsonld, fidelity="email-kitinerary",
                         source_id=f"file:{path.name}",
                         received_at=ctx.isoformat(),
                         source_meta={"path": str(path), "kind": "email"})
        n += 1
    print(f"ingested {n} reservation(s) from {path.name}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    rows = store.timeline(limit=args.limit)
    if not rows:
        print("no reservations")
        return 0
    for r in rows:
        print(_fmt(r))
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    row = store.get_reservation(args.identity)
    if not row:
        print("not found")
        return 1
    print(_fmt(row))
    print(json.dumps(json.loads(row["jsonld"]), indent=2))
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    for r in store.search(args.term):
        print(_fmt(r))
    return 0


def _cmd_supersede(args: argparse.Namespace) -> int:
    commands.supersede(args.old, args.new)
    print(f"{args.old} superseded by {args.new}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="trips", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    commands_spec: list[
        tuple[str, Any, list[tuple[str, dict[str, Any]]]]
    ] = [
        ("import-kayak", _cmd_import_kayak, [("path", {})]),
        ("import-ics", _cmd_import_ics, [("path", {})]),
        ("ingest", _cmd_ingest, [("path", {})]),
        ("show", _cmd_show, [("identity", {})]),
        ("search", _cmd_search, [("term", {})]),
        ("supersede", _cmd_supersede, [("old", {}), ("new", {})]),
    ]
    for name, fn, pos in commands_spec:
        sp = sub.add_parser(name)
        for arg, kw in pos:
            sp.add_argument(arg, **kw)
        sp.set_defaults(func=fn)
    lp = sub.add_parser("list")
    lp.add_argument("--limit", type=int, default=None)
    lp.set_defaults(func=_cmd_list)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 2)
    store.init_db()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
