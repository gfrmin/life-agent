#!/usr/bin/env python3
"""The fresh-clone decide smoke: a stranger's checkout reaches a DECISION, keyless.

`scripts/smoke-fresh-clone.sh` proved retrieval — the sample corpus builds and each
synthetic fact retrieves to its own document. It stopped there, one step short of the
thing this repo is: nothing in CI booted the bridge, and every ask goes through the
bridge, so a clone could pass the smoke and still answer *"the decider is unavailable"*
the first time someone asked it something.

This closes that step without a key, a network or a model call:

1. Boot the REAL `BridgeServer` on the sample sandbox's catalogue, with a **tripwire**
   in place of the extraction client — any model call at all is a failure, not a cost.
2. `GET /ready` must report a decider, and report it as the **host** act. A stranger
   downloads no engine to get one (`make engine` is a door, not a dependency).
3. `POST /decide` twice over HTTP, with the posterior in the body: evidence that settles
   on one candidate must COMMIT, and evidence that disperses must WITHHOLD. That is the
   one argmax (`core/decide.bayes_act`), reached the way the executor reaches it.
4. Render both origin lines a reply can carry — from your documents, and declined with a
   reason — because rule 3 is what the answer is *for*.

The gauge is the shipped example (`config/utility-model.example.yaml`) folded with **no
evidence**, i.e. the declared prior: u(correct) +1, u(wrong) -9, so the commit bar is
0.90. A stranger's KB has no elicitations and this smoke states that rather than
inventing a gauge.

    uv run python scripts/smoke_decide.py --sandbox <dir from bootstrap-sample.sh>
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb

from life_agent.bridge.server import BridgeDeps, BridgeServer
from life_agent.core import decide as D
from life_agent.core import decisions as DEC
from life_agent.core import executor as EX
from life_agent.core import lookup as LK
from life_agent.core import utility as UT
from life_agent.core.decider import Decider


class NoModel:
    """The tripwire. This smoke asserts a path that must not reach a model: if the bridge
    ever calls one here, CI is telling a stranger their keyless clone works when it does
    not."""

    engine_version = "smoke-no-model"

    def complete(self, *a: Any, **k: Any) -> Any:
        raise AssertionError(
            "the keyless smoke called a model — this path must not need one")


def fail(msg: str) -> None:
    print(f"SMOKE FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def declared_gauge(repo: Path) -> dict[str, float]:
    """The shipped example model, folded with no evidence — the DECLARED prior."""
    model = UT.load_model(repo / "config" / "utility-model.example.yaml")
    return UT.posterior(model, [], policy=LK.U_BAR_POLICY).u_bar()


def http(base: str, path: str, body: dict[str, Any] | None = None) -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(base + path, data=data,
                                 method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"null")


def _request(candidates: list[str], observations: list[dict[str, Any]],
             rho: float) -> dict[str, Any]:
    """One /decide body: the posterior's inputs, string-blind to the decider."""
    return {"question_id": "q" * 16, "candidates": candidates, "rho": rho,
            "observations": observations, "applied_probes": [], "hits": [],
            "shape": "unqualified_current_value"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sandbox", type=Path, required=True,
                    help="the directory bootstrap-sample.sh built (holds pkm-store/)")
    args = ap.parse_args(argv)
    repo = Path(__file__).resolve().parent.parent

    store = args.sandbox / "pkm-store"
    catalogue = store / "catalogue.duckdb"
    if not catalogue.is_file():
        fail(f"no sample catalogue at {catalogue} — run bootstrap-sample.sh first")

    gauge = declared_gauge(repo)
    bar = -gauge["u_wrong"] / (gauge["u_correct"] - gauge["u_wrong"])
    print(f"== gauge: the shipped example, no evidence folded — u_wrong "
          f"{gauge['u_wrong']:.1f}, commit bar {bar:.2f}")

    conn = duckdb.connect(str(catalogue), read_only=True)
    conn.execute("INSTALL fts; LOAD fts;")
    deps = BridgeDeps(root=store, conn=conn, client=NoModel(),
                      profile="I am the owner.", u_bar=lambda shape: gauge,
                      decisions_path=args.sandbox / "decisions.jsonl",
                      reactions_path=args.sandbox / "reactions.jsonl",
                      fold_version=lambda: "smoke-example-gauge",
                      gather_outcomes_path=args.sandbox / "gather_outcomes.jsonl",
                      decider=Decider(lambda: gauge))
    server = BridgeServer(deps, host="127.0.0.1", port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    # server_address is typed loosely (a unix socket path may be bytes); this server is
    # always AF_INET on 127.0.0.1, so name that rather than interpolating an unknown.
    _host, _port = server.server_address[:2]
    base = f"http://127.0.0.1:{int(_port)}"
    try:
        print("== 1. /ready reports a decider, and it is the host act ==")
        ready = http(base, "/ready")
        decider = ready.get("decider") or {}
        if not decider.get("enabled"):
            fail(f"/ready reports no decider: {ready}")
        if decider.get("kind") != "host":
            fail(f"/ready decider is {decider.get('kind')!r}, not the host act — a "
                 "stranger must not need an engine download to decide")
        print(f"  {json.dumps(ready.get('decider'))}")

        print("== 2. /decide commits when the evidence settles on one candidate ==")
        settled = http(base, "/decide", _request(
            ["A"], [{"reports": 0, "group": g, "authority": 1.0,
                     "subject_factor": 1.0, "time_factor": 1.0} for g in range(3)], 1.0))
        if settled["act"] not in D.ACTIONS:
            fail(f"/decide returned an action outside the menu: {settled['act']!r}")
        if settled["act"] != "respond":
            fail(f"three independent reports of one candidate chose "
                 f"{settled['act']!r} at p1 {settled['p1']:.3f} (bar {bar:.2f}) — "
                 "the act never commits, which is a system that cannot answer")
        print(f"  act {settled['act']} at p1 {settled['p1']:.3f} (bar {bar:.2f})")

        print("== 3. /decide withholds when the evidence disperses ==")
        split = http(base, "/decide", _request(
            ["A", "B"], [{"reports": i, "group": i, "authority": 1.0,
                          "subject_factor": 1.0, "time_factor": 1.0} for i in (0, 1)], 0.5))
        if split["act"] != "abstain":
            fail(f"one report each for two candidates (p1 {split['p1']:.3f}) chose "
                 f"{split['act']!r} — never invent is rule 1")
        print(f"  act {split['act']} at p1 {split['p1']:.3f}")

        print("== 4. every reply carries its origin (rule 3) ==")
        documents = LK.origin_line("documents")
        # A declined route, shaped as `executor.decide_via_loop` builds it when /route
        # says this is not a verbatim point fact. Its reply IS the origin line.
        declined = EX.render_view({
            "effector": "abstain", "rendered": EX.DECLINED_NOT_POINT_FACT,
            "origin": DEC.Origin("declined",
                                 reason=DEC.REASON_NOT_POINT_FACT).as_dict()})
        for line in (documents, declined):
            if not line.strip():
                fail("an origin line rendered empty")
        print(f"  {documents}\n  {declined}")
    finally:
        server.shutdown()
        server.server_close()

    print("\nSMOKE PASS: a fresh clone boots the bridge, reaches the host act over HTTP, "
          "commits and withholds on the evidence, and names its origin — no key, no "
          "network, no engine.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
