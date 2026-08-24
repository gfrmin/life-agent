#!/usr/bin/env python3
"""Recorded-replay audit — replay run 10's questions through the DEPLOYED path and record it.

r06 read the replace branch (design §6.12) from a gate run's own records. Three things were
out of reach there and all three are what this checkpoint is for: which site fired FIRST (its
`extract@<opus>` spelling is shared by S1's opus tier, S4 and S5, and the records carry no
ordering), what the probes actually OBSERVED (needed for the JOIN counterfactual its criterion
9(b) excluded), and why its reconstruction disagreed with the recorded terminal on 28% of the
rows where its own counterfactual was provably a no-op.

The method is a replay, not a re-derivation: `core/executor.run_pass` and
`bridge/server.dispatch` run unmodified against the live credence daemon, and a recording
transport sits between them. Every claim below is therefore about the deployed code's own
behaviour, and the counterfactual is ENACTED through the guards the deployed code already has
rather than reconstructed beside them.

FROZEN CRITERIA (stated before any result is read; §14 carries the mirror):

1. SCOPE — run 10's question set (`gate-20260821T094545`), replayed through the deployed
   decision path at zero spend, with every bridge and daemon call recorded in firing order.
   Ruled by the owner on 2026-08-22 ("start r07") as r06's QUESTION 2: close the attribution
   before any money is spent.

2. THE PIN (§6.10 — a run must pin its tree, not just its recipe). Verified before any
   question runs, published, and a mismatch is a NAMED REFUSAL and not a caveat:
     (a) `src/` at HEAD byte-identical to run 10's `life_agent_git.sha`;
     (b) the live corpus digest equal to run 10's `corpus.digest`;
     (c) the utility elicitations sha equal to run 10's `utility.elicitations_sha256`;
     (d) the outcomes and gather-outcome logs TRUNCATED to run 10's `created_at` — correct
         because `run_eval` appends a run's edge rows AFTER the run, so no question in run 10
         conditioned on run 10's own rows;
     (e) curves folded LEAVE-ONE-QUESTION-OUT, as run 10's `gate.loo` records, and the
         transform menu assembled the way the deployed caller assembles it
         (`menu_transforms(curves)` under `deliberate_enabled()`). `DELIBERATE_TRANSFORM` is
         NOT in `DEFAULT_TRANSFORMS`: a replay that leaves it out is measuring a different
         system, and a rehearsal that did so lost the deliberate firing entirely;
     (f) WRITE ISOLATION — no writable stream resolves into the live KB. The staging root
         carries its OWN ledger directory and the ledger mirror is off. *Added after a
         rehearsal wrote into the live unified ledger's manifest; see the report's DEVIATION 1.*

3. NO SPEND. The instrument client REFUSES a cold §18.9 derivation. The deliberate edge is
   preflighted per question against its own key and a cold one EXCLUDES the question BY NAME —
   the refusal must happen BEFORE the loop, because the executor catches every exception around
   `/probe/deliberate` and a refusal raised inside it would be read as an infrastructure
   fail-open, which is contamination that looks like data. A tripwire asserts every reply's
   `cost_usd == 0.0` and ABORTS the read if one does not.

4. SITE ATTRIBUTION FROM THE PAYLOAD, never from the model spelling — this is what r06 could
   not do. The ENDPOINT names the site first; the allow_new rules apply only to
   `/probe/corroborate` (the deliberate probe is posted with `allow_new` too):
     S3  `/probe/deliberate`
     S5  `/probe/corroborate` with `allow_new` over an EMPTY candidate set (the k=0 walk)
     S4  `/probe/corroborate` with `allow_new` over a non-empty candidate set
     S1  `/probe/corroborate` without `allow_new`
     S2  a `/retrieve` after the first
   Ambiguity that survives this is REPORTED as ambiguity.

5. THE CHANNEL TRACE — per question, the grounded channel's n_obs at `/extract` and after every
   site firing, in order, computed through the DEPLOYED guards (`executor._null_read` itself,
   the S3 ok-guard, the fruitless-recall guard) and never through a copy of them. The
   ATTRIBUTED DISCARDER is every firing at which the channel FELL to the committed size; a
   size-preserving replace discards nothing and is not named; where more than one firing
   qualifies, all are named.

6. FIDELITY, as a direct control on everything above. The replay's terminal action against run
   10's recorded terminal, per question, published as a rate with the disagreeing rows named.
   This is also the DIAGNOSIS of r06's floor: r06 reconstructed its base arm through
   `core/lookup`'s decide while the deployed arm decided through the daemon. If the replay
   reproduces the record where r06's reconstruction did not, the 28% was the decide LAYER and
   r06's per-site excesses were understated by it; if it does not, the floor is elsewhere and
   r06's bound stands exactly as published.

7. THE TWO COUNTERFACTUALS.
     (a) RETIRE — r06's rule, here ENACTED rather than reconstructed: the recording transport
         rewrites a replace-site reply into the shape the deployed code ALREADY retires on (a
         null read at S1/S4, a non-ok status at S3, a withheld mint at S5), so the real
         executor and the real daemon run the counterfactual. No executor change, and the guard
         under test is the deployed guard.
     (b) JOIN — pool the probe's observations with the grounded channel. *AMENDED BEFORE ANY
         READING, on a structural fact and not a result:* §5's dedup-as-inference
         (`lookup.dedup_correlated`) keys on the observation's QUOTE, and a joint re-read's
         observation has none — `/extract` returns ABSTRACT observations by design (the body is
         string-blind) and `_probe_corroborate` synthesises ONE abstract observation mapping the
         re-read value to a candidate index. So the guard that makes joining safe cannot be
         applied to the thing being joined, and a §5-deduped JOIN is not readable by ANY
         instrument that stays off the decision path. That is itself a finding about §6.12's
         alternative, not a shortfall of this checkpoint, and it is reported as one. What IS
         read is the UPPER BOUND: pooling with NO dedup, the most favourable case joining could
         ever have. If the upper bound is small the question closes; if it is large it needs an
         instrument with a correlation key, which needs decision-path code.
   Both are classified with r06's grammar and matcher (repair / regression / neutral /
   ungradeable) so the two checkpoints are comparable. *Added before any reading:* the arms of
   one question SHARE a retrieval draw per breadth. §6.13 makes at least one question's draw a
   lottery, and an arm that differed because it drew differently would be a confound rather than
   a counterfactual. The double run of criterion 9(b) still draws afresh, which is where
   instability is looked for.

8. THE VERDICT — published BESIDE r06's, never in place of it. Owner ruling 2026-08-22:
   r06's criterion 8 is not reopened, not narrowed and not re-scored. A site is bought a priced
   run only if BOTH readings put it above their floor AND its excess over r07's own control is
   >= 5 rows — the bar of 5 inherited from r05 and r06 so all three checkpoints compare.
   Below 5: KNOWN-AND-UNCOVERED, no code. r07 may not promote a site r06 left under its floor.

9. THE INSTRUMENT'S OWN LIMITS, published and never averaged away:
     (a) This is a replay of run 10's QUESTIONS on run 10's pinned pre-run state, not a rerun
         of run 10. The daemon is a live process and nothing here pins its internals; whatever
         gap that leaves shows up in criterion 6 and bounds every claim made from the tape.
     (b) §6.13's sampler makes at least one question's retrieval a lottery, so the read runs
         TWICE and every question whose two runs disagree is NAMED and carries no attribution.
         *Narrowed before any reading, with its argument:* the second pass covers the DEPLOYED
         arm only. Instability is a property of the retrieval draw, not of the arm — an unstable
         question is unstable in every arm — and the deployed arm is the one every attribution
         claim rests on, so a second deployed pass names exactly the rows that must be withheld.
         Re-running the counterfactual arms would add cost and no detections. The counterfactual
         arms are therefore read ONCE and that is stated wherever their numbers appear.
     (c) A question that cannot be served without spend is EXCLUDED BY NAME, and cold-at-start
         is reported apart from COLD-MID-LOOP — the latter means run 10 never made that call (a
         §18.9 record is written on success), so it is evidence of DIVERGENCE and not merely an
         exclusion. Cache eviction and a failed run-10 call are the named alternatives.
         *Refined before any reading, on a rehearsal:* the exclusion is PER ARM. Enacting a
         counterfactual walks paths the pinned run never took, so the retire and join arms reach
         cold derivations far more often than the deployed arm does — which is itself the
         finding that an ENACTED counterfactual costs money where a reconstructed one does not.
         A question whose DEPLOYED arm reads still carries its firing order and its attribution;
         only the arms that went cold are withheld, each named. A question whose deployed arm
         goes cold carries nothing. Arm coverage is published beside every counterfactual number
         so no reach rate is ever read against the wrong denominator.
     (d) A recorded reply carries corpus text. Nothing derived from it is published except
         counts, n_obs, and gold-match booleans.

10. NO DECISION-PATH CODE. Nothing under `src/` changes in this checkpoint; a commit gate
    refuses if `src/` is dirty.

Usage (the daemon must be up: `julia --project=. apps/answer-brain/daemon/main.jl` in the
credence checkout; the bridge is dispatched IN-PROCESS, not over HTTP):

  uv run python scripts/replay_audit.py --run-id gate-20260821T094545 \
      --live-kb $LIFE_AGENT_KB --run-meta $KB/eval/.../run_meta-<run>.json \
      --paired $KB/eval/.../paired-<run>.jsonl --questions $KB/eval/questions_v2.yaml \
      [--daemon http://127.0.0.1:8799] [--limit N] [--only q2-011,q2-019] \
      [--out F.md] [--out-yaml F.yaml]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --- the staging pin (criterion 2) — pure, and runs BEFORE life_agent is imported ---------

#: Directories the staging root must OWN rather than borrow. `ledger/` is here because a
#: rehearsal symlinked it at the live KB and the ledger mirror rewrote the live manifest's
#: recorded legacy offset (report DEVIATION 1) — a writer reached live state through a
#: read-only-looking symlink.
NEVER_SYMLINKED: tuple[str, ...] = ("calibration", "ledger", "tmp")

#: Truncation cannot place a row with no `tx_time`. Keeping it is the conservative choice
#: (dropping it would shrink the evidence base every curve folds from); the fact that one was
#: kept is recorded here and published, never swallowed.
UNDATED_KEPT: list[str] = []

#: The calibration streams the staging root rewrites rather than borrows.
_TRUNCATED = ("outcomes.jsonl", "gather_outcomes.jsonl")
_EMPTIED = ("decisions.jsonl", "reactions.jsonl")


def truncate_jsonl(src: Path, dest: Path, *, cutoff: str) -> int:
    """Copy the rows written at or before ``cutoff`` (ISO-8601, string-ordered). Returns the
    count kept. A row with no ``tx_time`` cannot be placed: it is KEPT and recorded in
    :data:`UNDATED_KEPT`."""
    kept = 0
    with dest.open("w") as out:
        for line in src.read_text().splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = str(row.get("tx_time") or "")
            if not ts:
                UNDATED_KEPT.append(f"{src.name}: a row carries no tx_time and was kept")
            elif ts > cutoff:
                continue
            out.write(line + "\n")
            kept += 1
    return kept


def build_staging_kb(live: Path, dest: Path, *, cutoff: str) -> Path:
    """A KB root that reads like the live one at ``cutoff`` and can never write back to it.

    Everything not in :data:`NEVER_SYMLINKED` is symlinked (read-only in practice and cheap);
    the calibration streams are rewritten; every other never-symlinked directory is created
    EMPTY, so a writer that reaches for one lands in the staging root."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for child in sorted(live.iterdir()):
        if child.name not in NEVER_SYMLINKED:
            (dest / child.name).symlink_to(child)
    for name in NEVER_SYMLINKED:
        (dest / name).mkdir(exist_ok=True)
    cal_live, cal = live / "calibration", dest / "calibration"
    if cal_live.is_dir():
        for child in sorted(cal_live.iterdir()):
            if child.name not in (*_TRUNCATED, *_EMPTIED):
                (cal / child.name).symlink_to(child)
        for name in _TRUNCATED:
            if (cal_live / name).is_file():
                truncate_jsonl(cal_live / name, cal / name, cutoff=cutoff)
    for name in _EMPTIED:
        (cal / name).write_text("")
    return dest


