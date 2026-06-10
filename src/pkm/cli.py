"""Command-line interface for pkm.

Phase 1 + Phase 2 (Stage A) surface:

    pkm                          # prints help to stderr, exits 1
    pkm --help                   # argparse help, exits 0
    pkm --version                # "pkm <package-version>", exits 0

    pkm migrate [--dry-run]
    pkm rebuild-catalogue [--dry-run]
    pkm ingest
    pkm extract [--retry-failed] [--source HASH] [--producer NAME]

    pkm transform list
    pkm transform run <name>
    pkm transform approve <approval_id>
    pkm transform reject <approval_id> --reason "..."
    pkm transform status [<name>]
    pkm transform show <cache_key>

Design notes:

  - ``argparse`` from the stdlib — no click, no typer, no
    argcomplete, no generated shell completions.
  - Subcommand dispatch is an explicit ``{name: handler}`` dict.
    No ``set_defaults(func=...)``. Grepping for the literal string
    ``"migrate"`` finds the handler; grepping for ``_cmd_migrate``
    finds its dispatch entry.
  - Exit codes:
        0  — the command succeeded (including dry-run reports).
        1  — the command was reached but failed (not implemented,
             or an unhandled exception that's not a config error).
        2  — configuration error (missing config, malformed config,
             argparse argument errors).
  - Logging goes to JSONL files via ``pkm.logging_setup`` (SPEC §10).
    The root logger is configured once per invocation in ``main``
    before the subcommand dispatches. CLI user-facing output (the
    one-line summaries after each command) is separate and goes to
    stdout; stderr carries error messages; the JSONL file carries
    structured events.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version
from pathlib import Path

from pkm.approval import approve, list_pending, reject
from pkm.cache import lineage_file, meta_file, read_artifact
from pkm.catalogue import open_catalogue, run_migrations
from pkm.config import Config, ConfigError, load_config
from pkm.extract import extract
from pkm.ingest import ingest_sources
from pkm.logging_setup import setup_logging
from pkm.rebuild import rebuild_artifacts

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH: Path = Path("~/.local/share/pkm/config.yaml")


def _pkm_version() -> str:
    """Resolve the installed version, tolerating either packaging.

    pkm ships as its own ``pkm`` distribution when installed standalone, or as
    a module inside the ``life-agent`` umbrella distribution in the monorepo.
    Try each in turn; never raise — a bare source checkout has no metadata."""
    for dist in ("pkm", "life-agent"):
        try:
            return _package_version(dist)
        except PackageNotFoundError:
            continue
    return "0+unknown"


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit code; does not call
    ``sys.exit``. The installed ``pkm`` console script and
    ``python -m pkm`` both wrap the return value.

    Order of operations:

      1. Parse argv. ``--help``/``--version`` / usage errors exit
         via ``SystemExit`` before returning from here (argparse
         default).
      2. Return 1 if no subcommand was given (the top-level usage
         message goes to stderr).
      3. Load config. A missing or malformed file surfaces at exit
         code 2 with "config error:" on stderr — before any
         logging or subcommand side effects.
      4. Configure the JSONL logger against ``config.root_dir`` at
         the requested level.
      5. Dispatch to the subcommand handler. Any exception that
         escapes the handler is logged via ``logger.exception`` and
         surfaces at exit code 1 with "error:" on stderr.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.subcommand is None:
        parser.print_help(sys.stderr)
        return 1

    try:
        config = _load_config(args)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    _configure_logging(args, config)

    handler = _SUBCOMMANDS[args.subcommand]
    try:
        return handler(args, config)
    except Exception as e:
        logger.exception("unhandled error in pkm %s", args.subcommand)
        print(f"error: {e}", file=sys.stderr)
        return 1


# --- Argument parser -----------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pkm",
        description=(
            "Personal knowledge management — content-addressed "
            "extraction cache and catalogue."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"pkm {_pkm_version()}",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        metavar="PATH",
        help=(
            f"path to config.yaml (default: {DEFAULT_CONFIG_PATH}); "
            "no environment-variable override per SPEC §14.6"
        ),
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="log level for this invocation (default: INFO)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="shortcut for --log-level DEBUG",
    )

    subparsers = parser.add_subparsers(
        dest="subcommand",
        metavar="<subcommand>",
    )

    p_migrate = subparsers.add_parser(
        "migrate",
        help="Apply pending schema migrations.",
        description=(
            "Apply any pending catalogue migrations in numeric "
            "order. Idempotent: running twice produces zero new "
            "schema_meta rows on the second run. The on-disk hash "
            "of every previously applied migration is verified "
            "before anything new is applied (SPEC §14.8)."
        ),
    )
    p_migrate.add_argument(
        "--dry-run",
        action="store_true",
        help="list pending migrations without applying any",
    )

    p_rebuild = subparsers.add_parser(
        "rebuild-catalogue",
        help="Rebuild the artifacts table from cache meta.json files.",
        description=(
            "Walk <root>/cache/ and rewrite the artifacts table "
            "from the meta.json files (SPEC §5.3). Does not touch "
            "sources or source_paths — re-run `pkm ingest` "
            "afterwards to repopulate those."
        ),
    )
    p_rebuild.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be inserted without writing",
    )

    subparsers.add_parser(
        "ingest",
        help="Register sources from sources.yaml into the catalogue.",
        description=(
            "Read <root>/sources/sources.yaml, hash each referenced "
            "file, and populate the sources and source_paths tables "
            "(SPEC §8). Idempotent: a second run produces zero new "
            "rows. Unreadable entries (missing file, broken symlink, "
            "directory without recursive: true) are WARNING-logged "
            "and skipped (SPEC §13.4); ingest never halts on a bad "
            "manifest entry."
        ),
    )

    p_extract = subparsers.add_parser(
        "extract",
        help="Run extractors over registered sources.",
        description=(
            "Apply the routing policy (SPEC §7.3) to every "
            "registered source and run the producers it selects, "
            "writing artifacts through the cache layer. Idempotent: "
            "a second run produces zero new artifacts (routing "
            "returns [] for fully-extracted sources)."
        ),
    )
    p_extract.add_argument(
        "--retry-failed",
        action="store_true",
        help=(
            "include previously-failed producers back in the "
            "candidate set (SPEC §14.3: failures are explicit to "
            "re-run)"
        ),
    )
    p_extract.add_argument(
        "--source",
        metavar="HASH_PREFIX",
        help=(
            "restrict to sources whose source_id starts with this "
            "lowercase hex prefix (minimum 16 characters)"
        ),
    )
    p_extract.add_argument(
        "--producer",
        choices=["pandoc", "docling", "unstructured", "tesseract", "email"],
        help="restrict to the named producer",
    )

    p_chunk = subparsers.add_parser(
        "chunk",
        help="Chunk extracted text artifacts for FTS indexing.",
        description=(
            "Split text artifacts into overlapping character-boundary "
            "chunks and write them to artifact_chunks. "
            "Use --backfill to chunk all unchunked artifacts from "
            "prior extractions. Idempotent: re-running leaves the "
            "same rows."
        ),
    )
    p_chunk.add_argument(
        "--backfill",
        action="store_true",
        help=(
            "chunk every success artifact that has no artifact_chunks "
            "rows yet; uses cached content (no re-extraction)"
        ),
    )

    p_search = subparsers.add_parser(
        "search",
        help="Search extracted text with FTS keyword search.",
        description=(
            "Run a Unicode-aware BM25 full-text search over chunked "
            "artifacts. Supports Hebrew, Arabic, CJK, and other "
            "non-ASCII scripts (SPEC v0.3.1 §15.2). Use "
            "'pkm rebuild-index' to refresh the FTS index after "
            "adding new chunks."
        ),
    )
    p_search.add_argument("query", help="search query string")
    p_search.add_argument(
        "--k",
        type=int,
        default=20,
        metavar="N",
        help="maximum number of results to return (default: 20)",
    )

    subparsers.add_parser(
        "rebuild-index",
        help="Rebuild the FTS index over artifact_chunks.",
        description=(
            "Rebuild the DuckDB full-text search index. Run this after "
            "'pkm chunk --backfill' to make new chunks searchable. "
            "Index rebuilding is a maintenance operation, separate from "
            "query (SPEC v0.3.1 §15.2)."
        ),
    )

    subparsers.add_parser(
        "serve",
        help="Start the read-only MCP server over stdio (SPEC §17).",
        description=(
            "Start the pkm-memory MCP server. Stdout carries the "
            "JSON-RPC protocol stream; all logging goes to stderr and "
            "the JSONL log file. Register this command in your MCP "
            "client (e.g. Claude Code settings.json mcpServers)."
        ),
    )

    subparsers.add_parser(
        "stale",
        help="Report artifacts a newer derivation has superseded (SPEC §18.10).",
        description=(
            "Read-only staleness report. Lists artifacts that a newer "
            "success has superseded for the same (input_hash, producer), "
            "plus everything derived downstream of them over artifact_lineage. "
            "Reports only — the cache is append-only, so nothing is deleted "
            "(SPEC §18.10)."
        ),
    )

    p_transform = subparsers.add_parser(
        "transform",
        help="Run and manage LLM transforms.",
        description=(
            "Phase 2 transform commands (SPEC v0.2.0 S20-S24). "
            "Run `pkm transform <subcommand> --help` for details."
        ),
    )
    t_sub = p_transform.add_subparsers(
        dest="transform_subcommand",
        metavar="<subcommand>",
    )

    t_sub.add_parser(
        "list",
        help="List available transform declarations.",
    )

    p_t_run = t_sub.add_parser(
        "run",
        help="Execute a transform over eligible sources.",
    )
    p_t_run.add_argument("name", help="transform declaration name")
    p_t_run.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="process at most N eligible sources",
    )
    p_t_run.add_argument(
        "--approval-id",
        metavar="UUID",
        help="skip policy evaluation with a pre-approved ID",
    )

    p_t_approve = t_sub.add_parser(
        "approve",
        help="Approve a pending transform run.",
    )
    p_t_approve.add_argument("approval_id", help="approval UUID")

    p_t_reject = t_sub.add_parser(
        "reject",
        help="Reject a pending transform run.",
    )
    p_t_reject.add_argument("approval_id", help="approval UUID")
    p_t_reject.add_argument(
        "--reason", required=True, help="rejection reason",
    )

    p_t_status = t_sub.add_parser(
        "status",
        help="Show transform status and pending approvals.",
    )
    p_t_status.add_argument(
        "name", nargs="?", help="optional transform name filter",
    )

    p_t_show = t_sub.add_parser(
        "show",
        help="Display a transform artifact with lineage.",
    )
    p_t_show.add_argument("cache_key", help="64-hex cache key")

    return parser


def _configure_logging(args: argparse.Namespace, config: Config) -> None:
    level = (
        logging.DEBUG
        if args.verbose
        else getattr(logging, args.log_level)
    )
    setup_logging(config.root_dir, level)


def _load_config(args: argparse.Namespace) -> Config:
    return load_config(args.config.expanduser())


# --- Subcommand handlers -------------------------------------------------


def _cmd_migrate(args: argparse.Namespace, config: Config) -> int:
    versions = run_migrations(config.root_dir, dry_run=args.dry_run)
    if args.dry_run:
        if versions:
            print(
                f"dry-run: would apply {len(versions)} migration(s): "
                f"{versions}"
            )
        else:
            print("dry-run: no pending migrations")
    else:
        if versions:
            print(f"applied {len(versions)} migration(s): {versions}")
        else:
            print("no pending migrations")
    return 0


def _cmd_rebuild_catalogue(
    args: argparse.Namespace, config: Config
) -> int:
    result = rebuild_artifacts(config.root_dir, dry_run=args.dry_run)
    if args.dry_run:
        print(
            f"dry-run: scanned {result.scanned}, "
            f"would insert {result.scanned - len(result.skipped)}, "
            f"would skip {len(result.skipped)}"
        )
    else:
        print(
            f"rebuilt artifacts: scanned {result.scanned}, "
            f"inserted {result.inserted}, "
            f"skipped {len(result.skipped)}, "
            f"swept {len(result.swept)}"
        )
    return 0


def _cmd_ingest(args: argparse.Namespace, config: Config) -> int:
    result = ingest_sources(config.root_dir)
    print(
        f"ingested: scanned {result.scanned}, "
        f"{result.new_sources} new sources, "
        f"{result.new_paths} new paths, "
        f"{len(result.skipped)} skipped"
    )
    return 0


def _cmd_extract(args: argparse.Namespace, config: Config) -> int:
    result = extract(
        config.root_dir,
        config,
        retry_failed=args.retry_failed,
        source_prefix=args.source,
        producer_name=args.producer,
        progress=lambda line: print(line),
    )
    print(
        f"extract: processed {result.processed}/{result.total_sources} "
        f"sources, {result.succeeded} succeeded, "
        f"{result.failed} failed, {result.cache_hits} cache hits "
        f"({result.elapsed_seconds:.1f}s)"
    )
    if result.interrupted:
        return 1
    return 0


def _cmd_chunk(args: argparse.Namespace, config: Config) -> int:
    from pkm.cache import content_file
    from pkm.chunking import (
        CHUNKABLE_CONTENT_TYPES,
        chunk_text,
        extract_text,
        write_chunks,
    )

    root = config.root_dir
    backfill = getattr(args, "backfill", False)

    chunkable = list(CHUNKABLE_CONTENT_TYPES)
    placeholders = ", ".join("?" * len(chunkable))

    with open_catalogue(root) as conn:
        if backfill:
            rows = conn.execute(
                f"""
                SELECT a.cache_key, a.content_type
                FROM artifacts a
                WHERE a.status = 'success'
                  AND a.content_type IN ({placeholders})
                  AND NOT EXISTS (
                      SELECT 1 FROM artifact_chunks ac
                      WHERE ac.artifact_cache_key = a.cache_key
                  )
                ORDER BY a.produced_at
                """,
                chunkable,
            ).fetchall()
        else:
            print(
                "nothing to do: use --backfill to chunk existing artifacts",
                file=sys.stderr,
            )
            return 0

        total = len(rows)
        chunked = 0
        file_missing = 0
        text_empty = 0

        for cache_key, content_type in rows:
            cf = content_file(root, cache_key)
            content = None if not cf.exists() else cf.read_bytes()
            if content is None:
                logger.warning(
                    "chunk backfill: content file missing for %s — skipped",
                    cache_key[:12],
                    extra={"event": "chunk_backfill_missing", "cache_key": cache_key},
                )
                file_missing += 1
                continue

            text = extract_text(content, content_type)
            if not text:
                text_empty += 1
                continue
            chunks = chunk_text(text)
            write_chunks(conn, cache_key, chunks, source_origin="backfill")
            chunked += 1

            if chunked % 100 == 0:
                print(f"chunk backfill: {chunked}/{total} done …")

    print(
        f"chunk: {chunked} artifacts chunked, "
        f"{file_missing} skipped (file missing), "
        f"{text_empty} skipped (empty text), "
        f"{total - chunked - file_missing - text_empty} already chunked"
    )
    return 0


def _cmd_rebuild_index(args: argparse.Namespace, config: Config) -> int:
    from pkm.retrieval import build_fts_index

    with open_catalogue(config.root_dir) as conn:
        build_fts_index(conn)
    print("FTS index rebuilt.")
    return 0


def _cmd_search(args: argparse.Namespace, config: Config) -> int:
    from pkm.retrieval import search

    with open_catalogue(config.root_dir) as conn:
        results = search(conn, args.query, k=args.k)

    if not results:
        print(f"no results for {args.query!r}")
        return 0

    for i, r in enumerate(results, start=1):
        snippet = r.chunk_text[:200].replace("\n", " ")
        print(f"{i:3d}. [{r.score:.4f}] {r.source_path}")
        print(f"      {snippet}")
        if i < len(results):
            print()
    return 0


def _cmd_serve(args: argparse.Namespace, config: Config) -> int:
    from pkm import mcp_server  # lazy import — mcp dep only needed for serve

    mcp_server.set_root(config.root_dir)
    mcp_server.mcp.run(transport="stdio")
    return 0


def _cmd_stale(args: argparse.Namespace, config: Config) -> int:
    from pkm import staleness

    with open_catalogue(config.root_dir) as conn:
        rows = staleness.stale(conn)

    if not rows:
        print("no stale artifacts")
        return 0

    for s in rows:
        if s.reason == staleness.SUPERSEDED:
            why = f"superseded by {s.via}"
        else:
            why = f"stale-input via {s.via}"
        print(f"{s.cache_key}  {s.producer_name:<20}  {why}")

    n_superseded = sum(1 for s in rows if s.reason == staleness.SUPERSEDED)
    n_downstream = len(rows) - n_superseded
    print(f"\n{len(rows)} stale "
          f"({n_superseded} superseded, {n_downstream} stale-input)")
    return 0


def _cmd_transform(args: argparse.Namespace, config: Config) -> int:
    sub = args.transform_subcommand
    if sub is None:
        print("usage: pkm transform <subcommand>", file=sys.stderr)
        return 1
    handler = _TRANSFORM_SUBCOMMANDS[sub]
    return handler(args, config)


def _cmd_transform_list(
    args: argparse.Namespace, config: Config,
) -> int:
    t_dir = config.root_dir / "transforms"
    if not t_dir.exists():
        print("no transforms directory")
        return 0
    decls = sorted(t_dir.glob("*.yaml"))
    if not decls:
        print("no transform declarations found")
        return 0
    for p in decls:
        print(p.stem)
    return 0


def _cmd_transform_run(
    args: argparse.Namespace, config: Config,
) -> int:
    from pkm.transform_run import run_transform

    result = run_transform(
        config.root_dir,
        config,
        args.name,
        limit=getattr(args, "limit", None),
        approval_id=getattr(args, "approval_id", None),
        progress=lambda line: print(line),
    )

    if result.blocked:
        print(f"blocked: {result.block_reason}", file=sys.stderr)
        return 1

    if result.approval_required:
        print(f"approval required: {result.approval_id}")
        print("run `pkm transform approve <id>` to proceed")
        return 0

    print(
        f"transform: {result.processed}/{result.total_sources} sources, "
        f"{result.succeeded} succeeded, {result.failed} failed, "
        f"{result.cache_hits} cache hits, "
        f"${result.total_cost_usd:.4f} total cost "
        f"({result.elapsed_seconds:.1f}s)"
    )
    return 0 if result.failed == 0 else 1


def _cmd_transform_approve(
    args: argparse.Namespace, config: Config,
) -> int:
    with open_catalogue(config.root_dir) as conn:
        approve(conn, args.approval_id)
    print(f"approved: {args.approval_id}")
    return 0


def _cmd_transform_reject(
    args: argparse.Namespace, config: Config,
) -> int:
    with open_catalogue(config.root_dir) as conn:
        reject(conn, args.approval_id, reason=args.reason)
    print(f"rejected: {args.approval_id} ({args.reason})")
    return 0


def _cmd_transform_status(
    args: argparse.Namespace, config: Config,
) -> int:
    with open_catalogue(config.root_dir) as conn:
        pending = list_pending(conn)
    if not pending:
        print("no pending approvals")
        return 0
    for record in pending:
        name_filter = getattr(args, "name", None)
        if name_filter and record.transform_name != name_filter:
            continue
        print(
            f"  {record.approval_id}  {record.transform_name}  "
            f"sources={record.source_count}  "
            f"cost=${record.cost_estimate_usd or 0:.2f}"
        )
    return 0


def _cmd_transform_show(
    args: argparse.Namespace, config: Config,
) -> int:
    import json

    with open_catalogue(config.root_dir) as conn:
        entry = read_artifact(config.root_dir, conn, args.cache_key)
    if entry is None:
        print(
            f"artifact {args.cache_key} not found", file=sys.stderr,
        )
        return 1
    print(f"cache_key:    {entry.cache_key}")
    print(f"status:       {entry.status}")
    print(f"producer:     {entry.producer_name}@{entry.producer_version}")
    print(f"input_hash:   {entry.input_hash}")
    print(f"produced_at:  {entry.produced_at}")
    if entry.size_bytes is not None:
        print(f"size:         {entry.size_bytes} bytes")

    lf = lineage_file(config.root_dir, args.cache_key)
    if lf.exists():
        lineage = json.loads(lf.read_text(encoding="utf-8"))
        print("lineage:")
        for inp in lineage.get("inputs", []):
            print(f"  {inp['cache_key'][:12]}…  role={inp['role']}")

    mf = meta_file(config.root_dir, args.cache_key)
    if mf.exists():
        meta = json.loads(mf.read_text(encoding="utf-8"))
        pm = meta.get("producer_metadata", {})
        if pm.get("prompt_name"):
            print(f"prompt:       {pm['prompt_name']}")
        if pm.get("model_identity"):
            model = pm["model_identity"].get("model", "?")
            print(f"model:        {model}")

    return 0


_TRANSFORM_SUBCOMMANDS: dict[
    str, Callable[[argparse.Namespace, Config], int]
] = {
    "list": _cmd_transform_list,
    "run": _cmd_transform_run,
    "approve": _cmd_transform_approve,
    "reject": _cmd_transform_reject,
    "status": _cmd_transform_status,
    "show": _cmd_transform_show,
}


# Explicit subcommand table. Grep-friendly: searching for "migrate"
# finds both this entry and the function that handles it.
_SUBCOMMANDS: dict[str, Callable[[argparse.Namespace, Config], int]] = {
    "migrate": _cmd_migrate,
    "rebuild-catalogue": _cmd_rebuild_catalogue,
    "ingest": _cmd_ingest,
    "extract": _cmd_extract,
    "chunk": _cmd_chunk,
    "rebuild-index": _cmd_rebuild_index,
    "search": _cmd_search,
    "serve": _cmd_serve,
    "stale": _cmd_stale,
    "transform": _cmd_transform,
}
