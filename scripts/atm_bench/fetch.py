#!/usr/bin/env python3
"""Fetch ATM-Bench at a PINNED revision, on your machine, for `make sets`.

`scripts/atm_bench/build_kb.py` builds a second KB from the released files; until now the
files had to already be on disk and **where to get them was written down nowhere** — the
one step of the stranger's path that could not be followed. This is that step.

The corpus is **CC-BY-NC-4.0**. It is downloaded to a cache on your machine and never
enters this repo and is not redistributed from it: the default destination is outside the
working tree entirely (an XDG cache dir, so there is nothing for `.gitignore` to catch),
`build_kb.py` writes its KB beside it, and the board publishes counts.

Pinned by revision, so what a board row was scored on is a fact and not "whatever the
dataset said that day". The revision below is the one this project measured; pass
``--revision`` to take another deliberately.

    uv run python scripts/atm_bench/fetch.py            # -> the default cache
    uv run python scripts/atm_bench/fetch.py --dest DIR
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

#: The dataset, and the revision this project's `atm` board row is measured at.
REPO = "Jingbiao/ATM-Bench"
REVISION = "78e826dc07e97466b2f54443831ef9a83ab8b27c"
LICENSE = "CC-BY-NC-4.0 (data); never redistributed from this repo"

#: Only what the KB build reads: the email corpus and the question files.
PATTERNS = ("data/raw_memory/email/*", "data/atm-bench/*.json")

#: Where the files land unless you say otherwise. Under XDG cache, never in the repo.
DEFAULT_DEST = Path(
    os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "life-agent" / "atm-bench"

#: What `make sets` reads back out of the download.
EMAILS_REL = "data/raw_memory/email"
QA_REL = "data/atm-bench/atm-bench.json"


def paths(dest: Path) -> tuple[Path, Path]:
    """(emails dir, qa file) inside a fetched destination."""
    return dest / EMAILS_REL, dest / QA_REL


def already_there(dest: Path) -> bool:
    emails, qa = paths(dest)
    return qa.is_file() and emails.is_dir() and any(emails.iterdir())


def fetch(dest: Path, revision: str = REVISION) -> Path:
    """Download the pinned revision into ``dest`` (idempotent) and record what was taken."""
    try:
        from huggingface_hub import snapshot_download
    except ImportError as e:  # pragma: no cover - environment, not logic
        raise SystemExit(
            "this needs huggingface-hub (a declared dependency): `uv sync`, or fetch the "
            f"files by hand from https://huggingface.co/datasets/{REPO} at revision "
            f"{revision} and pass --emails/--qa to `make sets` yourself."
        ) from e

    dest.mkdir(parents=True, exist_ok=True)
    snapshot_download(repo_id=REPO, repo_type="dataset", revision=revision,
                      allow_patterns=list(PATTERNS), local_dir=str(dest))
    (dest / "REVISION.json").write_text(json.dumps({
        "repo": REPO, "repo_type": "dataset", "revision": revision,
        "allow_patterns": list(PATTERNS), "license": LICENSE,
        "downloaded_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }, indent=1) + "\n", encoding="utf-8")
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    ap.add_argument("--revision", default=REVISION)
    ap.add_argument("--print-paths", action="store_true",
                    help="print '<emails> <qa>' for an already-fetched dest and exit")
    ap.add_argument("--print-dest", action="store_true",
                    help="print the destination and exit (the Makefile asks for it rather "
                         "than spelling a home-relative path of its own)")
    args = ap.parse_args(argv)
    dest = args.dest.expanduser()

    emails, qa = paths(dest)
    if args.print_dest:
        print(dest)
        return 0
    if args.print_paths:
        if not already_there(dest):
            raise SystemExit(f"nothing fetched at {dest} — run this without --print-paths")
        print(f"{emails} {qa}")
        return 0

    if already_there(dest):
        print(f"already at {dest} (revision pinned {args.revision[:12]}) — nothing to do")
    else:
        print(f"fetching {REPO}@{args.revision[:12]} → {dest}\n  {LICENSE}")
        fetch(dest, args.revision)
        print(f"  emails {sum(1 for _ in emails.iterdir())} · qa {qa.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