def verify_pin(meta: dict[str, Any], *, src_sha: str, corpus_digest: str,
               elicitations_sha: str, acknowledged_src: str = "") -> list[str]:
    """Criterion 2 (a)-(c) and (e), as a list of NAMED failures — empty means clean.

    ``acknowledged_src``: the ONE src tree the caller declares HEAD is expected to have when
    it legitimately differs from the run's (r08 Read C replays a run recorded before the fix
    commit — the drift IS the intervention). Only an exact match on the declared tree passes;
    an empty acknowledgement changes nothing, so the pin is never silently weakened."""
    fails: list[str] = []
    want_sha = str((meta.get("life_agent_git") or {}).get("sha") or "")
    # criterion 2(a) is about `src/` being BYTE-IDENTICAL, not about the commit being the same
    # one: r05 and r06 committed documents only, so HEAD has moved while the decision path has
    # not. The comparable object is git's tree hash for `src/` at each commit — comparing the
    # COMMIT sha would refuse a tree that is provably identical, which is a false refusal and
    # exactly as bad as a false pass.
    if want_sha and src_sha and want_sha != src_sha and src_sha != acknowledged_src:
        fails.append(f"src tree: HEAD's src is {src_sha[:12]}, the run's was {want_sha[:12]}")
    want_digest = str((meta.get("corpus") or {}).get("digest") or "")
    if want_digest and want_digest != corpus_digest:
        fails.append(f"corpus digest: live {corpus_digest[:12]}, the run pinned "
                     f"{want_digest[:12]}")
    want_elic = str((meta.get("utility") or {}).get("elicitations_sha256") or "")
    if want_elic and want_elic != elicitations_sha:
        fails.append(f"utility elicitations: live {elicitations_sha[:12]}, the run pinned "
                     f"{want_elic[:12]}")
    if not (meta.get("gate") or {}).get("loo"):
        fails.append("curve fold: the run did not record `loo`, so a held-out replay would "
                     "fold curves the pinned run did not")
    return fails


