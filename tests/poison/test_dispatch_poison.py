"""Poison fixtures for the decision-path guards — r23, from the K1 G4 adversary pass.

These require the GUARD to FAIL. Each was verified RED by mutation against the exact
violation the adversary reproduced; the transcript is in
``docs/unification/reports/r23-k1-g4-adversary.md``.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from life_agent.core import pricing as PRC
from life_agent.core.executor import menu_transforms

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src" / "life_agent"


# --- F2: a renamed classifier is still a classifier ----------------------------------
# The C1 guard is a NAME census over a frozen list, so family routing came back as
# `pipeline_verdict` / `POST /pipeline` with every deleted name absent and the census
# green. Its literal claim held; the guarantee a reader takes from it did not. What
# actually matters is not which names are gone but WHICH CALLS MAY CONSUME THE QUESTION on
# the dispatch path — a new predicate on the question text shows up here whatever it is
# called.

_QUESTION_CONSUMERS: dict[str, frozenset[str]] = {
    "terminals.answer": frozenset({
        "_expand_terms", "_narrative_scored", "_rerank_hits", "build_query",
        "intent_verdict", "lookup_answer", "owner_question", "synthesize"}),
    "executor.decide_via_loop": frozenset({"_obj", "post", "run_pass"}),
}


def _question_consumers(path: Path, fname: str) -> set[str]:
    """Every call inside ``fname`` that receives ``question`` as an argument."""
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == fname):
            continue
        out: set[str] = set()
        for n in ast.walk(node):
            if not isinstance(n, ast.Call):
                continue
            takes_q = (
                any(isinstance(a, ast.Name) and a.id == "question" for a in n.args)
                or any(isinstance(k.value, ast.Name) and k.value.id == "question"
                       for k in n.keywords)
                or any(isinstance(v, ast.Name) and v.id == "question"
                       for d in n.args if isinstance(d, ast.Dict) for v in d.values))
            if takes_q:
                f = n.func
                out.add(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "?"))
        return out
    raise AssertionError(f"{fname} not found in {path}")


@pytest.mark.parametrize("key", sorted(_QUESTION_CONSUMERS))
def test_poison_no_new_predicate_consumes_the_question(key: str) -> None:
    """F2. A host predicate on the question text that decides which family runs is
    decision-shaping outside the one decision space (PRINCIPLES §16). The K1 name census
    cannot see it renamed; this can."""
    mod, fname = key.split(".")
    got = _question_consumers(_SRC / "core" / f"{mod}.py", fname)
    extra = got - _QUESTION_CONSUMERS[key]
    assert not extra, (
        f"a new call consumes the question on the dispatch path: {sorted(extra)} — if it "
        f"decides which family runs, that is decision-shaping outside the argmax "
        f"(PRINCIPLES §16); the K1 guard is a name census and this is the same mechanism "
        f"renamed. Declare it here only when it is NOT a routing predicate."
    )


def test_poison_the_bridge_serves_no_second_stage_router() -> None:
    """F2, the wire half. The router came back as `POST /pipeline`. The endpoint set is
    declared, so any NEW route is a decision the register has not seen."""
    from life_agent.bridge import server

    declared = {
        "/route", "/retrieve", "/extract", "/narrative", "/probe/recency",
        "/probe/subject", "/probe/authority", "/probe/corroborate", "/probe/confirm",
        "/probe/deliberate", "/log_decision", "/log_reaction", "/log_gather",
        "/decide-support", "/gate-support"}
    extra = set(server._POST) - declared
    assert not extra, (
        f"the bridge serves undeclared endpoint(s) {sorted(extra)} — a second-stage "
        f"router on the wire under any name is family routing (membrane-shadow §11 i-13)"
    )


# --- F1: the offer set is (probe, name, kind, trigger, rho AND cost) ------------------
# The pin compared probe and name only, so every row's cost could be set to 0.0 —
# including the $0.38 opus deliberate edge run 17 measured as the most expensive act on
# the menu — with the gate green. That is the largest argmax move short of adding a row,
# and C4 declared the pin to be the evidence that K1 owed no priced run.

FROZEN_MENU: tuple[tuple[str, str, str, str, float | None], ...] = (
    ("recency", "recency", "guard", "era_split", None),
    ("corroborate_opus", "corroborate_owner", "guard", "owner_report", None),
    ("corroborate_haiku", "corroborate_haiku", "voi", "below_bar", 0.004),
    ("corroborate_sonnet", "corroborate_sonnet", "voi", "below_bar", 0.012),
    ("corroborate_opus", "corroborate_opus", "voi", "below_bar", 0.020),
    ("deliberate", "deliberate", "voi", "below_bar", 0.38),
)


def test_poison_the_priced_offer_set_is_frozen_whole() -> None:
    """F1. A price change moves the argmax exactly as an added row does."""
    got = tuple((r["probe"], r["name"], r["kind"], r["trigger"], r.get("cost"))
                for r in menu_transforms(None))
    assert got == FROZEN_MENU, (
        "the transform menu re-priced or re-shaped a row — K1's offer set is frozen on "
        "(probe, name, kind, trigger, cost); a price change moves the argmax and owes a "
        "priced gate run just as an added row does"
    )


def test_poison_grow_actuator_prices_are_frozen_whole() -> None:
    """F1, the recall half — the grow menu is priced data too."""
    got = tuple((a["probe"], a["cost"], a["alpha0"], a["beta0"])
                for a in PRC.GROW_ACTUATORS)
    assert got == (("retrieve_rerank", 0.004, 3.0, 7.0),
                   ("retrieve_expand", 0.006, 3.5, 6.5),
                   ("re_extract_strong", 0.020, 4.0, 6.0)), (
        "a grow actuator was re-priced — same argmax move, same debt"
    )
