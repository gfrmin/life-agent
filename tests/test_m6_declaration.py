"""M6 (r16) — the observation model declared once: the drift gates and the one-declaration
behavioural pins for the checkpoint's unifications (D-11 / D-14 / D-15) and its riders
(D-12 / D-13). Pure-refactor checkpoint: every pin here asserts a SPELLING property or
the one function's behaviour; the behaviour itself is byte-pinned by the m5-base replay
(G2, pure equality)."""
from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path as GuardPath

sys.path.insert(0, str(GuardPath(__file__).resolve().parent))

import _guard_ast as G

# --- P-I (D-11): the value-join is ONE declaration ------------------------------------


def test_d11_the_lattice_join_is_one_declaration() -> None:
    """Both edge joins bind the one lattice join; the exact-norm-match idiom appears
    exactly once in the bridge (a second spelling cannot exist)."""
    from life_agent.bridge import server as BR
    from life_agent.core import lookup as LK

    assert hasattr(BR, "_lattice_join"), "the one join function must exist (D-11)"
    src = inspect.getsource(BR)
    # word-bounded: a bare substring also matches the confirm probe's `== vkey`
    assert len(re.findall(r"\bkey\(c\) == vk\b", src)) == 1, (
        "the candidate equality scan must have ONE spelling — inside _lattice_join. r34 "
        "moved it from _norm_value to _candidate_key (the §4.2 declared identity), r36 "
        "reverted it, and r37 parameterised it so the tap's counterfactual re-runs THIS "
        "rule; the pin follows the spelling because its job is to forbid a SECOND scan, "
        "not to freeze which key the scan uses")
    assert inspect.signature(BR._lattice_join).parameters["key"].default is LK._norm_value, (
        "the DEPLOYED identity is the default argument — r36's revert. r37 made the key a "
        "parameter for the tap's counterfactual only; if the default moves, the lever has "
        "shipped, and it may only ship through its own pre-registration")
    assert G.calls(BR._probe_corroborate, "_lattice_join"), (
        "BR._probe_corroborate does not CALL _lattice_join() — one declaration, one home; a "
        "source substring would be satisfied by a comment (r23 F10)")
    assert G.calls(BR._join_deliberate_value, "_lattice_join"), (
        "BR._join_deliberate_value does not CALL _lattice_join() — one declaration, one home; a "
        "source substring would be satisfied by a comment (r23 F10)")


def test_d11_join_exact_normalised_match() -> None:
    from life_agent.bridge import server as BR

    idx, minted = BR._lattice_join("  P123 ", ["P123", "Q999"], allow_new=False)
    assert (idx, minted) == (0, None)   # PII-OK: synthetic id shapes


def test_d11_join_unique_containment_confirms() -> None:
    from life_agent.bridge import server as BR

    idx, minted = BR._lattice_join(
        "the contact is Abbot Corden for now", ["Abbot Corden"], allow_new=False)
    assert (idx, minted) == (0, None)   # PII-OK: synthetic personal-name shape


def test_d11_join_superset_extension_refused() -> None:
    from life_agent.bridge import server as BR

    idx, minted = BR._lattice_join(
        "Xylia Abbot Corden", ["Abbot Corden"], allow_new=False)
    assert (idx, minted) == (None, None)   # PII-OK: synthetic personal-name shapes


def test_d11_join_competing_shape_refused() -> None:
    from life_agent.bridge import server as BR

    # PII-OK: synthetic digit shapes on the next line
    idx, minted = BR._lattice_join("9999 8888", ["8888"], allow_new=False)  # PII-OK
    assert (idx, minted) == (None, None)


def test_d11_join_mint_gated_on_not_contained() -> None:
    from life_agent.bridge import server as BR

    # outside the set + allow_new -> minted at len(candidates)
    idx, minted = BR._lattice_join("Z777", ["P123"], allow_new=True)
    assert (idx, minted) == (1, "Z777")    # PII-OK: synthetic id shapes
    # ambiguous containment (a known candidate mentioned) must NOT mint wholesale
    idx, minted = BR._lattice_join(
        "Xylia Abbot Corden", ["Abbot Corden"], allow_new=True)
    assert (idx, minted) == (None, None)


def test_d11_joined_observation_shape_is_the_one_builder() -> None:
    """The r09-D1 uniform wire keys ride every joined observation, from ONE builder."""
    from life_agent.bridge import server as BR

    ob = BR._joined_observation(0, ["P123"], None, time_factor=0.5,
                                competition_factor=0.7)
    assert ob == {"reports": 0, "group": 0, "authority": 1.0, "subject_factor": 1.0,
                  "time_factor": 0.5, "competition_factor": 0.7,
                  "quote": "", "doc_key": "", "value_norm": "p123"}
    minted = BR._joined_observation(1, ["P123"], "Z777", time_factor=1.0,
                                    competition_factor=1.0)
    assert minted["reports"] == 1 and minted["value_norm"] == "z777"


# --- P-II (D-14): the one recency policy's date-selection is ONE declaration ----------