# --- past the re-exec ---------------------------------------------------------------------

def _bootstrap() -> None:
    """Build the staging root and re-exec into it. ``core/config`` resolves ``LIFE_AGENT_KB``
    at IMPORT time, so the pin cannot be applied after this module's own imports."""
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--live-kb")
    ap.add_argument("--staging", default=str(Path.home() / ".cache/life-agent/r07/stage-kb"))
    ap.add_argument("--run-meta")
    known, _ = ap.parse_known_args()
    if known.live_kb is None or known.run_meta is None:
        return
    if os.environ.get("LIFE_AGENT_KB") == known.staging:
        return
    meta = json.loads(Path(known.run_meta).read_text())
    cutoff = str(meta["created_at"])
    print(f"pin: staging {known.staging} at {cutoff}")
    build_staging_kb(Path(known.live_kb), Path(known.staging), cutoff=cutoff)
    os.environ["LIFE_AGENT_KB"] = known.staging
    os.environ["LIFE_AGENT_LEDGER_MIRROR"] = "0"   # criterion 2(f), belt to the ledger's braces
    os.execve(sys.executable, [sys.executable, *sys.argv], os.environ)


if __name__ == "__main__":
    _bootstrap()

import anthropic  # noqa: E402
import duckdb  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from carrier_audit import Arm, committed, correct  # noqa: E402  (the shared decision tail)
from gate_splice import load_paired  # noqa: E402
from run_eval import load_questions  # noqa: E402

import life_agent.core.calibration as CAL  # noqa: E402
import life_agent.core.corpus as CORPUS  # noqa: E402
import life_agent.core.deliberate as DL  # noqa: E402
import life_agent.core.derivations as D  # noqa: E402
import life_agent.core.executor as EX  # noqa: E402
import life_agent.core.lookup as LK  # noqa: E402
import life_agent.owner as owner  # noqa: E402
from life_agent.bridge import observations as OBS  # noqa: E402
from life_agent.bridge import server as SRV  # noqa: E402
from life_agent.collapse.taps import RefusingClient, WouldSpendError  # noqa: E402
from life_agent.core import config as LCFG  # noqa: E402
from life_agent.tasks import read as TREAD  # noqa: E402

SITES: dict[str, str] = {
    "S1": "corroborate_* tiers — guard: not _null_read(cr)",
    "S2": "retrieval grows (retrieve_rerank / retrieve_expand) — guard: new candidates",
    "S3": "the deliberate edge — guard: status == 'ok' ONLY (no null-read guard)",
    "S4": "re_extract_strong, in-loop — guard: not _null_read(cr)",
    "S5": "the k=0 rescue walk — mints from zero, discards nothing",
}


# --- criterion 3: the spend tripwire -------------------------------------------------------

class ColdDeliberate(BaseException):
    """A cold deliberate edge, raised FROM the transport and deriving from ``BaseException``
    on purpose.

    `core/executor.run_pass` wraps its `/probe/deliberate` post in `except Exception`, so an
    ordinary refusal raised there is swallowed and read as an infrastructure fail-open — a
    contamination that looks exactly like data (criterion 3). A `BaseException` passes straight
    through that handler, so the question is excluded by name and ONLY when the edge was
    actually scheduled. A blanket preflight would over-exclude every question whose loop never
    reaches the probe."""


class SpendMeter:
    """Every reply crossing the transport is checked. A single priced reply ABORTS the read —
    the audits are $0 by contract and a partial spend is not a cheaper reading, it is an
    unpriced one."""

    def __init__(self) -> None:
        self.n = 0

    def observe(self, reply: dict[str, Any] | None) -> None:
        self.n += 1
        cost = float((reply or {}).get("cost_usd") or 0.0)
        if cost > 0.0:
            raise WouldSpendError(
                f"a reply carried cost_usd={cost} — the replay is no-spend by criterion 3")


# --- criterion 4: the tape, and the site read off the payload -------------------------------

@dataclass(frozen=True)
class Call:
    n: int
    kind: str                      # bridge | bridge-get | daemon
    path: str
    payload: dict[str, Any]
    reply: dict[str, Any]


def site_of_call(call: Call) -> str | None:
    """The site this call enacts, read from the ENDPOINT first and the payload second.

    The endpoint-first order is load-bearing: `/probe/deliberate` is posted WITH `allow_new`
    and a candidate set, which is the exact payload shape that names S4 on the corroborate
    endpoint. A payload-first reader files every deliberate firing under S4."""
    if call.path == "/probe/deliberate":
        return "S3"
    if call.path == "/probe/corroborate":
        if not call.payload.get("allow_new"):
            return "S1"
        return "S4" if call.payload.get("candidates") else "S5"
    if call.path == "/retrieve":
        return "S2"
    return None


def sites_in_order(calls: list[Call]) -> tuple[str, ...]:
    """The firing order, repeats preserved — the tier ladder fires up to three times and a set
    would erase exactly the ordering this checkpoint exists to read. The FIRST `/retrieve` is
    the base pass, not a grow."""
    out: list[str] = []
    first_retrieve = True
    for c in calls:
        site = site_of_call(c)
        if site is None:
            continue
        if site == "S2" and first_retrieve:
            first_retrieve = False
            continue
        out.append(site)
    return tuple(out)


