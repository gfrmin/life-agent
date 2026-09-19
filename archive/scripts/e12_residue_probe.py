#!/usr/bin/env python3
"""E-12's report-economy residue probe (r15 amendment A2, $0).

The one unproven arm of the retired-latch decomposition: the executor never re-asks
with the grow block after a REPORT terminal, on the engine's own claim that grow
"self-gates on the terminal EU … a confident report prices ≈ -cost"
(`answer-brain/brain/answer_brain.jl`). Exact for confident reports; unproven for
low-confidence ones. This probe measures the residue against the LIVE daemon using
the recorded m2-base A-loop wire — the deployed rule end-to-end, nothing
re-implemented (r10's lesson):

for every recorded ``/decide`` exchange whose reply was ``report`` and whose request
carried NO grow block (the economy class), re-POST the same payload plus the grow
block the deployed code would have attached — ``sensors`` from the DEPLOYED
``GO.sensors_from`` over the recorded reply's own posterior, the menu from the
fixture's recorded ``/grow_menu`` reply with costs scaled by the recorded
``u_bar["lambda_usd"]`` exactly as the executor spells it — and read the effector.

FROZEN CRITERIA (r15 A2, committed before this instrument ran):
- zero effector flips  ⇒  E-12 is re-classified verified-economy/mechanics; NO code
  changes; the fixture set stays intact.
- any flip             ⇒  the residue is real: the grow re-ask fires after reports
  too, landing with its cassette-miss fixture cost counted under DIR-E12.

Usage: a daemon must answer on :8799 (`julia --project=. apps/answer-brain/daemon/main.jl`
in the credence repo). Then:  uv run python scripts/e12_residue_probe.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
from typing import Any

import life_agent.core.gather_outcomes as GO
from life_agent.core import config as C

DAEMON = "http://127.0.0.1:8799"


def _post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def _indeterminate(fx: dict[str, Any]) -> int:
    body = (fx.get("outputs") or {}).get("log_decision") or {}
    dec = body.get("decision") or body
    try:
        return int(dec.get("n_indeterminate") or 0)
    except (TypeError, ValueError):
        return 0


def main() -> int:
    d = C.KB / "eval" / "collapse-fixtures" / "m2-base"
    fixtures = sorted(d.glob("*-aloop-*.json"))
    if not fixtures:
        print(f"no A-loop fixtures under {d}", file=sys.stderr)
        return 2
    probed = flips = 0
    skipped: list[str] = []
    flip_rows: list[str] = []
    for path in fixtures:
        fx = json.loads(path.read_text())
        wire = fx.get("wire") or []
        menu_replies = [e["response"] for e in wire if e["seam"] == "http"
                        and str(e["request"].get("url", "")).endswith("/grow_menu")]
        if not menu_replies:
            skipped.append(f"{fx.get('question_id')}: no recorded /grow_menu")
            continue
        menu = menu_replies[0]["grow"]
        n_ind = _indeterminate(fx)
        for e in wire:
            if e["seam"] != "http" or not str(e["request"].get("url", "")).endswith("/decide"):
                continue
            payload = e["request"]["payload"]
            reply = e["response"]
            if reply.get("effector") != "report" or "grow" in payload:
                continue
            u_bar = payload["u_bar"]
            rate = float(u_bar["lambda_usd"])  # E-5: REQUIRED, fails loud
            scaled = {**menu, "actuators": [dict(a, cost=float(a["cost"]) * rate)
                                            if "cost" in a else a
                                            for a in menu["actuators"]]}
            sensors = GO.sensors_from(candidates=list(payload["candidates"]),
                                      credences=list(reply.get("credences") or []),
                                      p_none=reply.get("p_none"),
                                      indeterminate=n_ind)
            grown = {**payload, "sensors": sensors, "grow": scaled}
            out = _post(f"{DAEMON}/decide", grown)
            probed += 1
            if out.get("effector") != "report":
                flips += 1
                flip_rows.append(f"{fx.get('question_id')}: report -> "
                                 f"{out.get('effector')}/{out.get('probe')} "
                                 f"(eu {reply.get('eu')} -> {out.get('eu')})")
    print(f"A-loop fixtures: {len(fixtures)} · economy-class report consults probed: "
          f"{probed} · effector flips: {flips}")
    for row in flip_rows:
        print(f"  FLIP {row}")
    for row in skipped:
        print(f"  (skipped {row})")
    print("verdict:", "RESIDUE REAL — the fix lands with its DIR-E12 fixture cost"
          if flips else "ZERO FLIPS — E-12 re-classified verified-economy; no code change")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