def test_d14_the_date_selection_is_one_declaration() -> None:
    from life_agent.bridge import server as BR
    from life_agent.core import lookup as LK

    assert hasattr(LK, "source_date_iso"), "the one date-selection must exist (D-14)"
    assert G.calls(BR._source_time_factor, "source_date_iso"), (
        "the bridge's recency covariate must BIND the declared selection")


def test_d14_freshest_source_attestation_wins() -> None:
    from life_agent.core import lookup as LK

    assert LK.source_date_iso(["2020-01-01", None, "2024-06-05"],
                              "2019-01-01") == "2024-06-05"


def test_d14_self_reported_as_of_is_the_fallback() -> None:
    from life_agent.core import lookup as LK

    assert LK.source_date_iso([None, None], "2019-01-01") == "2019-01-01"
    assert LK.source_date_iso([], None) is None


# --- P-III (D-15): the verdict→evidence projection is ONE declaration -----------------


def test_d15_the_projection_table_is_one_object() -> None:
    """M4's binding pattern: the membrane's (action, valence)→y table IS the declared
    one (is-identity — a second spelling cannot drift)."""
    from life_agent.core import reactions as RX
    from life_agent.membrane import session as SES

    assert SES._VERDICT_Y is RX.VERDICT_Y


def test_d15_the_declaration_names_every_branch() -> None:
    """The one declaration's docstring/comment names the full domain: the y table
    (M-7), the Claude channel under owner precedence (M-6), and the utility branches
    (R-3/R-4/R-5) — a reader lands on every branch from the one home."""
    from life_agent.core import reactions as RX

    src = inspect.getsource(RX)
    assert "VERDICT_Y" in src
    assert "claude_verdicts.y" in src
    assert "boot_snapshot" in src            # the owner ≻ Claude precedence site
    assert "_lookup_reaction" in src and "_narrative_reaction" in src


def test_d15_the_table_content_is_unchanged() -> None:
    from life_agent.core import reactions as RX

    assert RX.VERDICT_Y == {
        ("report", "good"): 1, ("report", "bad"): 0,
        ("report_scoped", "good"): 1, ("report_scoped", "bad"): 0,
        ("abstain", "good"): 0, ("abstain", "bad"): 1,
    }


# --- P-IV: every §3.3 clause home carries its declaration stamp -----------------------

_STAMPS: tuple[tuple[str, str], ...] = (
    ("life_agent.core.lookup", "[§3.3 · L-1/E-10]"),
    ("life_agent.core.lookup", "[§3.3 · L-2]"),
    ("life_agent.core.lookup", "[§3.3 · L-4]"),
    ("life_agent.core.lookup", "[§3.3 · L-5/GA-3]"),
    ("life_agent.core.lookup", "[§3.3 · L-6]"),
    ("life_agent.core.lookup", "[§3.3 · L-7]"),
    ("life_agent.core.lookup", "[§3.3 · L-8]"),
    ("life_agent.core.lookup", "[§3.3 · L-10]"),
    ("life_agent.core.lookup", "[§3.3 · D-14]"),
    ("life_agent.bridge.server", "[§3.3 · D-11/BR-2]"),
    ("life_agent.bridge.server", "[§3.3 · BR-1]"),
    ("life_agent.bridge.server", "[§3.3 · BR-4]"),
    ("life_agent.bridge.server", "[§3.3 · BR-8]"),
    ("life_agent.core.volatility", "[§3.3 · V-1]"),
    ("life_agent.core.deliberate", "[§3.3 · DL-2]"),
    ("life_agent.core.deliberate", "[§3.3 · DL-3]"),
    ("life_agent.membrane.world", "[§3.3 · M-9]"),
    ("life_agent.core.gather_outcomes", "[§3.3 · GO-1]"),
    ("life_agent.core.gather_outcomes", "[§3.3 · GO-2]"),
    ("life_agent.core.narrative", "[§3.3 · N-1]"),
    ("life_agent.core.narrative", "[§3.3 · N-4]"),
    ("life_agent.core.reactions", "[§3.3 · D-15]"),
    ("life_agent.core.executor", "[§3.3 · E-10]"),
)


def test_every_clause_home_carries_its_stamp() -> None:
    """P-IV: the observation model's clauses are findable from the design and back —
    each declared home names its clause id in the uniform stamp form. A stamp that
    disappears (a refactor moving a clause without its declaration) fails here."""
    import importlib

    for module_name, marker in _STAMPS:
        src = inspect.getsource(importlib.import_module(module_name))
        assert marker in src, f"{module_name} lost its clause stamp {marker}"


# --- P-V riders: D-12 (one edge-name constructor) + D-13 (env constants read once) ----