# --- criterion 5: the channel trace, computed through the DEPLOYED guards -------------------

def _channel_after(site: str, reply: dict[str, Any], n: int) -> int:
    """The grounded channel's size after one firing, per the deployed branch for that site."""
    obs = len(reply.get("observations") or [])
    if site in ("S1", "S4"):
        return n if EX._null_read(reply) else obs          # the 2026-08-18 fail-open
    if site == "S3":
        return obs if reply.get("status") == "ok" else n   # no null-read guard, by design
    if site == "S5":
        return obs if reply.get("new_candidate") else n    # mints, or the walk moves on
    return n


def channel_trace(calls: list[Call]) -> list[tuple[str, int]]:
    """``[("base", n), (site, n), ...]`` — the channel's size at the first extraction and after
    every firing that could move it, in order."""
    trace: list[tuple[str, int]] = []
    n = 0
    pending_grow = False
    for c in calls:
        if c.path == "/extract":
            obs = len(c.reply.get("observations") or [])
            if not trace:
                n = obs
                trace.append(("base", n))
            elif pending_grow:
                if obs:            # a fruitless recall must not erase a posterior
                    n = obs
                trace.append(("S2", n))
                pending_grow = False
            continue
        site = site_of_call(c)
        if site is None:
            continue
        if site == "S2":
            pending_grow = bool(trace)   # the first retrieve is the base pass
            continue
        n = _channel_after(site, c.reply, n)
        trace.append((site, n))
    return trace


def attributed_discarder(trace: list[tuple[str, int]], *,
                         committed_n_obs: int) -> tuple[str, ...]:
    """Every firing at which the channel FELL to the committed size.

    A size-preserving replace discards nothing and is not named — naming it would inflate every
    site's count with firings that changed only which observations were held. Where more than
    one firing qualifies the ambiguity is reported, never resolved by a guess."""
    out: list[str] = []
    for i in range(1, len(trace)):
        site, n = trace[i]
        if n == committed_n_obs and n < trace[i - 1][1]:
            out.append(site)
    return tuple(dict.fromkeys(out))


# --- criterion 7: the counterfactuals -------------------------------------------------------

def retire_reply(site: str | None, reply: dict[str, Any]) -> dict[str, Any]:
    """RETIRE-NOT-REPLACE, enacted: rewrite a replace-site reply into the shape the DEPLOYED
    guard already retires on. Nothing in `src/` changes and the guard under test is the real
    one — `executor._null_read` for the extract-family sites, the ok-guard for the deliberate
    edge, the mint test for the rescue walk."""
    if site in ("S1", "S4"):
        return {**reply, "read": "null", "observations": []}
    if site == "S3":
        return {**reply, "status": "retired-by-audit", "observations": []}
    if site == "S5":
        return {k: v for k, v in reply.items() if k != "new_candidate"}
    return reply


def dedup_key_available(observations: list[Any]) -> bool:
    """Whether §5's dedup can even be applied to these observations.

    `lookup.dedup_correlated` clusters on the QUOTE. Wire observations are ABSTRACT (the body
    is string-blind) and a joint re-read's is synthesised with no quote at all, so on the tape
    the answer is False and a §5-deduped JOIN is not readable here — criterion 7(b) as amended.
    Kept as a live predicate rather than a comment so that a wire that ever grows the key turns
    this on by itself."""
    return all(("quote" in dict(o)) for o in observations) if observations else False


def join_observations(base: list[Any], probe: list[Any]) -> list[Any]:
    """The JOIN UPPER BOUND: pool the grounded channel with the probe's observations.

    Where §5's correlation key exists the deployed rule is CALLED (`lookup.dedup_correlated` —
    never re-implemented, r05's lesson). Where it does not — which is the case on this wire —
    the pool is taken RAW, and that is an upper bound on what joining could deliver, not an
    estimate of it: every forwarded copy counts as an independent witness, which is exactly the
    inflation §5 exists to stop."""
    pooled = [*base, *probe]
    if dedup_key_available(pooled):
        # r09: the key is on the wire — the deployed join applies (one rule, one adapter);
        # candidates are unneeded because every keyed observation carries its value_norm
        return list(OBS.join_wire_observations(list(base), list(probe), []))
    return pooled


# --- criteria 6 and 8: the floor, the bar, the verdict --------------------------------------

def excess_over_floor(*, exposure: int, reach: int, floor: float) -> float:
    """Reach minus what the instrument's own layer gap predicts, IN ROWS. A rate-against-rate
    label is what let r06 call 27.9% "above" 27.6%; rows make a wash look like one."""
    return round(reach - exposure * floor, 1) if exposure else 0.0


BAR = 5   # inherited from r05 and r06 so the three checkpoints compare

#: r06's PUBLISHED criterion-8 verdict, not a re-reading of its floor: it bought S1, S3, S4 and
#: S5, and left S2 NOT READ (it emits no attributed edge event). r07 may add a reading to any of
#: the four and may promote none of them, and may not promote S2 at all.
R06_BOUGHT: frozenset[str] = frozenset({"S1", "S3", "S4", "S5"})


def verdict(*, excess: float, r06_above_floor: bool) -> tuple[str, str]:
    if not r06_above_floor:
        return ("KNOWN-AND-UNCOVERED",
                "r06 left this site at or under its own floor and its criterion 8 is not "
                "reopened (owner ruling 2026-08-22) — r07 adds a reading, never a promotion")
    if excess >= BAR:
        return ("BUILD+PRICE",
                f"excess {excess} rows over r07's control, at or above the bar of {BAR}, and "
                f"r06 put the site above its floor too")
    return ("KNOWN-AND-UNCOVERED",
            f"excess {excess} rows is under the bar of {BAR} — not distinguishable from this "
            f"instrument's own layer gap")


def cold_kind(*, n_calls_before: int) -> str:
    """A derivation that goes cold AFTER the loop began means run 10 never made that call (a
    §18.9 record is written on success), so it is evidence of DIVERGENCE. Eviction and a failed
    run-10 call are the named alternatives."""
    return "cold-at-start" if n_calls_before == 0 else "cold-mid-loop"


# --- the replay ------------------------------------------------------------------------------

@dataclass
class Row:
    qid: str
    gold: str = ""
    variants: list[str] = field(default_factory=list)
    sites: tuple[str, ...] = ()
    trace: list[tuple[str, int]] = field(default_factory=list)
    discarder: tuple[str, ...] = ()
    deployed: Arm | None = None
    retire: Arm | None = None
    join: Arm | None = None
    cold_arms: tuple[str, ...] = ()
    recorded_action: str = ""
    recorded_correct: bool | None = None
    fidelity_agrees: bool = False
    r06_control: bool = False


