"""The disclosure record — what left the machine, to which model (CLAUDE.md rule 3).

One append-only JSONL log at :data:`life_agent.core.config.DISCLOSURES_LOG`
(``$LIFE_AGENT_KB/calibration/disclosures.jsonl``), written through the shared mechanics
(:mod:`life_agent.core.jsonl_log`): one row per model call that carried corpus text, on
one of four paths — per-chunk ``extract``, the ``joint`` re-read, ``rerank``, and the
``deliberate`` rung. A call that fails or is refused writes its row too, with
``outcome: "failed"``; a cache hit calls no model, so nothing crossed and no row is
written. A row holds artifact cache keys and counts, never document text and never the
question (its ``question_id`` is the decision log's hash). A field whose value a call
site does not have is ``None``, never a guess: ``run_id`` is whatever the request
carried, and the deliberate rung's ``n_chunks``/``n_chars`` are taken from the tool log
it leaves behind.

The write is the call site's own, through a :data:`Sink` it is handed; a call site given
no sink records nothing, which is how eval harnesses and unit tests stay off the KB.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from life_agent.core import decisions as DEC
from life_agent.core import jsonl_log
from life_agent.core import outcomes as O

FORMAT_VERSION = 1

#: The model calls that carry corpus text, as the ``path`` field names them.
PATHS: tuple[str, ...] = ("extract", "joint", "rerank", "deliberate")
OUTCOMES: tuple[str, ...] = ("ok", "failed")


@dataclass(frozen=True)
class Disclosure:
    """One model call's disclosure. ``n_chars`` counts corpus characters as sent (the
    question and the instructions are not corpus text)."""

    tx_time: str
    run_id: str | None
    question_id: str
    path: str
    model: str | None
    artifact_cache_keys: tuple[str, ...]
    n_chunks: int | None
    n_chars: int | None
    outcome: str
    format_version: int = FORMAT_VERSION

    def __post_init__(self) -> None:
        if self.path not in PATHS:
            raise ValueError(f"unknown disclosure path {self.path!r} (declared: {PATHS})")
        if self.outcome not in OUTCOMES:
            raise ValueError(
                f"unknown disclosure outcome {self.outcome!r} (declared: {OUTCOMES})")


#: What a call site is handed: it builds one row per model call and passes it here.
Sink = Callable[[Disclosure], None]


def make(path: str, *, question: str, model: str | None, artifact_cache_keys: Iterable[str],
         n_chunks: int | None, n_chars: int | None, outcome: str,
         run_id: str | None = None) -> Disclosure:
    """One row, stamped now. Keys are de-duplicated in first-seen order."""
    return Disclosure(
        tx_time=O.now_iso(), run_id=run_id, question_id=DEC.question_id(question),
        path=path, model=model,
        artifact_cache_keys=tuple(dict.fromkeys(str(k) for k in artifact_cache_keys)),
        n_chunks=n_chunks, n_chars=n_chars, outcome=outcome)


def _to_line(d: Disclosure) -> str:
    payload = asdict(d)
    payload["artifact_cache_keys"] = list(d.artifact_cache_keys)
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _from_line(line: str) -> Disclosure:
    obj = json.loads(line)
    obj["artifact_cache_keys"] = tuple(obj.get("artifact_cache_keys", ()))
    return Disclosure(**obj)


def record(path: Path, d: Disclosure) -> None:
    """Append one row, durably."""
    jsonl_log.append_line(path, _to_line(d))


def read(path: Path) -> list[Disclosure]:
    """Every row in file order; a missing file means nothing has been disclosed yet."""
    return [_from_line(line) for line in jsonl_log.read_lines(path)]


def to_log(path: Path | None, run_id: str | None = None) -> Sink | None:
    """The sink that appends to ``path``; ``None`` (no log) gives no sink. ``run_id``
    fills a row that does not carry one."""
    if path is None:
        return None

    def sink(d: Disclosure) -> None:
        record(path, d if d.run_id is not None else replace(d, run_id=run_id))
    return sink