def test_d12_edge_names_have_one_constructor() -> None:
    """One `edge_id(kind, model)` (§5.3 D-12): the executor's extract edge and the
    deliberate edge are BINDINGS of it — a hand-built f-string at a call site would
    silently split the curve/attribution namespace."""
    from life_agent.core import decisions as DEC
    from life_agent.core import deliberate as DL
    from life_agent.core import executor as EX

    assert DEC.edge_id("extract", "m") == "extract@m"
    assert DEC.edge_id("deliberate", "m") == "deliberate@m"
    assert EX.extract_edge("m") == "extract@m"
    assert DL.instrument("m") == "deliberate@m"
    assert G.calls(EX.extract_edge, "edge_id"), (
        "EX.extract_edge does not CALL edge_id() — one declaration, one home; a "
        "source substring would be satisfied by a comment (r23 F10)")
    assert G.calls(DL.instrument, "edge_id"), (
        "DL.instrument does not CALL edge_id() — one declaration, one home; a "
        "source substring would be satisfied by a comment (r23 F10)")


def test_d13_the_stack_urls_are_read_once() -> None:
    """D-13: `LIFE_AGENT_BRIDGE_URL`/`ANSWER_BRAIN_URL` are read in ONE place
    (ask_client); ask.py binds — a second environ read can drift its default."""
    from pathlib import Path

    ask_src = (Path(__file__).resolve().parent.parent / "scripts" / "ask.py").read_text()
    assert 'os.environ.get("LIFE_AGENT_BRIDGE_URL"' not in ask_src
    assert 'os.environ.get("ANSWER_BRAIN_URL"' not in ask_src
    assert "EXECUTOR_BRIDGE = AC.BRIDGE" in ask_src
    assert "EXECUTOR_DAEMON = AC.DAEMON" in ask_src


# --- r34: the value-join binds the DECLARED candidate identity -------------------------


def test_r34_join_binding_is_reverted_and_the_defect_is_pinned_live() -> None:
    """r34: `_lattice_join` is M6's one value-join, but it tested identity with
    `_norm_value` (whitespace+casefold) while `candidates_from`, `render`, `era_split`, the
    S2 grow join and the confirm probe all use `_candidate_key` (the §4.2 canonical key).
    Two declarations of one relation, numbered under different clauses. The edges therefore
    MINTED spelling variants the rest of the lattice considers one candidate."""
    from life_agent.bridge import server as BR
    from life_agent.core import lookup as LK

    # PII-OK: synthetic amount, the shape of the round-8 three-spelling split
    base, variants = "HKD 12345.67", ["HKD 12,345.67", "12345.67 HKD"]
    assert len({LK._candidate_key(c) for c in [base, *variants]}) == 1, (
        "premise: the declared key already calls these one candidate")

    # r36 REVERTED the binding on a K3 attribution kill, so the defect is live again and
    # PINNED as live: each variant is still minted as its own atom. r37 carries the successor.
    cands = [base]
    for v in variants:
        _idx, minted = BR._lattice_join(v, cands, allow_new=True)
        assert minted == v, "r36's revert is in force — the variant is still minted"
        cands = [*cands, minted]
    assert len({LK._candidate_key(c) for c in cands}) == 1, (
        "the declared identity still calls them ONE candidate — this is the standing defect")


def test_r34_the_join_is_a_monotone_coarsening() -> None:
    """Whatever `_norm_value` joined, the declared key still joins — `_candidate_key` falls
    back to it. The change can only merge MORE, never split more; that property is what makes
    the lever's risk surface enumerable (C1)."""
    from life_agent.bridge import server as BR

    idx, minted = BR._lattice_join("  p123 ", ["Q999", "P123"], allow_new=True)  # PII-OK
    assert (idx, minted) == (1, None), "the whitespace+case join must survive unchanged"


def test_r34_distinct_significant_digits_still_never_merge() -> None:
    """The confident-wrong boundary is `_candidate_key`'s, and binding it here inherits it
    rather than widening it: two genuinely different numbers stay two candidates."""
    from life_agent.bridge import server as BR

    idx, minted = BR._lattice_join("HKD 99999.99", ["HKD 12345.67"], allow_new=True)  # PII-OK
    assert idx == 1 and minted == "HKD 99999.99"   # unchanged by r36's revert


def test_r37_no_call_site_overrides_the_joins_identity_except_the_tap() -> None:
    """r37 parameterised the value-join's identity so the tap's counterfactual re-runs the
    deployed rule instead of copying it (`M-7`). That parameter is a back door to a SECOND
    declared identity on the decision path, so it is gated: `_join_tap` is the only caller
    in `src/` allowed to pass `key=`."""
    import ast

    repo = GuardPath(__file__).resolve().parent.parent
    offenders: list[str] = []
    for path in (repo / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        enclosing: dict[ast.AST, str] = {}
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef):
                for node in ast.walk(fn):
                    enclosing[node] = fn.name
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "_lattice_join"):
                continue
            if not any(kw.arg == "key" for kw in node.keywords):
                continue
            if enclosing.get(node) != "_join_tap":
                offenders.append(f"{path.name}:{node.lineno} in {enclosing.get(node)}")
    assert not offenders, (
        "a non-default identity key reached the value-join outside the tap — that is a "
        f"second declaration of candidate identity by the back door: {offenders}")