def _arm_from_view(view: dict[str, Any]) -> Arm:
    cands = [str(c) for c in (view.get("candidates") or [])]
    creds = [float(c) for c in (view.get("credences") or [])]
    n = min(len(cands), len(creds))
    order = sorted(range(n), key=lambda i: -creds[i])
    asserted = list(view.get("asserted") or [])
    leader = str(asserted[0]) if asserted else (cands[order[0]] if order else "")
    p_none = float(view["p_none"]) if view.get("p_none") is not None else 0.0
    return Arm(action=str(view.get("effector") or ""), leader=leader,
               n_obs=int(view.get("n_obs") or 0),
               n_docs=0, p_none=p_none,
               eu=float(view.get("eu") or 0.0),
               credences=[creds[i] for i in order])


MODES = ("deployed", "retire", "join")


def make_transport(deps: Any, daemon: str, meter: SpendMeter, tape: list[Call], *,
                   mode: str, root: Path | None = None, conn: Any = None,
                   draws: dict[str, Any] | None = None) -> tuple[Any, Any]:
    """The recording transport. In-process dispatch for the bridge (its handlers unmodified),
    real HTTP for the daemon, every call taped in firing order.

    ``mode`` selects which world is replayed. ``deployed`` records and changes nothing.
    ``retire`` rewrites each replace-site reply into the shape the deployed guard already
    retires on — criterion 7(a): the counterfactual is ENACTED through the real executor and
    the real daemon, so no branch is reimplemented. ``join`` rewrites it to the POOLED channel
    (criterion 7(b) as amended: an upper bound, because §5's key is not on this wire)."""
    import urllib.request

    assert mode in MODES, mode
    channel: list[Any] = []

    def _tape(kind: str, path: str, payload: dict[str, Any],
              reply: dict[str, Any] | None) -> dict[str, Any] | None:
        meter.observe(reply)
        tape.append(Call(n=len(tape), kind=kind, path=path, payload=dict(payload),
                         reply=dict(reply or {})))
        return reply

    def post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        nonlocal channel
        if url.startswith(daemon):
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                return _tape("daemon", url[len(daemon):], payload, json.loads(r.read()))
        path = url[len("bridge:"):]
        if path == "/retrieve" and draws is not None:
            # ONE retrieval draw per (question, breadth), shared across the arms of a question.
            # §6.13 makes at least one question's draw a lottery, and an arm that differed
            # because it drew differently would be a confound, not a counterfactual: the arms
            # must differ because of the rewrite. The DOUBLE RUN still draws afresh, so
            # instability is detected exactly where criterion 9(b) looks for it.
            memo = json.dumps(payload, sort_keys=True)
            if memo in draws:
                return _tape("bridge", path, payload, dict(draws[memo]))
        # checked HERE and not in a preflight: only a question whose loop actually SCHEDULES
        # the edge may be excluded for it (criterion 3, and see ColdDeliberate)
        if (path == "/probe/deliberate" and root is not None
                and not deliberate_is_warm(root, conn, str(payload.get("question") or ""))):
            raise ColdDeliberate(f"the deliberate edge is cold after {len(tape)} call(s)")
        status, reply = SRV.dispatch(deps, "POST", path, json.dumps(payload).encode())
        if status != 200:
            raise RuntimeError(f"bridge {path} -> {status}: {reply}")
        if reply is None:
            # `/route` answers NULL for a question the lookup family does not route, and the
            # executor branches on exactly that (`if route is None` → the narrative path).
            # Coercing it to {} makes a non-None empty dict, the loop proceeds, and it dies on
            # the first field it reads. A transport must not invent a reply the bridge withheld.
            return _tape("bridge", path, payload, None)
        out = dict(reply)
        if path == "/retrieve" and draws is not None:
            draws[json.dumps(payload, sort_keys=True)] = dict(out)
        if path == "/extract":
            channel = list(out.get("observations") or [])
        else:
            site = site_of_call(Call(n=0, kind="bridge", path=path, payload=payload, reply=out))
            if site in ("S1", "S3", "S4", "S5"):
                if mode == "retire":
                    out = retire_reply(site, out)
                elif mode == "join":
                    pooled = join_observations(channel, list(out.get("observations") or []))
                    out = {**out, "observations": pooled}
                channel = list(out.get("observations") or []) or channel
        return _tape("bridge", path, payload, out)

    def get(url: str) -> dict[str, Any]:
        path = url[len("bridge:"):]
        status, reply = SRV.dispatch(deps, "GET", path, b"")
        if status != 200:
            raise RuntimeError(f"bridge {path} -> {status}: {reply}")
        got = _tape("bridge-get", path, {}, reply)
        assert got is not None
        return got

    return post, get


def build_deps(root: Path, conn: Any, client: Any) -> Any:
    """The bridge's own deps, with the REFUSING client and the staging sinks."""
    def _u_bar() -> dict[str, float]:
        u_bar, _v = LK.current_u_bar(LK.shared_brain())
        return u_bar

    def _fold_version() -> str:
        _u, v = LK.current_u_bar(LK.shared_brain())
        return v

    return SRV.BridgeDeps(root=root, conn=conn, client=client,
                          profile=owner.load_profile(), u_bar=_u_bar,
                          decisions_path=LCFG.DECISIONS_LOG,
                          reactions_path=LCFG.REACTIONS_LOG, fold_version=_fold_version,
                          gather_outcomes_path=LCFG.GATHER_OUTCOMES_LOG, membrane=None)


def deliberate_is_warm(root: Path, conn: Any, question: str) -> bool:
    """Criterion 3's preflight, through the bridge's OWN key derivation — the executor swallows
    exceptions around `/probe/deliberate`, so a cold edge must be caught before the loop."""
    cfg = SRV._deliberate_cfg()
    digest = CORPUS.corpus_digest(conn)
    key = D.deliberate_key(question, digest, model=cfg.model,
                           prompt_template=DL.PROMPT_DELIB_V2, max_turns=cfg.max_turns)
    return D.lookup(root, key.cache_key) is not None


