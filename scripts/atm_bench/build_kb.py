#!/usr/bin/env python
"""build_kb — the external KB built from ATM-Bench's released files (r51b 2a).

Layout under ``--out DIR``: ``DIR/kb`` (the second ``LIFE_AGENT_KB``), ``DIR/emails`` as a
SIBLING of the KB (the ingest guard refuses a root inside the KB or the content store),
``DIR/pkm.yaml`` pointing ``root_dir`` at ``--store``. Every email record becomes one
``.eml`` carrying only what the record can derive — ``Date`` (when the timestamp parses),
``Subject`` (the short summary), ``Message-ID`` ``<id@atm-bench>`` — and the detail as a
``text/plain`` body; no From/To/Cc. QA pairs whose evidence is ALL emails become the KB's
``eval/questions.yaml`` with ``fuzzy`` typed from the ANSWER (the one gradeability predicate,
``gold_verdicts.gradeable``), ``answer_variants`` empty on purpose (normalisation lives in the
matcher, not the data) and notes carrying ids, never values. The gauge is copied from the
owner's KB — exactly ``utility/model.yaml`` and ``utility/elicitations.jsonl``, both sha256s
recorded in ``external-corpus.json`` so X9 can name them. The pkm steps are the
``bootstrap-sample.sh`` recipe, run as subprocesses with ``LIFE_AGENT_KB``/``PKM_CONFIG`` set
and ``LIFE_AGENT_MEMBRANE_COMMAND`` removed (env is bound at import time across the stack).
Stdout carries counts only. Idempotent: a second run writes nothing.

  uv run --project . python scripts/atm_bench/build_kb.py --emails EMAILS.json --qa QA.json \\
      --out DIR --store STORE --gauge-from REAL_KB [--hf-revision SHA] [--no-pkm]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path
from typing import Any

import yaml

SCRIPTS = Path(__file__).resolve().parent.parent
REPO = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from gold_verdicts import MANIFEST, gradeable  # noqa: E402

from atm_bench.vendored import UPSTREAM_SHA, is_abstention  # noqa: E402
from pkm.producers.email_producer import installed_email_version  # noqa: E402

CORPUS = "atm-bench"
LICENSE = "CC-BY-NC-4.0 (data) — read on-machine only, never redistributed from the repo"
GAUGE_FILES: tuple[str, ...] = ("utility/model.yaml", "utility/elicitations.jsonl")
STABLE_COUNTS: tuple[str, ...] = ("emails", "unparseable_timestamps", "qa", "questions",
                                  "gradeable", "abstention")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_if_changed(path: Path, data: bytes) -> bool:
    """Write only when the bytes differ — the builder's idempotence, file by file."""
    if path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def _yaml(doc: Mapping[str, Any]) -> bytes:
    return yaml.safe_dump(dict(doc), allow_unicode=True, sort_keys=False,
                          default_flow_style=False).encode("utf-8")


# --- the .eml -------------------------------------------------------------------------------


