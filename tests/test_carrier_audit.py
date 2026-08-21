"""Carrier audit (scripts/carrier_audit.py) — hermetic.

The instrument answers one question: does *which document* represents byte-identical text
decide the answer (design §6.11)? Its criteria are frozen in the module docstring, so what
these tests pin is that the instrument measures what the criteria say — in particular the
two things it got wrong before the battery ran, each of which biased a verdict:

* divergence must be read off the FACTOR TRIPLE the posterior consumes, never off the
  carrier's provenance path (two email copies at different paths share an authority class);
* the partition must be compared as the text -> document ASSIGNMENT, never as a key set.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import carrier_audit as CA

import life_agent.core.lookup as LK

_TODAY = date(2026, 8, 21)

# Synthetic corpus paths — only their SHAPE matters (the authority classifier reads the
# extension/segment, never the value).
_MAIL = "/corpus/mail/one.eml"    # PII-OK: synthetic corpus path
_MAIL2 = "/corpus/mail/two.eml"   # PII-OK: synthetic corpus path
_DOC = "/corpus/docs/one.pdf"     # PII-OK: synthetic corpus path


@dataclass
class _Hit:
    """The SearchResult shape the instrument reads (duck-typed, like pkm's own)."""
    chunk_text: str
    score: float
    artifact_cache_key: str
    source_path: str = _MAIL
    source_origin: str | None = None


def _text(*carriers: _Hit) -> CA.Text:
    return CA.Text(chunk_text=carriers[0].chunk_text, carriers=list(carriers))


def _cov(t: CA.Text, **per_key: CA.CarrierCov) -> CA.Text:
    t.covariates = dict(per_key)
    return t


# --- the declared key and the dedup mirror ------------------------------------------------

def test_the_declared_key_is_r2s_key_verbatim() -> None:
    assert CA.declared_key(_Hit("t", 12.3456789012, "b")) == (-12.345678901, "b", "t")


def test_the_dedup_mirrors_retrieve_set_and_keeps_the_losers(monkeypatch) -> None:
    """The claim "same order, same first-wins keep" is checked against `retrieve_set`
    itself on one hit list, not asserted in a comment."""
    import life_agent.core.retrieval as RET
    hits = [_Hit("shared", 9.0, "ddd"), _Hit("shared", 9.0, "aaa"),
            _Hit("solo", 11.0, "ccc"), _Hit("other", 9.0, "bbb")]
    monkeypatch.setattr("pkm.retrieval.search", lambda conn, q, k: list(hits))
    got = CA.texts_from_hits(list(hits), 3)
    want = RET.retrieve_set(None, "q", 3)
    assert [t.chunk_text for t in got] == [h["chunk_text"] for h in want]
    assert [t.chosen for t in got] == [h["artifact_cache_key"] for h in want]
    # and the loser the dedup discarded is still reachable
    assert [c.artifact_cache_key for c in got[1].carriers] == ["aaa", "ddd"]


def test_a_tie_is_named_only_when_the_quantised_scores_are_equal() -> None:
    assert _text(_Hit("t", 9.0, "a"), _Hit("t", 9.0, "b")).tie_decided
    # a real score difference means something substantive separated the carriers
    assert not _text(_Hit("t", 9.0, "a"), _Hit("t", 8.0, "b")).tie_decided
    assert not _text(_Hit("t", 9.0, "a")).tie_decided
    # engine noise below the quantisation IS a tie (R2's whole point)
    assert _text(_Hit("t", 9.0, "a"), _Hit("t", 9.0000000001, "b")).tie_decided


# --- divergence is read off the factors, not the provenance -------------------------------

def test_two_copies_at_different_paths_are_not_divergent() -> None:
    """Bug the smoke test caught: comparing the provenance identity reported divergence
    where the weight is bit-identical, over-stating load-bearing exposure."""
    t = _cov(_text(_Hit("t", 9.0, "a"), _Hit("t", 9.0, "b")),
             a=(_MAIL, None, False, None),
             b=(_MAIL2, None, False, None))
    assert not t.divergent(time_indexed=False, today=_TODAY)


def test_a_different_authority_class_is_divergent() -> None:
    t = _cov(_text(_Hit("t", 9.0, "a"), _Hit("t", 9.0, "b")),
             a=(_MAIL, None, False, None),
             b=(_DOC, None, False, None))
    assert LK.authority_for(_MAIL)[1] != LK.authority_for(_DOC)[1]
    assert t.divergent(time_indexed=False, today=_TODAY)


def test_projected_without_a_date_differs_from_never_projected() -> None:
    """`observe_hits` gives an unprojected hit factor 1.0 and a projected-but-undated hit
    the stated attenuation. Collapsing the two would hide a real divergence."""
    t = _cov(_text(_Hit("t", 9.0, "a"), _Hit("t", 9.0, "b")),
             a=(_MAIL, None, False, None),
             b=(_MAIL2, None, True, None))
    assert t.divergent(time_indexed=True, today=_TODAY)
    # ... and not when the decay is off, because then neither carries a time factor
    assert not t.divergent(time_indexed=False, today=_TODAY)


def test_the_covariate_is_the_product_lookup_folds() -> None:
    t = _cov(_text(_Hit("t", 9.0, "a")),
             a=(_DOC, "other", True, "2020-08-21"))
    a, sf, tf = t.factors("a", time_indexed=True, today=_TODAY)
    assert (a, sf) == (LK.authority_for(_DOC)[1], LK.subject_factor("other"))
    assert tf == LK.time_factor("2020-08-21", time_indexed=True, today=_TODAY)
    assert CA.carrier_covariate(t, "a", time_indexed=True, today=_TODAY) == a * sf * tf


# --- the named rule, and the diagnostic bounds --------------------------------------------

def test_the_named_rule_takes_the_max_covariate_carrier() -> None:
    t = _cov(_text(_Hit("t", 9.0, "a"), _Hit("t", 9.0, "b")),
             a=(_MAIL, None, False, None),
             b=(_DOC, None, False, None))
    assert CA.max_covariate_chooser(False, _TODAY)(t).artifact_cache_key == "b"
    assert CA.worst_covariate_chooser(False, _TODAY)(t).artifact_cache_key == "a"


def test_at_equal_covariate_the_named_rule_falls_back_to_the_declared_key() -> None:
    """Stated in the pre-registration and worth pinning: where the factors tie the fix
    under test cannot move anything — it degenerates to today's behaviour."""
    t = _cov(_text(_Hit("t", 9.0, "a"), _Hit("t", 9.0, "b")),
             a=(_MAIL, None, False, None),
             b=(_MAIL2, None, False, None))
    assert CA.max_covariate_chooser(False, _TODAY)(t).artifact_cache_key == t.chosen


def test_the_grouping_bounds_spread_and_concentrate() -> None:
    """Two texts carried by the same pair of documents: the carrier sets admit both one
    document and two, and nothing in the declared key decides which is right."""
    t1 = _text(_Hit("t1", 9.0, "a"), _Hit("t1", 9.0, "b"))
    t2 = _text(_Hit("t2", 9.0, "a"), _Hit("t2", 9.0, "b"))
    spread = CA.hit_dicts([t1, t2], CA.spread_chooser())
    conc = CA.hit_dicts([t1, t2], CA.concentrate_chooser())
    assert CA.assignment(spread) == ["a", "b"]
    assert CA.assignment(conc) == ["a", "a"]


def test_the_partition_is_the_assignment_not_the_key_set() -> None:
    """Bug the smoke test caught: a swap between two texts keeps the key set and changes
    every group, so a set comparison under-reports it."""
    now = [{"artifact_cache_key": "a"}, {"artifact_cache_key": "b"}]
    swapped = [{"artifact_cache_key": "b"}, {"artifact_cache_key": "a"}]
    assert {h["artifact_cache_key"] for h in now} == {h["artifact_cache_key"] for h in swapped}
    assert CA.partition_changed(now, swapped)
    assert not CA.partition_changed(now, list(now))


# --- the frozen classification and verdict ------------------------------------------------

def _arm(action: str, leader: str) -> CA.Arm:
    return CA.Arm(action=action, leader=leader, n_obs=1, n_docs=1, p_none=0.1, eu=0.5)


def _row(qid: str, now: CA.Arm | None, alt: CA.Arm | None, **kw) -> CA.Row:
    return CA.Row(qid=qid, gold="1,234,567", now=now, alt=alt, **kw)  # PII-OK: synthetic id


def test_the_reach_split_is_the_frozen_one() -> None:
    gold, var = "1,234,567", []  # PII-OK: synthetic id
    assert CA.classify(_row("q", _arm("report", "9,999"), _arm("report", gold)),
                       gold, var) == "repair"
    assert CA.classify(_row("q", _arm("report", gold), _arm("report", "9,999")),
                       gold, var) == "regression"
    assert CA.classify(_row("q", _arm("report", gold), _arm("abstain", gold)),
                       gold, var) == "regression"
    assert CA.classify(_row("q", _arm("abstain", ""), _arm("report", gold)),
                       gold, var) == "reach-gain"
    assert CA.classify(_row("q", _arm("report", "9,999"), _arm("abstain", "")),
                       gold, var) == "repair"
    assert CA.classify(_row("q", _arm("report", gold), _arm("report", gold)),
                       gold, var) == "unchanged"
    assert CA.classify(_row("q", None, None), gold, var) == "unchanged"


def test_criterion_7_is_applied_mechanically() -> None:
    lb = [f"q{i}" for i in range(5)]
    build, price = CA.verdict(lb, ["q0"], [], [])
    assert build.startswith("BUILD") and price.startswith("PRICE")
    # under the bar the entry converts to a standing source, and no run is bought
    build, price = CA.verdict(lb[:4], [], [], [])
    assert build.startswith("NO-GO") and price.startswith("no run bought")
    # regressions outnumbering repairs refuses regardless of exposure
    build, _ = CA.verdict(lb, ["q0"], ["q1", "q2"], [])
    assert build.startswith("REFUSE")


def test_a_straddling_text_is_load_bearing_on_the_probe_surface() -> None:
    """Surface (b)'s sharp case: `_fresh_hits` drops a hit whose carrier is already held,
    so where the carriers straddle the held set the choice decides whether the
    corroboration exists at all — not how much it weighs."""
    t = _text(_Hit("t", 9.0, "held"), _Hit("t", 9.0, "new"))
    assert CA.straddles_held(t, {"held"})
    assert not CA.straddles_held(t, {"other"})
    assert not CA.straddles_held(t, {"held", "new"})
    now = CA.fresh_hits(CA.hit_dicts([t], lambda t: t.carriers[0]), {"held"})
    alt = CA.fresh_hits(CA.hit_dicts([t], lambda t: t.carriers[1]), {"held"})
    assert now == [] and len(alt) == 1
    assert _row("q", None, None, n_probe_straddle=1).load_bearing_probe
    assert not _row("q", None, None, n_divergent=1).load_bearing_probe


def test_a_row_is_load_bearing_on_divergence_or_on_the_partition() -> None:
    assert _row("q", None, None, n_divergent=1).load_bearing
    assert _row("q", None, None, partition_arbitrary=True).load_bearing
    assert _row("q", None, None, n_probe_straddle=1).load_bearing
    # the named rule MOVING the partition is criterion 5's question, not criterion 3's
    assert not _row("q", None, None, partition_changed=True).load_bearing
    assert not _row("q", None, None).load_bearing


def test_the_decay_date_is_the_audited_runs_own() -> None:
    assert CA._run_date("gate-20260821T094545") == date(2026, 8, 21)


def test_the_partition_clause_is_read_off_the_carriers_not_off_one_rule() -> None:
    """Criterion 3 asks whether *the carriers* disagree on the document partition — the
    same rule-independent shape as its two siblings (covariate divergence, `_fresh_hits`
    survival). Measuring one chosen rule's effect instead answers criterion 5's question,
    and where that rule is a no-op it reports an arbitrariness that is plainly there as
    absent."""
    t1 = _text(_Hit("t1", 9.0, "a"), _Hit("t1", 9.0, "b"))
    t2 = _text(_Hit("t2", 9.0, "a"), _Hit("t2", 9.0, "b"))
    spread = CA.hit_dicts([t1, t2], CA.spread_chooser())
    conc = CA.hit_dicts([t1, t2], CA.concentrate_chooser())
    # one document or two — nothing in the declared key decides which
    assert CA.grouping(CA.assignment(spread)) != CA.grouping(CA.assignment(conc))
    assert CA.partition_arbitrary(spread, conc)
    # ... and a single-carrier corpus admits exactly one partition
    solo = [_text(_Hit("t1", 9.0, "a")), _text(_Hit("t2", 9.0, "b"))]
    assert not CA.partition_arbitrary(CA.hit_dicts(solo, CA.spread_chooser()),
                                      CA.hit_dicts(solo, CA.concentrate_chooser()))


def test_relabelling_a_group_is_not_a_different_partition() -> None:
    """`lookup_posterior` conditions once per document; which key names the document is not
    something it reads. Splitting or merging a group is a real change, renaming it is not."""
    assert CA.grouping(["a", "a", "b"]) == CA.grouping(["x", "x", "y"])
    assert CA.grouping(["a", "a", "b"]) != CA.grouping(["a", "b", "b"])


def test_load_bearing_follows_the_carriers_not_the_named_rule() -> None:
    assert _row("q", None, None, partition_arbitrary=True).load_bearing_base
    assert not _row("q", None, None, partition_changed=True).load_bearing_base


def test_which_side_a_straddle_falls_on_is_named() -> None:
    """The count alone does not say whether the arbitrariness can ADD a duplicate or DROP a
    real witness, and those are opposite hazards. `_fresh_hits` drops a hit whose chosen
    carrier is already held, so the side is decided by where the chosen carrier sits."""
    held_first = _text(_Hit("t", 9.0, "aaa"), _Hit("t", 9.0, "zzz"))
    assert CA.straddle_side(held_first, {"aaa"}) == "dropped"
    assert CA.straddle_side(held_first, {"zzz"}) == "kept"
    assert CA.straddle_side(held_first, set()) == "none"
    assert CA.straddle_side(held_first, {"aaa", "zzz"}) == "none"