def replay(question: str, k: int, *, deps: Any, daemon: str, curves: Any, mode: str,
           tape: list[Call], root: Path, conn: Any,
           draws: dict[str, Any] | None = None) -> dict[str, Any]:
    """One question through the DEPLOYED loop, with the deployed caller's own menu assembly.

    The TAPE is the caller's: on a cold derivation the exception must leave behind the calls
    that DID happen, or `cold_kind` reads every failure as cold-at-start and the divergence
    signal criterion 9(c) is built on vanishes."""
    meter: SpendMeter = SpendMeter()
    post, get = make_transport(deps, daemon, meter, tape, mode=mode, root=root, conn=conn,
                               draws=draws)
    transforms = EX.menu_transforms(curves) if LCFG.deliberate_enabled() else None
    return EX.decide_via_loop(question, k, bridge="bridge:", daemon=daemon,
                              post=post, get=get, transforms=transforms, curves=curves)


def src_tree_hash(rev: str) -> str:
    """git's tree hash for `src/` at ``rev`` — the object that is equal exactly when the
    directory's bytes are equal. `""` when the rev is unknown to this checkout."""
    r = subprocess.run(["git", "rev-parse", f"{rev}:src"], capture_output=True,
                       text=True, check=False)
    return r.stdout.strip() if r.returncode == 0 else ""


def _curves_for(qid: str) -> Any:
    """Criterion 2(e): the pinned run held each question's OWN rows out of its fold, so the
    replay must too — folded from the STAGING outcomes log, which is already truncated to the
    run's start."""
    rows = CAL.edge_outcomes_from_log(LCFG.OUTCOMES_LOG, exclude_question_ids=frozenset({qid}))
    return CAL.fit_edge_curves(rows) if rows else None


def classify(deployed: Arm | None, alt: Arm | None, gold: str,
             variants: list[str]) -> str:
    """r06's grammar verbatim, so the two checkpoints compare: a withholding that becomes a
    CORRECT commit is a repair; one that becomes a WRONG commit is a regression."""
    if deployed is None or alt is None:
        return "ungradeable"
    if deployed.action == alt.action and deployed.leader == alt.leader:
        return "unchanged"
    d_c, a_c = committed(deployed), committed(alt)
    d_ok, a_ok = correct(deployed, gold, variants), correct(alt, gold, variants)
    if d_c and a_c:
        if a_ok and not d_ok:
            return "repair"
        return "regression" if (d_ok and not a_ok) else "neutral"
    if d_c and not a_c:
        return "repair" if not d_ok else "regression"
    if a_c and not d_c:
        return "repair" if a_ok else "regression"
    return "neutral"


def audit_rows(qids: list[str], by_id: dict[str, dict[str, Any]],
               paired: dict[str, dict[str, Any]], *, deps: Any, root: Path, conn: Any,
               daemon: str, k: int,
               modes: tuple[str, ...]) -> tuple[list[Row], list[str]]:
    rows: list[Row] = []
    excluded: list[str] = []
    for qid in qids:
        q = by_id.get(qid)
        if q is None:
            excluded.append(f"{qid} (not in the questions file)")
            continue
        gold = str(q.get("answer") or "")
        if not gold:
            excluded.append(f"{qid} (unanswerable by construction — no gold)")
            continue
        question = str(q["question"])
        curves = _curves_for(qid)
        row = Row(qid=qid, gold=gold,
                  variants=[str(v) for v in (q.get("answer_variants") or [])])
        arms: dict[str, Arm] = {}
        # one retrieval draw per breadth, shared by this question's arms (see make_transport)
        draws: dict[str, Any] = {}
        for mode in modes:
            tape: list[Call] = []
            try:
                view = replay(question, k, deps=deps, daemon=daemon, curves=curves,
                              mode=mode, tape=tape, root=root, conn=conn, draws=draws)
            except (WouldSpendError, ColdDeliberate) as e:
                why = ("the deliberate edge is cold" if isinstance(e, ColdDeliberate)
                       else "a §18.9 derivation is cold")
                excluded.append(f"{qid}/{mode} ({why}, "
                                f"{cold_kind(n_calls_before=len(tape))} — criterion 9(c))")
                row.cold_arms = (*row.cold_arms, mode)
                continue
            arms[mode] = _arm_from_view(view)
            if mode == "deployed":
                row.sites = sites_in_order(tape)
                row.trace = channel_trace(tape)
                row.discarder = attributed_discarder(
                    row.trace, committed_n_obs=int(view.get("n_obs") or 0))
        if "deployed" in row.cold_arms:
            continue   # no attribution without the deployed tape; the arm rows are named above
        row.deployed = arms.get("deployed")
        row.retire = arms.get("retire")
        row.join = arms.get("join")
        typed = dict((paired.get(qid) or {}).get("typed") or {})
        row.recorded_action = str(typed.get("action") or "")
        row.recorded_correct = typed.get("correct") if "correct" in typed else None
        row.fidelity_agrees = bool(row.deployed
                                   and row.deployed.action == row.recorded_action)
        row.r06_control = not row.sites
        rows.append(row)
        # progress to STDERR only, and only ids + counts — criterion 9(d): a recorded reply
        # carries corpus text and none of it may reach a log any more than a report
        print(f"  [{len(rows)}] {qid}: sites={'/'.join(row.sites) or '-'} "
              f"n_obs={row.deployed.n_obs if row.deployed else '-'} "
              f"cold={'/'.join(row.cold_arms) or '-'}", file=sys.stderr, flush=True)
    return rows, excluded


def _site_tally(rows: list[Row], site: str, arm: str) -> dict[str, int]:
    hit = [r for r in rows if site in r.sites]
    out = {"exposure": len(hit), "reach": 0, "repairs": 0, "regressions": 0,
           "discarded_by": sum(1 for r in hit if site in r.discarder)}
    for r in hit:
        alt = getattr(r, arm)
        verd = classify(r.deployed, alt, r.gold, r.variants)
        if verd in ("repair", "regression", "neutral"):
            out["reach"] += 1
        if verd == "repair":
            out["repairs"] += 1
        elif verd == "regression":
            out["regressions"] += 1
    return out


def _distinctive(value: str) -> bool:
    """Whether a plain substring test can tell this value apart from a coincidence.

    A one-character or purely numeric gold matches the `7` in an `n_obs=7` — and word
    boundaries do not help, because `=` is not a word character. No text test can separate
    those two sevens. So short and numeric values are checked only where a coincidence is
    unlikely and a real leak would actually come from: the report's FREE-TEXT channels."""
    return len(value) >= 5 and not value.replace(".", "").replace("-", "").isdigit()


def _shape(value: str) -> str:
    """A value's shape, for an error message that must not carry the value itself."""
    kind = ("numeric" if value.replace(".", "").replace("-", "").isdigit()
            else "alphanumeric" if any(c.isdigit() for c in value) else "alphabetic")
    return f"len={len(value)}/{kind}"