def _parse_ts(ts: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return None


def eml_bytes(rec: Mapping[str, Any]) -> bytes:
    """One RFC822 message from one email record: only the three derivable headers, the
    detail as body. The deployed email producer renders Date/Subject/Message-ID from its
    fixed header order and never sees a From/To/Cc here because none is written."""
    msg = EmailMessage()
    dt = _parse_ts(rec.get("timestamp"))
    if dt is not None:
        msg["Date"] = format_datetime(dt)
    subject = str(rec.get("short_summary") or "").strip()
    if subject:
        msg["Subject"] = subject
    msg["Message-ID"] = f"<{rec['id']}@{CORPUS}>"
    msg.set_content(str(rec.get("detail") or ""))
    return msg.as_bytes()


# --- the questions --------------------------------------------------------------------------


def _is_email_id(x: object) -> bool:
    return str(x).lower().startswith("email")


def question_for(qa: Mapping[str, Any]) -> dict[str, Any] | None:
    """The eval row for one QA pair, or None unless EVERY evidence id is an email.
    ``fuzzy`` is typed from the ANSWER; notes carry ids, never values."""
    evidence = [str(x) for x in (qa.get("evidence_ids") or [])]
    if not evidence or not all(_is_email_id(x) for x in evidence):
        return None
    answer = str(qa["answer"])
    return {
        "id": str(qa["id"]), "question": str(qa["question"]), "answer": answer,
        "subject": "n/a", "fuzzy": not gradeable(answer), "answer_variants": [],
        "search_queries": [], "notes": "evidence: " + " ".join(evidence),
    }


def write_questions(path: Path, qas: Iterable[Mapping[str, Any]]) -> int:
    rows = [q for q in (question_for(qa) for qa in qas) if q is not None]
    _write_if_changed(path, _yaml({"questions": rows}))
    return len(rows)


# --- registry, pkm config, owner, gauge, manifest -------------------------------------------


def registry_doc(emails_dir: Path) -> dict[str, Any]:
    return {"version": 1, "roots": [{
        "id": CORPUS, "kind": "filetree", "path": str(emails_dir), "include": ["**/*.eml"],
        "tags": [CORPUS], "enabled": True}]}


def pkm_config_doc(store: Path) -> dict[str, Any]:
    """Binds the INSTALLED email-producer version (`M-7`), never the literal."""
    return {"root_dir": str(store),
            "extractors": {"email": {"version": installed_email_version(), "config": {}}}}


def owner_profile() -> str:
    return ("# Owner profile (external corpus)\n\n"
            "I am the recipient of the emails in this corpus.\n")


def copy_gauge(real_kb: Path, kb: Path) -> dict[str, str]:
    """Exactly the two gauge files, byte-copied; their sha256s returned for the manifest."""
    shas: dict[str, str] = {}
    for rel in GAUGE_FILES:
        src = real_kb / rel
        if not src.is_file():
            raise FileNotFoundError(f"gauge source missing: {src}")
        data = src.read_bytes()
        _write_if_changed(kb / rel, data)
        shas[rel] = _sha(data)
    return shas


def manifest_doc(counts: Mapping[str, int], *, gauge: Mapping[str, str],
                 hf_revision: str | None, built_at: str) -> dict[str, Any]:
    return {"corpus": CORPUS, "license": LICENSE, "built_at": built_at,
            "hf_revision": hf_revision, "evaluator_sha": UPSTREAM_SHA,
            "counts": {k: int(counts[k]) for k in STABLE_COUNTS}, "gauge": dict(gauge)}


def _write_manifest(kb: Path, counts: Mapping[str, int], *, gauge: Mapping[str, str],
                    hf_revision: str | None) -> None:
    path = kb / MANIFEST
    now = datetime.now(UTC).isoformat(timespec="seconds")
    new = manifest_doc(counts, gauge=gauge, hf_revision=hf_revision, built_at=now)
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        same = {k: v for k, v in old.items() if k != "built_at"} == {
            k: v for k, v in new.items() if k != "built_at"}
        if same:
            return
    _write_if_changed(path, (json.dumps(new, indent=1, sort_keys=True) + "\n").encode("utf-8"))


# --- the pkm steps --------------------------------------------------------------------------


def pkm_steps(repo: Path, pkm_yaml: Path, kb: Path) -> list[list[str]]:
    """`scripts/bootstrap-sample.sh`'s recipe, as argv lists."""
    uv = ["uv", "run", "--project", str(repo)]
    pkm = [*uv, "pkm", "--config", str(pkm_yaml)]
    return [
        [*pkm, "migrate"],
        [*uv, "python", str(repo / "scripts" / "ingest_sources.py"),
         "--registry", str(kb / "config" / "data-sources.yaml")],
        [*pkm, "extract", "--producer", "email"],
        [*pkm, "chunk", "--backfill"],
        [*pkm, "rebuild-index"],
    ]


def run_pkm_steps(repo: Path, pkm_yaml: Path, kb: Path, *,
                  log: Callable[[str], None] = print) -> None:
    """Subprocesses, never imports: ``ingest_sources.DEFAULT_PKM_CONFIG`` and the whole stack
    read env at import time, so the env is set BEFORE each interpreter starts; the membrane
    command is removed so nothing here can enable a shadow."""
    env = {k: v for k, v in os.environ.items() if k != "LIFE_AGENT_MEMBRANE_COMMAND"}
    env["LIFE_AGENT_KB"] = str(kb)
    env["PKM_CONFIG"] = str(pkm_yaml)
    for cmd in pkm_steps(repo, pkm_yaml, kb):
        log("+ " + " ".join(cmd[4:]))
        res = subprocess.run(cmd, env=env, check=False)
        if res.returncode != 0:
            raise RuntimeError(f"pkm step failed (rc {res.returncode}): {' '.join(cmd[4:])}")


# --- the build ------------------------------------------------------------------------------


def build(emails: Sequence[Mapping[str, Any]], qas: Sequence[Mapping[str, Any]], *,
          out: Path, store: Path, gauge_from: Path, hf_revision: str | None) -> dict[str, int]:
    kb, emails_dir = out / "kb", out / "emails"
    written = unchanged = bad_ts = 0
    for rec in emails:
        if _parse_ts(rec.get("timestamp")) is None:
            bad_ts += 1
        if _write_if_changed(emails_dir / f"{rec['id']}.eml", eml_bytes(rec)):
            written += 1
        else:
            unchanged += 1
    n_questions = write_questions(kb / "eval" / "questions.yaml", qas)
    rows = [q for q in (question_for(qa) for qa in qas) if q is not None]
    _write_if_changed(kb / "config" / "data-sources.yaml", _yaml(registry_doc(emails_dir)))
    _write_if_changed(kb / "owner.md", owner_profile().encode("utf-8"))
    _write_if_changed(kb / "pii-patterns.txt",
                      (REPO / "config" / "pii-patterns.txt.example").read_bytes())
    _write_if_changed(out / "pkm.yaml", _yaml(pkm_config_doc(store)))
    gauge = copy_gauge(gauge_from, kb)
    counts = {
        "emails": len(emails), "emails_written": written, "emails_unchanged": unchanged,
        "unparseable_timestamps": bad_ts, "qa": len(qas), "questions": n_questions,
        "gradeable": sum(1 for q in rows if not q["fuzzy"]),
        "abstention": sum(1 for q in rows if is_abstention(q["answer"])),
        "gauge_files": len(gauge),
    }
    _write_manifest(kb, counts, gauge=gauge, hf_revision=hf_revision)
    return counts


def _load_list(path: Path) -> list[dict[str, Any]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(doc, list):
        return doc
    return next(v for v in doc.values() if isinstance(v, list))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--emails", type=Path, required=True)
    parser.add_argument("--qa", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--gauge-from", type=Path, required=True, metavar="REAL_KB")
    parser.add_argument("--hf-revision", default=None)
    parser.add_argument("--no-pkm", action="store_true", help="write the layout only")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out, store = Path(args.out).expanduser(), Path(args.store).expanduser()
    try:
        counts = build(_load_list(Path(args.emails)), _load_list(Path(args.qa)), out=out,
                       store=store, gauge_from=Path(args.gauge_from).expanduser(),
                       hf_revision=args.hf_revision)
    except FileNotFoundError as e:
        print(f"REFUSED: {e}")
        return 2
    print(f"{CORPUS} kb: " + " ".join(f"{k}={v}" for k, v in counts.items()) + f" -> {out}")
    if not args.no_pkm:
        run_pkm_steps(REPO, out / "pkm.yaml", out / "kb")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
