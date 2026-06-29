"""Unit tests for the dogfood ask REPL (scripts/ask.py) and the owner profile.

Run in life-agent's own env (which pulls in pkm + duckdb via the path dependency):
    uv run --project . python -m pytest tests/

Covers the dependency-free logic — log-entry / owner-profile formatting, retrieve() dedupe-rank,
query-expansion cleaning, and the lock-error classification. The live retrieval + LLM synthesis
paths are exercised by the manual end-to-end verification in the plan, not in CI.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ask

from life_agent import owner
from life_agent.core import SourceCard

# --- log_entry formatting -------------------------------------------------- #

def _cards():
    return [SourceCard(n=1, text="x", origin="/data/id_scan.pdf"),
            SourceCard(n=2, text="y", origin="/data/2024-01-15.eml")]


def test_log_entry_good_format() -> None:
    entry = ask.log_entry("q?", "the answer [1]", _cards(), {1: 0.89, 2: 0.76},
                          "GOOD", when="14:32")
    assert entry.startswith("## 14:32  GOOD\n")
    assert "Q: q?" in entry
    assert "A: the answer [1]" in entry
    assert "sources: id_scan.pdf(0.89), 2024-01-15.eml(0.76)" in entry
    assert "note:" not in entry        # the verdict is one bit — no free text is ever logged


def test_log_entry_no_sources_omits_sources_line() -> None:
    entry = ask.log_entry("q?", "nothing retrieved", [], {}, "BAD", when="00:00")
    assert "sources:" not in entry


# --- retrieve() dedupe + rank (no DuckDB; pkm.retrieval.search monkeypatched) #

def _hit(text: str, score: float, path: str = "/data/p/doc"):
    return SimpleNamespace(chunk_text=text, score=score, source_path=path,
                           artifact_cache_key="a" * 64)


def test_retrieve_dedupes_keeping_best_score_and_ranks(monkeypatch) -> None:
    import pkm.retrieval as R

    hits = [_hit("A", 0.3), _hit("B", 0.9), _hit("A", 0.7), _hit("C", 0.5)]
    monkeypatch.setattr(R, "search", lambda conn, q, k: hits)

    out = ask.retrieve(conn=None, question="q", k=10)

    # one card per distinct chunk, ranked by best score desc, numbered 1..n
    assert [c.text for c, _ in out] == ["B", "A", "C"]
    assert [s for _, s in out] == [0.9, 0.7, 0.5]   # "A" kept its better 0.7, not 0.3
    assert [c.n for c, _ in out] == [1, 2, 3]


def test_retrieve_truncates_to_k(monkeypatch) -> None:
    import pkm.retrieval as R

    hits = [_hit(t, sc) for t, sc in [("A", 0.9), ("B", 0.8), ("C", 0.7), ("D", 0.6)]]
    monkeypatch.setattr(R, "search", lambda conn, q, k: hits)

    out = ask.retrieve(conn=None, question="q", k=2)
    assert [c.text for c, _ in out] == ["A", "B"]


# --- query expansion: _clean_terms + build_query (pure) -------------------- #

def test_clean_terms_flattens_llm_reply() -> None:
    # newlines, bullets, commas, quotes -> single space-separated term run
    raw = '- income\n- "salary"\n- contractor, freelance\n'
    assert ask._clean_terms(raw) == "income salary contractor freelance"


def test_clean_terms_preserves_hebrew() -> None:
    # Hebrew letters are word chars and must survive (the corpus is bilingual)
    assert ask._clean_terms("salary, משכורת; עוסק מורשה") == "salary משכורת עוסק מורשה"


def test_clean_terms_empty_on_blank() -> None:
    assert ask._clean_terms("   \n  ") == ""


def test_build_query_appends_terms_to_question() -> None:
    # the original words are ALWAYS retained, so expansion can only add recall
    assert ask.build_query("how do i make money", "income salary contractor") == (
        "how do i make money income salary contractor"
    )


def test_build_query_falls_back_to_question_when_no_terms() -> None:
    # expansion failure (empty terms) must leave the raw-question search unchanged
    assert ask.build_query("am i a contractor?", "") == "am i a contractor?"


# --- owner profile: load_profile + append_fact (tmp KB, no live I/O) ------- #

def test_load_profile_empty_when_absent(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(owner, "PROFILE", tmp_path / "owner.md")
    assert owner.load_profile() == ""


def test_append_fact_creates_section_once_and_accumulates(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(owner, "PROFILE", tmp_path / "owner.md")

    owner.append_fact("My name is Ada Lovelace", when="2026-06-03 14:00")
    owner.append_fact("My phone is 555-0100", when="2026-06-03 14:05")

    text = owner.load_profile()
    assert text.count("## Told by the owner") == 1          # heading written exactly once
    assert "- My name is Ada Lovelace  _(told 2026-06-03 14:00)_" in text
    assert "- My phone is 555-0100  _(told 2026-06-03 14:05)_" in text


def test_append_fact_preserves_seeded_prose(monkeypatch, tmp_path) -> None:
    # a hand-seeded profile (no '## Told' section yet) must survive — the section is appended
    profile = tmp_path / "owner.md"
    profile.write_text("# Owner\n\nName: Ada Lovelace.\n", encoding="utf-8")
    monkeypatch.setattr(owner, "PROFILE", profile)

    owner.append_fact("My ID is 123456789", when="2026-06-03 15:00")

    text = owner.load_profile()
    assert "Name: Ada Lovelace." in text                     # seeded prose retained
    assert "## Told by the owner" in text
    assert "- My ID is 123456789  _(told 2026-06-03 15:00)_" in text


# --- lock handling (no real concurrent extraction needed) ------------------ #

def test_is_lock_error_truth_table() -> None:
    assert ask._is_lock_error("Could not set lock on file: Conflicting lock")
    assert ask._is_lock_error("database is being used by another process")
    assert ask._is_lock_error("write-write CONFLICT detected")   # case-insensitive
    assert not ask._is_lock_error("Catalog Error: Table does not exist")
    assert not ask._is_lock_error("Binder Error: syntax error")


def test_main_returns_2_on_locked_corpus(monkeypatch, capsys) -> None:
    def _locked() -> None:
        raise duckdb.Error("Could not set lock on file catalogue.duckdb: Conflicting lock")

    monkeypatch.setattr(ask, "connect", _locked)
    assert ask.main(["what is my id?"]) == 2
    assert "corpus locked" in capsys.readouterr().err


def test_tell_records_fact_without_touching_corpus(monkeypatch, tmp_path) -> None:
    # /tell is corpus-free: connect() must never be called, yet the fact lands in the profile.
    monkeypatch.setattr(owner, "PROFILE", tmp_path / "owner.md")
    monkeypatch.setattr(ask, "connect", lambda: (_ for _ in ()).throw(AssertionError("connected")))

    assert ask.main(["/tell", "My name is Ada Lovelace"]) == 0
    assert "My name is Ada Lovelace" in owner.load_profile()


# --- one-shot argv routes through the SAME line grammar as the REPL --------- #

def test_one_shot_temporal_routing(monkeypatch) -> None:
    # The argv words are joined and parsed by parse_line; the predicate reaches ask_once.
    monkeypatch.setattr(ask, "_pkm_root", lambda: None)   # hermetic: no reconcile I/O
    monkeypatch.setattr(ask, "connect", lambda: None)
    seen: dict = {}

    def fake_ask_once(conn, question, k, **kw):  # type: ignore[no-untyped-def]
        seen.update(question=question, **kw)
        return []

    monkeypatch.setattr(ask, "ask_once", fake_ask_once)
    assert ask.main(["/since", "2026-01-01", "what", "invoices?"]) == 0
    assert seen["question"] == "what invoices?"
    assert str(seen["since"]) == "2026-01-01"
    assert seen["until"] is None and seen["recent"] is False


def test_one_shot_grammar_error_exits_2(monkeypatch, capsys) -> None:
    monkeypatch.setattr(ask, "connect", lambda: (_ for _ in ()).throw(AssertionError("connected")))
    assert ask.main(["/since", "soon", "dentist"]) == 2
    assert "YYYY-MM-DD" in capsys.readouterr().err


def test_one_shot_derive_is_an_error(monkeypatch, capsys) -> None:
    # /derive is stateful (needs the prior answer's targets) — REPL only.
    monkeypatch.setattr(ask, "connect", lambda: (_ for _ in ()).throw(AssertionError("connected")))
    assert ask.main(["/derive"]) == 2
    assert "/derive" in capsys.readouterr().err


def test_removed_flags_stay_removed() -> None:
    # One grammar: the line expresses these concepts; the flags are gone (invariant 5).
    import pytest

    for argv in (["--tell", "x"], ["--since", "2026-01-01", "q"],
                 ["--until", "2026-01-01", "q"], ["--recent", "q"]):
        with pytest.raises(SystemExit):
            ask.main(argv)


# --- reliability: weak-retrieval abstention floor -------------------------- #

def test_retrieval_is_weak_truth_table() -> None:
    assert ask.retrieval_is_weak({}, floor=4.0, min_hits=1)                  # zero retrieval
    assert ask.retrieval_is_weak({1: 3.9, 2: 1.0}, floor=4.0, min_hits=1)    # none clear the floor
    assert not ask.retrieval_is_weak({1: 5.0}, floor=4.0, min_hits=1)        # one strong hit
    assert ask.retrieval_is_weak({1: 5.0}, floor=4.0, min_hits=2)            # need 2, have 1
    assert not ask.retrieval_is_weak({1: 9.0, 2: 8.0}, floor=4.0, min_hits=2)


def test_answer_abstains_on_weak_retrieval_without_calling_llm(monkeypatch) -> None:
    monkeypatch.setattr(owner, "load_profile", lambda: "")  # no profile to answer from
    monkeypatch.setattr(ask, "_pkm_root", lambda: None)     # hermetic: no live cache I/O
    monkeypatch.setattr(
        ask, "_retrieve_set",
        lambda conn, q, k: [{"artifact_cache_key": "a" * 64, "chunk_text": "x",
                             "score": 1.0, "origin": "/data/a.pdf"}],  # weak score
    )
    monkeypatch.setattr(
        ask.C, "anthropic_complete",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("synthesis LLM must not run")),
    )
    text, cards, _ = ask.answer(conn=None, question="q", k=8, expand=False)
    assert text == ask.ABSTENTION
    assert [c.n for c in cards] == [1]  # weak hits still returned for the dogfood log


def test_log_entry_records_unverified_line() -> None:
    e = ask.log_entry("q?", "ID 222222222 [1]", _cards(), {1: 0.5, 2: 0.4},
                      "BAD", when="10:00", unverified="[1] ID 222222222")
    assert "unverified: [1] ID 222222222" in e


# --- the narrative scorer seam (foundations §7 wiring) ---------------------- #

def test_narrative_scored_returns_labeled_render(monkeypatch) -> None:
    from life_agent.core import narrative as N

    fake = SimpleNamespace(rendered="- claim — credence 0.900\n\nfooter",
                           answer_cache_key="nk")
    monkeypatch.setattr(N, "narrative_answer", lambda *a, **k: fake)
    ask.STAGES_LAST = {"synthesize": "sk"}
    out = ask._narrative_scored(Path("/fake/root"), "q?", "raw prose [1]", _cards())
    assert out == fake.rendered
    assert ask.NARRATIVE_LAST is fake
    assert ask.STAGES_LAST["narrative_answer"] == "nk"


def test_narrative_scored_fail_open_is_named(monkeypatch, capsys) -> None:
    from life_agent.core import narrative as N

    def _boom(*a, **k):
        raise RuntimeError("fold exploded")

    monkeypatch.setattr(N, "narrative_answer", _boom)
    ask.NARRATIVE_LAST = None
    out = ask._narrative_scored(Path("/fake/root"), "q?", "raw prose [1]", _cards())
    assert out == "raw prose [1]"  # the proposal still reaches the owner
    assert ask.NARRATIVE_LAST is None
    printed = capsys.readouterr().out
    assert N.GRAMMAR["fallthrough"].format(reason="failed: fold exploded") in printed


def test_narrative_scored_disabled_seam_returns_prose() -> None:
    # the conftest autouse stub (narrative_answer -> None) IS the disabled seam
    out = ask._narrative_scored(Path("/fake/root"), "q?", "raw prose [1]", _cards())
    assert out == "raw prose [1]"


# --- the executor read-path (--executor) ----------------------------------- #

def test_answer_via_executor_renders_logs_and_binds(monkeypatch) -> None:
    # The executor read-path drives the loop (stubbed), renders in the shared credence grammar,
    # builds ask's cards/scores from the view's hits, AND logs the terminal lookup decision so a
    # verdict can fold — EXECUTOR_LAST holds the bridge's id. No live daemon.
    monkeypatch.setattr(ask, "_executor_ready", lambda: True)
    view = {"effector": "report", "asserted": ["P123"], "candidates": ["P123"],
            "credences": [0.9], "p_none": 0.05, "eu": 0.8, "n_obs": 1,
            "hits": [{"artifact_cache_key": "d0", "chunk_text": "Passport P123",
                      "origin": "/data/id.pdf", "score": 9.0}],
            "route": {"construct": "passport number"}}
    monkeypatch.setattr(ask.EX, "decide_via_loop", lambda *a, **k: view)
    posted: dict[str, object] = {}

    def fake_post(url: str, payload: dict) -> dict | None:
        posted[url] = payload
        return {"decision_id": "ab-cafef00d"} if url.endswith("/log_decision") else None

    monkeypatch.setattr(ask, "_http_post", fake_post)
    text, cards, scores = ask.answer_via_executor("my passport?", 20)
    assert "P123" in text and "credence 0.900" in text
    assert len(cards) == 1 and cards[0].origin == "/data/id.pdf"
    assert scores == {1: 9.0}
    log_url = next(u for u in posted if u.endswith("/log_decision"))
    assert posted[log_url]["decision"]["effector"] == "report"
    assert posted[log_url]["retrieval_keys"] == ["d0"]
    assert ask.EXECUTOR_LAST == "ab-cafef00d"


def test_answer_via_executor_skips_log_for_miss(monkeypatch) -> None:
    # A miss (zero grounded observations) is not a lookup decision — nothing to log or verdict.
    monkeypatch.setattr(ask, "_executor_ready", lambda: True)
    view = {"effector": "miss", "asserted": [], "candidates": [], "credences": [],
            "p_none": None, "eu": None, "n_obs": 0,
            "hits": [{"artifact_cache_key": "d0", "chunk_text": "x", "origin": "/d.pdf",
                      "score": 1.0}], "route": {"construct": "passport number"}}
    monkeypatch.setattr(ask.EX, "decide_via_loop", lambda *a, **k: view)
    calls: list[str] = []
    monkeypatch.setattr(ask, "_http_post", lambda url, payload: calls.append(url) or None)
    ask.answer_via_executor("my passport?", 20)
    assert not any(u.endswith("/log_decision") for u in calls)
    assert ask.EXECUTOR_LAST is None


def test_answer_via_executor_abstains_named_when_daemon_down(monkeypatch) -> None:
    # Never a silent fallback to another path's answer: a down stack is the NAMED abstention.
    monkeypatch.setattr(ask, "_executor_ready", lambda: False)
    text, cards, scores = ask.answer_via_executor("my passport?", 20)
    assert text == ask.EXECUTOR_DOWN
    assert cards == [] and scores == {}


def test_record_reaction_binds_verdict_to_executor_decision(monkeypatch, tmp_path) -> None:
    # The in-session g/b verdict must bind to the EXECUTOR's logged decision id — else the fold
    # never joins it. Mirrors the legacy path's bind via LOOKUP_LAST.answer_cache_key.
    monkeypatch.setattr(ask, "EXECUTOR_LAST", "ab-deadbeef")
    monkeypatch.setattr(ask, "LOOKUP_LAST", None)
    monkeypatch.setattr(ask, "NARRATIVE_LAST", None)
    log = tmp_path / "reactions.jsonl"
    monkeypatch.setattr(ask.C, "REACTIONS_LOG", log)
    ask._record_reaction("my passport?", "GOOD")
    rec = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert rec["decision_id"] == "ab-deadbeef"
    assert rec["valence"] == "good"


def test_ask_once_defaults_to_executor_when_ready(monkeypatch) -> None:
    # 2c: the executor is the DEFAULT read-path — a ready daemon answers through it.
    monkeypatch.setattr(ask, "_executor_ready", lambda: True)
    monkeypatch.setattr(ask, "answer_via_executor", lambda q, k: ("EXEC", [], {}))
    monkeypatch.setattr(ask, "answer", lambda *a, **k: ("LEGACY", [], {}))
    monkeypatch.setattr(ask, "capture", lambda *a, **k: None)
    seen: dict[str, str] = {}
    monkeypatch.setattr(ask, "render", lambda text, *a, **k: seen.update(text=text))
    ask.ask_once(None, "my passport?", 20)
    assert seen["text"] == "EXEC"


def test_ask_once_falls_back_to_legacy_when_daemon_down(monkeypatch, capsys) -> None:
    # The flip is robust: a down daemon falls back to the in-process path, NAMED (never silent).
    monkeypatch.setattr(ask, "_executor_ready", lambda: False)
    monkeypatch.setattr(ask, "answer_via_executor", lambda q, k: ("EXEC", [], {}))
    monkeypatch.setattr(ask, "answer", lambda *a, **k: ("LEGACY", [], {}))
    monkeypatch.setattr(ask, "capture", lambda *a, **k: None)
    seen: dict[str, str] = {}
    monkeypatch.setattr(ask, "render", lambda text, *a, **k: seen.update(text=text))
    ask.ask_once(None, "my passport?", 20)
    assert seen["text"] == "LEGACY"
    assert "in-process" in capsys.readouterr().out  # the named fallback notice


def test_ask_once_clears_stale_executor_decision_on_legacy(monkeypatch) -> None:
    # Bug guard: a prior executor answer's id must NOT bind a later legacy answer's verdict.
    # ask_once resets EXECUTOR_LAST before dispatch, so the in-process fallback leaves no stale id
    # for _record_reaction (which checks EXECUTOR_LAST first) to mis-join.
    monkeypatch.setattr(ask, "EXECUTOR_LAST", "ab-stale")
    monkeypatch.setattr(ask, "_executor_ready", lambda: False)  # daemon down → legacy fallback
    monkeypatch.setattr(ask, "answer", lambda *a, **k: ("LEGACY", [], {}))
    monkeypatch.setattr(ask, "capture", lambda *a, **k: None)
    monkeypatch.setattr(ask, "render", lambda *a, **k: None)
    ask.ask_once(None, "q?", 20)
    assert ask.EXECUTOR_LAST is None


def test_ask_once_legacy_flag_forces_in_process(monkeypatch) -> None:
    # --legacy (executor=False) forces the in-process path even when the daemon is up.
    monkeypatch.setattr(ask, "_executor_ready", lambda: True)
    monkeypatch.setattr(ask, "answer_via_executor", lambda q, k: ("EXEC", [], {}))
    monkeypatch.setattr(ask, "answer", lambda *a, **k: ("LEGACY", [], {}))
    monkeypatch.setattr(ask, "capture", lambda *a, **k: None)
    seen: dict[str, str] = {}
    monkeypatch.setattr(ask, "render", lambda text, *a, **k: seen.update(text=text))
    ask.ask_once(None, "my passport?", 20, executor=False)
    assert seen["text"] == "LEGACY"