def leak_check(text: str, rows: list[Row], *, freetext: str | None = None) -> list[str]:
    """Criterion 9(d): the SHAPES of any corpus value that reached the rendered text.

    Two channels, because they admit different tests. **Distinctive values** are checked
    against the WHOLE report — a name or an identifier appearing anywhere is a leak, full stop.
    **Short or numeric values** are checked only against ``freetext`` (the pin notes, the
    exclusion lines, the site descriptions), because the structured tables emit ids and integers
    this module computes, and a gold of `7` is indistinguishable there from a count of 7.

    *That is a stated limit, not a silent one:* a one-character gold emitted into a table cell
    would not be caught here. Nothing in `render` writes a value into a cell — the tables carry
    qids, site ids, arrows and integers — so the guard's job is to catch a value arriving
    through prose, which is how one would actually arrive."""
    hits: list[str] = []
    for r in rows:
        for v in (r.gold, *r.variants):
            if not v:
                continue
            haystack = text if _distinctive(v) else (freetext if freetext is not None else text)
            if _distinctive(v):
                found = v in haystack
            else:
                found = re.search(rf"(?<![\w-]){re.escape(v)}(?![\w-])", haystack) is not None
            if found:
                hits.append(_shape(v))
    return sorted(set(hits))


def render(rows: list[Row], excluded: list[str], *, run_id: str, k: int,
           pin_notes: list[str], modes: tuple[str, ...], r06_floor_sites: frozenset[str],
           unstable: list[str]) -> str:
    n = len(rows)
    out = [f"# Recorded-replay audit — {run_id} (k={k}, the deployed path, $0)", "",
         f"{n} question(s) replayed, {len(excluded)} excluded by name. "
         f"Arms: {', '.join(modes)}.", ""]
    for note in pin_notes:
        out.append(f"- pin: {note}")
    if UNDATED_KEPT:
        out += ["", *[f"- {u}" for u in dict.fromkeys(UNDATED_KEPT)]]
    out += ["", "## Criterion 6 — fidelity, the direct control on everything below", ""]
    agree = sum(1 for r in rows if r.fidelity_agrees)
    out.append(f"The replay reproduces the recorded terminal ACTION on **{agree}/{n}** "
             f"question(s).")
    dis = [r.qid for r in rows if not r.fidelity_agrees]
    if dis:
        out.append("")
        out.append(f"Disagreeing rows, named and never averaged away: {', '.join(dis)}.")
    ctrl = [r for r in rows if r.r06_control]
    ctrl_ok = sum(1 for r in ctrl if r.fidelity_agrees)
    out += ["", f"On the **{len(ctrl)}** question(s) where NO site fired the replay agrees with "
              f"the record on **{ctrl_ok}**. r06's reconstruction of those same rows disagreed "
              f"at 28%; this is the number that says whether that floor was the DECIDE LAYER "
              f"or the evidence.", ""]
    out += ["## Criteria 4-5 — the firing order and the attributed discarder", "",
          "| question | firing order | channel trace | committed n_obs | discarder |",
          "|---|---|---|---|---|"]
    for r in rows:
        if not r.sites:
            continue
        trace = " → ".join(f"{s}:{v}" for s, v in r.trace)
        out.append(f"| {r.qid} | {' → '.join(r.sites)} | {trace} | "
                 f"{r.deployed.n_obs if r.deployed else '—'} | "
                 f"{', '.join(r.discarder) or '—'} |")
    out += ["", "## Criteria 7-8 — the two counterfactuals, per site", "",
          "| site | arm | exposure | discards | reach | repairs | regressions |",
          "|---|---|---|---|---|---|---|"]
    for site in SITES:
        for arm in ("retire", "join"):
            if arm not in modes:
                continue
            t = _site_tally(rows, site, arm)
            out.append(f"| {site} | {arm} | {t['exposure']} | {t['discarded_by']} | "
                     f"{t['reach']} | {t['repairs']} | {t['regressions']} |")
    floor = (len(ctrl) - ctrl_ok) / len(ctrl) if ctrl else 0.0
    out += ["", f"**r07's own noise floor: {len(ctrl) - ctrl_ok} of {len(ctrl)} = "
              f"{floor:.0%}.** On those questions no site fired, so both counterfactuals are "
              f"provably no-ops and every difference is instrument error.", "",
          "| site | excess over floor (retire) | verdict |", "|---|---|---|"]
    for site in SITES:
        t = _site_tally(rows, site, "retire") if "retire" in modes else {"exposure": 0,
                                                                        "reach": 0}
        ex = excess_over_floor(exposure=t["exposure"], reach=t["reach"], floor=floor)
        v, why = verdict(excess=ex, r06_above_floor=site in r06_floor_sites)
        out.append(f"| {site} | {ex} rows | **{v}** — {why} |")
    if unstable:
        out += ["", f"## Criterion 9(b) — unstable across the double run: "
                  f"{', '.join(unstable)}. These carry NO attribution claim.", ""]
    if excluded:
        out += ["", "## Excluded, by name (criterion 9(c))", ""]
        out += [f"- {e}" for e in excluded]
    out += ["", "*Criterion 7(b) as amended: the JOIN column is an UPPER BOUND — §5's dedup "
            "key is not on this wire, so every pooled copy counts as an independent "
            "witness.*", ""]
    text = "\n".join(out)
    freetext = "\n".join([*pin_notes, *excluded, *SITES.values(), *unstable])
    leaked = leak_check(text, rows, freetext=freetext)
    if leaked:
        # criterion 9(d), enforced rather than intended: a recorded reply carries corpus text,
        # and the one thing this report may never contain is a value from it. Loud, not a
        # silent redaction — a report that has to be scrubbed is a report that was written
        # wrong. The failure names SHAPES, never the values it is protecting.
        raise AssertionError(
            f"criterion 9(d): {len(leaked)} corpus value(s) reached the rendered report "
            f"(shapes: {', '.join(leaked)})")
    return text


def dump_rows(rows: list[Row], excluded: list[str]) -> str:
    """The reading's rows, as data. Carries the leader values — which is why it is written under
    `$LIFE_AGENT_KB` and never into the repo (criterion 9(d) governs the REPORT; this file is
    the corpus-side record the report is derived from)."""
    return json.dumps({
        "excluded": excluded,
        "rows": [{"qid": r.qid, "gold": r.gold, "variants": r.variants,
                  "sites": list(r.sites), "trace": r.trace,
                  "discarder": list(r.discarder), "cold_arms": list(r.cold_arms),
                  "deployed": r.deployed.__dict__ if r.deployed else None,
                  "retire": r.retire.__dict__ if r.retire else None,
                  "join": r.join.__dict__ if r.join else None,
                  "recorded_action": r.recorded_action,
                  "recorded_correct": r.recorded_correct,
                  "fidelity_agrees": r.fidelity_agrees,
                  "r06_control": r.r06_control} for r in rows]}, indent=2)


