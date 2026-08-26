"""Q5's volatility transcript (M6/r16 P-VII, design §9 Q5) — $0 by construction.

The question (deferred to M6 by the design's own ruling): BR-1 lets the half-life
table OVERRIDE the route model's ``time_indexed`` verdict, and V-1's first-match
keyword order is a hand rule. Is a latent with a prior warranted?

**The frozen decision rule (r16 P-VII, the design's own words): a latent with a
prior is warranted iff the disagreements are NOT all the table's wins.** A "table
win" is a disagreement where the override is protective or corrective in kind — the
named exemplar class is q-014 (the model called a mobile number permanent; the table
decayed it). The transcript publishes every disagreement row so the call is made on
the published table, not on this docstring.

Reads, for every eval question: the CACHED route derivation (the model's own
``time_indexed`` verdict — `lookup.route_question` consults the §18.9 cache before
any client call) and the table's verdict (``VOL.half_life(construct) < PERMANENT``).
The client is a RefusingClient carrying the LIVE engine version (the cache key
covers it), so a cold route is a NAMED absence, never a charge. No decision-path
code is touched either way — the transcript DECIDES the §9 Q5 disposition entry
only.

Usage:
  LIFE_AGENT_KB=... PKM_CONFIG=... uv run python scripts/q5_volatility_transcript.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from life_agent.collapse import taps as T
from life_agent.core import config as CFG
from life_agent.core import lookup as LK
from life_agent.core import volatility as VOL


def _engine_version() -> str:
    from life_agent.core import instrument as INSTR

    return str(INSTR.instrument_client(LK.LOOKUP_MODEL).engine_version)


def main() -> int:
    root = CFG.pkm_root()
    if root is None:
        print("no pkm root", file=sys.stderr)
        return 2
    qpath = Path(CFG.KB) / "eval" / "questions_v2.yaml"
    raw = yaml.safe_load(qpath.read_text(encoding="utf-8"))
    questions = raw if isinstance(raw, list) else raw["questions"]
    client = T.RefusingClient(engine_version=_engine_version())

    rows: list[dict] = []
    cold: list[str] = []
    narrative: list[str] = []
    for q in questions:
        qid, question = str(q["id"]), str(q["question"])
        try:
            r = LK.route_question(root, question, client=client)
        except T.WouldSpendError:
            cold.append(qid)
            continue
        if r is None:
            narrative.append(qid)
            continue
        hl = VOL.half_life(r.construct)
        rows.append({"id": qid, "construct": r.construct,
                     "model_time_indexed": bool(r.time_indexed),
                     "table_time_indexed": bool(hl < VOL.PERMANENT),
                     "half_life_years": hl})

    disagree = [r for r in rows if r["model_time_indexed"] != r["table_time_indexed"]]
    print(f"routed {len(rows)} · narrative-routed {len(narrative)} · cold {len(cold)}")
    if cold:
        print(f"  cold (named absences): {', '.join(cold)}")
    print(f"disagreements: {len(disagree)} of {len(rows)}"
          f" ({100.0 * len(disagree) / len(rows):.1f}%)" if rows else "no routed rows")
    print("\n| id | construct | model | table | half-life (y) |")
    print("|---|---|---|---|---|")
    for r in disagree:
        print(f"| {r['id']} | {r['construct']} | "
              f"{'time-indexed' if r['model_time_indexed'] else 'permanent'} | "
              f"{'time-indexed' if r['table_time_indexed'] else 'permanent'} | "
              f"{r['half_life_years']:g} |")
    over = [r for r in disagree if r["table_time_indexed"] and not r["model_time_indexed"]]
    under = [r for r in disagree if r["model_time_indexed"] and not r["table_time_indexed"]]
    print(f"\ntable overrides model-permanent -> decays (the q-014 protective class): {len(over)}")
    print(f"table overrides model-time-indexed -> permanent (the risk class): {len(under)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