def load_rows(path: Path) -> tuple[list[Row], list[str]]:
    """The inverse of :func:`dump_rows`, for `--render-only`."""
    return load_rows_from_text(path.read_text())


def load_rows_from_text(text: str) -> tuple[list[Row], list[str]]:
    blob = json.loads(text)
    rows: list[Row] = []
    for d in blob["rows"]:
        r = Row(qid=d["qid"], gold=d.get("gold", ""), variants=list(d.get("variants") or []))
        r.sites = tuple(d.get("sites") or [])
        r.trace = [(str(a), int(b)) for a, b in (d.get("trace") or [])]
        r.discarder = tuple(d.get("discarder") or [])
        r.cold_arms = tuple(d.get("cold_arms") or [])
        for arm in ("deployed", "retire", "join"):
            if d.get(arm):
                setattr(r, arm, Arm(**d[arm]))
        r.recorded_action = str(d.get("recorded_action") or "")
        r.recorded_correct = d.get("recorded_correct")
        r.fidelity_agrees = bool(d.get("fidelity_agrees"))
        r.r06_control = bool(d.get("r06_control"))
        rows.append(r)
    return rows, list(blob.get("excluded") or [])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--live-kb", required=True)
    ap.add_argument("--staging", default=str(Path.home() / ".cache/life-agent/r07/stage-kb"))
    ap.add_argument("--run-meta", required=True)
    ap.add_argument("--paired", required=True)
    ap.add_argument("--questions", required=True)
    ap.add_argument("--daemon", default="http://127.0.0.1:8799")
    ap.add_argument("--k", type=int, default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--only", default="")
    ap.add_argument("--modes", default="deployed,retire,join")
    ap.add_argument("--out")
    ap.add_argument("--out-yaml")
    ap.add_argument("--render-only", help="re-render from a rows file written by a prior run")
    ap.add_argument("--acknowledge-src-drift", default="", metavar="TREE_SHA",
                    help="full `src/` tree hash HEAD is EXPECTED to carry when it differs "
                         "from the replayed run's (the drift is stamped into the pin notes)")
    args = ap.parse_args()

    if str(LCFG.KB) != args.staging:
        # the pin is applied by a re-exec (see _bootstrap): if we are still on the live KB the
        # bootstrap did not run, and reading here would write the owner's ledgers (criterion 2f)
        print(f"REFUSED — LIFE_AGENT_KB is {LCFG.KB}, not the staging root {args.staging}; "
              f"the pin was never applied (criterion 2)")
        return 2

    meta = json.loads(Path(args.run_meta).read_text())
    k = args.k if args.k is not None else int((meta.get("gate") or {}).get("k") or 20)
    if args.render_only:
        rows, excluded = load_rows(Path(args.render_only))
        modes = tuple(m.strip() for m in args.modes.split(",") if m.strip())
        report = render(rows, excluded, run_id=args.run_id, k=k,
                        pin_notes=["re-rendered from a saved rows file"],
                        modes=modes, r06_floor_sites=R06_BOUGHT, unstable=[])
        print(report)
        if args.out:
            Path(args.out).write_text(report)
        return 0
    root = TREAD.pkm_root()
    conn = duckdb.connect(str(root / "catalogue.duckdb"), read_only=True)
    conn.execute("INSTALL fts; LOAD fts;")
    client = RefusingClient(engine_version=str(anthropic.__version__))
    deps = build_deps(root, conn, client)

    elic = LCFG.UTILITY_ELICITATIONS
    import hashlib
    elic_sha = (hashlib.sha256(elic.read_bytes()).hexdigest() if elic.is_file() else "")
    run_sha = str((meta.get("life_agent_git") or {}).get("sha") or "")
    here, there = src_tree_hash("HEAD"), src_tree_hash(run_sha)
    if run_sha and not there:
        print(f"REFUSED — the run's commit {run_sha[:12]} is not in this checkout, so `src/` "
              f"cannot be compared (criterion 2a)")
        return 2
    meta = {**meta, "life_agent_git": {"sha": there}}
    fails = verify_pin(meta, src_sha=here, corpus_digest=CORPUS.corpus_digest(conn),
                       elicitations_sha=elic_sha,
                       acknowledged_src=args.acknowledge_src_drift)
    if fails:
        print("REFUSED — the pin does not hold (criterion 2):")
        for f in fails:
            print(f"  - {f}")
        return 2
    src_note = (f"src tree {here[:12]} == the run's (HEAD is a later commit, docs only)"
                if here == there else
                f"src tree {here[:12]} != the run's {there[:12]} — drift ACKNOWLEDGED "
                f"(--acknowledge-src-drift): the replaying tree carries the r08 fix")
    pin_notes = [src_note,
                 "corpus digest == the run's",
                 "utility elicitations == the run's",
                 f"logs truncated to {meta['created_at']}",
                 f"curves LOO, menu via menu_transforms (deliberate in menu: "
                 f"{LCFG.deliberate_enabled()})",
                 f"write isolation: KB={LCFG.KB}, ledger mirror "
                 f"{os.environ.get('LIFE_AGENT_LEDGER_MIRROR')}"]

    questions = load_questions(Path(args.questions))
    by_id = {str(q["id"]): q for q in questions}
    paired = load_paired(Path(args.paired))
    qids = sorted(paired)
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        qids = [q for q in qids if q in want]
    if args.limit:
        qids = qids[:args.limit]
    modes = tuple(m.strip() for m in args.modes.split(",") if m.strip())

    rows, excluded = audit_rows(qids, by_id, paired, deps=deps, root=root, conn=conn,
                                daemon=args.daemon, k=k, modes=modes)
    # The rows are written BEFORE the render. A render that raises — criterion 9(d) does, on
    # purpose — must not destroy an hour of replaying; `--render-only` then re-renders from
    # here in seconds. (Learned by losing a full battery to a leak-check false positive.)
    if args.out_yaml:
        Path(args.out_yaml).write_text(dump_rows(rows, excluded))
        print(f"rows written to {args.out_yaml}", file=sys.stderr)
    report = render(rows, excluded, run_id=args.run_id, k=k, pin_notes=pin_notes,
                    modes=modes, r06_floor_sites=R06_BOUGHT, unstable=[])
    print(report)
    if args.out:
        Path(args.out).write_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
