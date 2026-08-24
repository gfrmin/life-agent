"""The lookup family — Ask v0's first typed question family (foundations §4).

V is a point fact ("what is my ID?", "when is the appointment?"). The pipeline, every
stage on the ledger (system-design §3) and every modelling choice stated:

    route      cached local-model verdict: is this a typed lookup? (§4.1; misroutes
               fall to the narrative path — the §9 no-hard-zeros routing)
    observe    per retrieval hit, a question-parameterised grounded extraction (§18.9,
               cached on (question, chunk content); an ungrounded quote is recorded and
               treated as indeterminate — the grounding gate is error-model surgery)
    posterior  noisy-channel mixture over candidate values + an explicit
               none-of-the-retrieved atom, composed under §2's lineage rule: the
               likelihood product is TEMPERED for shared instrument identity (one
               extractor produced every observation) and shared evidence ancestry
               (chunks of one document corroborate less than two documents) — stated
               exponents below, conditioned through the credence skin
    respond    optimise over {report, hedge, ask_clarify, abstain} under the §4.4
               utility posterior's mean (the collapse theorem) — ask-about-U is
               deliberately absent (passive learning until the governor)
    render     deterministic templates from one grammar table (no LLM — the strongest
               conformance: the render IS the claim set), citations per observation
    decide     the decision logged (§8 — no EU decision is ever made unlogged)

Stated channel parameters (each a prior choice calibration will move — §2, §14):
``_A_ALTERNATIVES`` (effective wrong-value alternatives), ``_RHO_PRIOR_*`` (the
grounded-extraction reliability Beta prior, moved by audit outcomes — the
``reliability_categorical`` rho prior the engine integrates exactly), ``_ORACLE_P``
(the owner-as-oracle prior for pricing ask_clarify), the declared source-authority
classes (§4.1's v0 lattice), and the §4.1 covariate factors (``_A_SUBJECT_*`` /
``_TIME_HALF_LIFE_YEARS`` / ``_A_TIME_UNKNOWN`` — doc_subject and doc_date enter
a_i: a document about someone else, or from the wrong era, supports a different
variable; construct validity, not noise).
"""
from __future__ import annotations

import atexit
import dataclasses
import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from life_agent.core import config
from life_agent.core import decisions as DEC
from life_agent.core import derivations as D
from life_agent.core import instrument as INSTR
from life_agent.core import matching as MATCH
from life_agent.core import outcomes as O
from life_agent.core import reactions as R
from life_agent.core import seam as SEAM
from life_agent.core import utility as UT
from life_agent.core.brain import Brain
from life_agent.core.dates import parse_date as _parse_date
from life_agent.core.decide import u_assert

# The route + extract instrument model (local Ollama deprecated 2026-08-17 — owner
# directive, §14-registered; both verdicts are cached, so call counts are bounded by
# distinct questions x distinct chunks, and warm replays cost $0).
LOOKUP_MODEL = INSTR.INSTRUMENT_MODEL

ROUTE_PROMPT = """\
Classify this question in two steps.

STEP 1 — is it NOT a lookup? Answer {"lookup": false} if the question asks for ANY of:
- a list or set (plural asks: "which banks", "what are my balances", "who are all", "what's
  next on my list", "list every ...");
- an aggregate the READER must compute over several documents ("in total across all my
  X", "how much did I spend last year") — but a total that is itself a listed figure in
  one document ("total prize money listed for horse X", "total number of issued shares
  for company Y") is a single value, NOT an aggregate;
- a summary, overview, comparison, or explanation ("summarise", "overview", "compare",
  "why", "explain", "what did X ask and what did I answer");
- MULTIPLE separate values at once ("lender, amount, and end date"; "when and where";
  "what is X and what is its number") — two asks joined by "and" are two values.

STEP 2 — otherwise it IS a lookup: exactly ONE specific value that could be read off a
document in the corpus — personal records and emails, but equally papers, theses, books,
lecture notes, spreadsheets, code, and data files: a number, ID, date, name, place,
address, amount, term, an abbreviation's expansion, a citation, a formula, a notation, a
statistic, or similar point fact. "What does X stand for", "what is the formula for X",
"which text is cited for X", "how many X in year Y", "what city/company/technique is
described as ..." are lookups. A value conventionally written as one unit — a year range
(1924-2000), a volume(issue) like 358(14), "N units at price P" — is ONE value.

If it IS a lookup, also classify the value's persistence. TIME-INDEXED means the value
is a current state that can change over a life: an address, phone number, employer,
salary, balance, status, expiry, coverage figure. NOT time-indexed means the value is
permanent or historical once set: a birth date, a national ID, the date an event
happened, a published figure, a definition.

QUESTION: {question}

Reply with JSON only:
{"lookup": true, "construct": "<3-8 words naming the value asked for>", \
"time_indexed": true|false}
or {"lookup": false}
"""

ROUTE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["lookup"],
    "properties": {
        "lookup": {"type": "boolean"},
        "construct": {"type": "string"},
        "time_indexed": {"type": "boolean"},
    },
}

EXTRACT_PROMPT = """\
You are extracting ONE value from a document excerpt, if it is present.

QUESTION: {question}

EXCERPT:
{chunk}

Reply {"found": true, ...} ONLY if the excerpt contains the specific value the
question asks for. Strict rules:
- NEVER extract a form label, field name, or heading (e.g. "Any other status:") — only
  an actual filled-in value.
- If the excerpt shows a value of the right KIND but explicitly for a different person,
  a different account, or a different context than the question asks, reply found false.
- If no such value is present in the excerpt, reply found false. Report what the
  excerpt shows — whether the document itself is trustworthy is judged downstream.

If the answering value is present, reply with JSON:
{"found": true, "value": "<the value, concise>", \
"quote": "<verbatim text copied from the excerpt containing the value>"}
Otherwise reply: {"found": false}
"""

EXTRACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["found"],
    "properties": {
        "found": {"type": "boolean"},
        "value": {"type": "string"},
        "quote": {"type": "string"},
    },
}

CONFIRM_PROMPT = """\
You are checking whether a document excerpt independently confirms a proposed value.

QUESTION: {question}
PROPOSED VALUE: {value}

EXCERPT:
{chunk}

Reply {"confirms": true, ...} ONLY if the excerpt itself states this value as the
current answer to the question. Strict rules:
- The excerpt must assert the value for the SAME person, account, and context the
  question asks about; a matching value explicitly for someone or something else is
  not a confirmation — reply confirms false.
- A value shown as superseded, corrected, cancelled or replaced ("was", "previous",
  "changed to ...") is not a confirmation — reply confirms false.
- A bare form label or heading, or the value appearing only inside a different,
  unrelated figure, is not a confirmation — reply confirms false.

If the excerpt confirms the value, reply with JSON:
{"confirms": true, \
"quote": "<verbatim text copied from the excerpt containing the value>"}
Otherwise reply: {"confirms": false}
"""

CONFIRM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["confirms"],
    "properties": {
        "confirms": {"type": "boolean"},
        "quote": {"type": "string"},
    },
}

# --- stated channel parameters (priors; calibration moves them — §2/§14) ---------------
_A_ALTERNATIVES = 10.0   # effective number of wrong values a misreport spreads over
# (the §4.2 ancestry/model tempering exponents are RETIRED — the exact group-noisy-channel
#  + continuous rho-latent the `reliability_categorical` integrates replaces the host temper.)
# The reliability prior for "this grounded observation's value IS the true V" —
# end-to-end, construct validity included (a grounded form label or another person's
# number is a wrong observation, not a misread). The first eval run refuted the original
# Beta(17,3)=0.85 quote-fidelity prior for THIS construct (report accuracy 0/7): the
# prior is now wide, and the eval's per-candidate claim outcomes condition it (see
# extractor_reliability) — the instrument earns trust from evidence, never from fiat.
_RHO_PRIOR_A = 4.0       # Beta(4,4): mean 0.5, wide
_RHO_PRIOR_B = 4.0
# The none-of-the-retrieved prior mass: the stated complement of an unproven extraction
# channel — candidates share the rest uniformly. (Was uniform over K+1; the first eval
# showed agreeing junk burying NONE at 0.98 credence.)
_P_NONE_PRIOR = 0.5
_ORACLE_P = 0.9          # owner-as-oracle prior mean for pricing ask_clarify (§4.4)
_PROB_EPS = 1e-12
# Candidate identity: a numeric identifier this many digits or longer is keyed on its
# significant digits (leading zeros stripped) so OCR/format variants of ONE number collapse
# instead of splitting posterior mass. Below it, identity stays the whitespace+case norm.
_CANON_MIN_DIGITS = 5
# The §4.2 competition term at the source (foundations §14, registered 2026-08-17): a
# quote window carrying a distinct same-shape value beside the extracted one halves the
# probability the extractor PICKED the true one — an r-shaped (report-correctness)
# covariate, never an A-shaped one (the competitor concentrates the miss, it does not
# grow the wrong-value universe). Cap FROZEN at 1 (binary 0.5) by the off-gate sweep
# (temper-audit-20260817: D3/cap1 — weakest temper that flips the 3/3 run-8 wrongs,
# minimal collateral 18/56) so a competed observation stays a live sub-bar lead the VOI
# ladder can rescue instead of being erased toward the prior.
_COMPETITION_CAP = 1


def competition_factor(n_competing: int) -> float:
    """Per-observation reliability multiplier for ``n_competing`` same-shape competitors
    in the extractor's quote window (``matching.quote_scoped_competitors``): 1 or 1/2."""
    return 1.0 / (1.0 + min(max(n_competing, 0), _COMPETITION_CAP))

# §4.1's v0 source-authority lattice: P(document's assertion = W's value | doc class),
# a declared prior keyed on what is observable (origin path), calibrated later from
# outcomes (open question: per-sender vs per-kind).
_AUTHORITY_CLASSES: tuple[tuple[tuple[str, ...], str, float], ...] = (
    ((".pdf", ".docx", ".doc", ".odt"), "document", 0.95),
    ((".eml",), "email", 0.90),
    ((".md", ".txt", ".org"), "note", 0.80),
)
_AUTHORITY_MAIL_MARKERS = ("/mail/", "/cur/", "/new/")
_AUTHORITY_DEFAULT = ("other", 0.85)

# §4.1's covariates on a_i (stated priors, calibrated later from outcomes). The second
# eval run's remaining confident-wrong reports were exactly these two channels: documents
# about someone else agreeing on their value, and stale documents agreeing on a
# superseded one — construct validity, entering the likelihood, never a rank heuristic.
_A_SUBJECT_OTHER = 0.05      # P(a doc about someone else asserts the owner's value)
_P_OWNER_GIVEN_INDET = 0.5   # P(the doc is about the owner | subject indeterminate)
_TIME_HALF_LIFE_YEARS = 5.0  # current-state facts: P(assertion still current | doc age)
_A_TIME_UNKNOWN = 0.6        # undated/underived doc date under a time-indexed construct

# The response actions, in the optimise action-space order. Names are the
# decisions.ACTIONS vocabulary; ask-about-U is deliberately absent (§4.4).
_ACTION_ORDER: tuple[str, ...] = DEC.LOOKUP_ACTION_ORDER

# Closed abstention reasons (the credence grammar — interaction contract).
# The reason must be the TRUE one. These are not interchangeable labels: DISPERSED is a
# statement about a posterior that existed and lost the EU argmax; NO_OBSERVATIONS is the
# absence of any posterior at all (nothing was grounded, so nothing was dispersed);
# UNAVAILABLE is a statement about the corpus, not about belief — the evidence is not in
# this machine's catalogue, so no amount of thinking here would have found it.
REASON_DISPERSED = "dispersed posterior"
REASON_NO_OBSERVATIONS = "no admitted evidence"
REASON_UNAVAILABLE = "corpus unavailable"

# One grammar table for every rendered string (drift-gated; interaction contract).
# Credences render at three decimals: two rounded 0.997 up to "1.00" on the first live
# answer — a certainty the posterior never asserted (presentation error, §3).
GRAMMAR: dict[str, str] = {
    "report": "{value} — credence {p:.3f} {cites}",
    # the time-scoped assertion (scoped-claims design): a TRUE claim about the record when the
    # current value is uncertain. Names the currency gap and the deferred upgrade, never silent.
    "report_scoped": ("As of {as_of}: {value} — credence {p:.3f} {cites}\n"
                      "  — the most recent record I found; I may be missing a newer one. "
                      "A confirmed current figure would need a costlier check."),
    "hedge": "Unresolved — candidates: {alts}",
    "ask_clarify": "Worth asking you directly — the evidence does not settle it: {alts}",
    "abstain": "No answer asserted ({reason}).",
    # abstain still shows the candidate(s) it withheld below the assert threshold — the
    # held-back "thinking" that makes the decision verdictable (is that value right?) rather
    # than a blind "should you have answered?". Used when the posterior held >=1 candidate.
    "abstain_withheld": "No answer asserted ({reason}). Held back: {alts}",
    "footer": ("lookup: {n_hits} hits → {n_obs} grounded observations"
               " · {n_ind} indeterminate · none-of-retrieved {p_none:.3f}"
               " · decision {action} (EU {eu:.2f})"),
    "fallthrough": "(lookup: {reason} — narrative path)",
}


@dataclass(frozen=True)
class Route:
    """The cached route verdict for a typed lookup (§4.1)."""

    construct: str
    time_indexed: bool


@dataclass(frozen=True)
class HitCovariates:
    """Read-side §4.1 covariates per hit artifact, keyed on artifact_cache_key.

    Carried OUTSIDE the hit dicts so the retrieval-set bytes (and every key hashed
    from them) stay untouched. Absent key = the channel was not projected for that
    hit (factor 1.0). ``subject_state`` values are the owner-filter partition states
    ("owner" | "unclear" | "underived" | "other" | "generic"); ``doc_date`` is an
    ISO date, or None for a projected-but-unknown date (undated/underived)."""

    subject_state: Mapping[str, str] = field(default_factory=dict)
    doc_date: Mapping[str, str | None] = field(default_factory=dict)


def subject_factor(state: str | None) -> float:
    """The doc_subject covariate on a_i. None = no covariate (not an owner-scoped
    question, or not projected). A state outside the partition raises — junk from
    the annotation seam must surface, not silently weight evidence."""
    if state is None or state == "owner":
        return 1.0
    if state in ("other", "generic"):
        return _A_SUBJECT_OTHER
    if state in ("unclear", "underived"):
        return (_P_OWNER_GIVEN_INDET
                + (1.0 - _P_OWNER_GIVEN_INDET) * _A_SUBJECT_OTHER)
    raise ValueError(f"subject covariate outside the partition: {state!r}")


def time_factor(date_iso: str | None, *, time_indexed: bool,
                today: date | None = None,
                half_life_years: float = _TIME_HALF_LIFE_YEARS) -> float:
    """The doc_date covariate on a_i: for a time-indexed construct, the probability a
    document's assertion is still current decays with document age at the construct's
    ``half_life_years`` (the per-construct volatility prior; a permanent construct passes a
    near-infinite half-life ⇒ no decay). ``date_iso`` None = projected but unknown
    (undated/underived) — the stated marginal attenuation. Future-dated documents clamp to 1.0."""
    if not time_indexed:
        return 1.0
    if date_iso is None:
        return _A_TIME_UNKNOWN
    now = today if today is not None else datetime.now(UTC).date()
    age_years = max((now - date.fromisoformat(date_iso)).days, 0) / 365.25
    return float(0.5 ** (age_years / half_life_years))


@dataclass(frozen=True)
class Observation:
    """One grounded extraction over one retrieval hit (§4.1's o_i)."""

    card_n: int                  # the source card number, for citations
    artifact_cache_key: str      # the hit's artifact (the ancestry-group key)
    obs_cache_key: str           # this observation's §18.9 key (answer lineage)
    value_raw: str
    value_norm: str
    quote: str
    authority_class: str
    authority: float
    subject_factor: float = 1.0  # §4.1 doc_subject covariate on a_i
    time_factor: float = 1.0     # §4.1 doc_date covariate on a_i
    doc_date: str | None = None  # the supporting doc's projected ISO date (the scoped claim's
    #                              as-of; None = undated/underived). Does not enter obs_cache_key
    #                              (that is the extraction key) — a read-side covariate like the
    #                              factors above.
    n_competing: int = 0         # distinct same-shape values in the quote window (§4.2's
    #                              competition term, matching.quote_scoped_competitors) —
    #                              a read-side covariate like doc_date, never in the key
    competition_factor: float = 1.0  # the frozen n→factor map applied (1 or 1/2)


@dataclass(frozen=True)
class LookupResult:
    """The family's full output — consumed by ask.py (render) and run_eval (grading)."""

    question: str
    construct: str
    action: str                          # one of _ACTION_ORDER
    eu: float
    candidates: tuple[str, ...]          # display values, posterior order
    credences: tuple[float, ...]         # aligned with candidates
    p_none: float
    observations: tuple[Observation, ...]
    n_hits: int
    n_indeterminate: int
    utility_fold_version: str
    answer_cache_key: str
    rendered: str
    # report_scoped inputs (scoped-claims design), recorded whether or not scoped was chosen:
    # the freshest-record value + its as-of date, and p_attested (the record's recency-off
    # support). The render uses them only when action == "report_scoped".
    as_of: str | None = None
    scoped_value: str | None = None
    scoped_p: float = 0.0
    # the route's time-indexing of the construct (a volatile attribute decays with document age;
    # a permanent one does not). Surfaced so a downstream edge (the joint extractor) can apply the
    # same recency model the single-pass path applies via its per-hit covariates.
    time_indexed: bool = False


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _norm_value(value: str) -> str:
    return " ".join(value.split()).casefold()


# Calendar-date parsing lives in core.dates (the canonical normaliser, shared with the matcher);
# _candidate_key keys a parseable date on its ISO form so format variants collapse to one candidate.


def _candidate_key(value: str) -> str:
    """The identity key for candidate de-duplication (§4.2). A value that parses to an
    unambiguous calendar date keys on that date, so the same date written in different
    formats collapses (q-003). Otherwise a numeric identifier (>= _CANON_MIN_DIGITS digits)
    keys on its digit-string with leading zeros stripped: OCR/format variants of one number
    — a dropped/added leading zero, embedded spaces or punctuation — collapse to one
    candidate, while values with DIFFERENT significant digits NEVER merge (the confident-wrong
    boundary: a misread truncation stays its own candidate, two distinct people's IDs stay
    distinct). All other values fall back to the whitespace+case norm (unchanged behaviour)."""
    iso = _parse_date(value)
    if iso is not None:
        return f"date:{iso}"
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) >= _CANON_MIN_DIGITS:
        return digits.lstrip("0") or "0"
    return _norm_value(value)


def era_split(observations: list[Observation], doc_date: dict[str, str | None],
              *, years: float = _TIME_HALF_LIFE_YEARS) -> bool:
    """Do the candidate values split across eras? True iff, among candidates with at least one
    dated supporting document, the span between the newest-dated and the oldest-dated candidate
    exceeds ``years`` — the precondition for a stale-vs-current confusion, and so the signal that
    recency discriminates. Fewer than two dated candidates ⇒ nothing to discriminate ⇒ False (a
    permanent fact is not decayed).

    This is the evidence *shape* the string-blind answer-brain body cannot compute itself — the
    abstract observations carry no value/date (the parity boundary). The capability bridge
    projects it from the raw observations + the doc_date covariate and the daemon reads it as a
    bool (move-4-design §2C). ``gather._era_split`` delegates here."""
    newest: dict[str, date] = {}
    for o in observations:
        iso = doc_date.get(o.artifact_cache_key)
        if not iso:
            continue
        key = _candidate_key(o.value_raw)
        d = date.fromisoformat(iso)
        if key not in newest or d > newest[key]:
            newest[key] = d
    if len(newest) < 2:
        return False
    span_days = (max(newest.values()) - min(newest.values())).days
    return span_days / 365.25 > years


def _grounded(quote: str, value: str, chunk: str) -> bool:
    """Whitespace-normalised verbatim containment of the quote OR the value (the
    action_items precedent, widened): the gate ties the observation to the excerpt
    (anti-hallucination), and must not fail a value that is plainly present just
    because RTL PDF extraction scrambled the visual order the model quoted in.
    Either anchor suffices; neither present = ungrounded."""
    norm_chunk = " ".join(chunk.split())
    quote_in = bool(quote.strip()) and " ".join(quote.split()) in norm_chunk
    value_in = bool(value.strip()) and " ".join(value.split()) in norm_chunk
    return quote_in or value_in


def authority_for(origin: str) -> tuple[str, float]:
    """The declared v0 authority class for a hit's origin path (stated prior)."""
    low = origin.casefold()
    if any(marker in low for marker in _AUTHORITY_MAIL_MARKERS):
        return ("email", 0.90)
    for extensions, name, value in _AUTHORITY_CLASSES:
        if low.endswith(extensions):
            return (name, value)
    return _AUTHORITY_DEFAULT


_NONE_CLAIM = "(none of the retrieved)"


def extract_instrument_hash() -> str:
    """The extract instrument's identity component that prompt surgery moves — graded
    outcomes carry it so reliability conditions on the EXACT instrument (§2), never
    pooling evidence about a superseded prompt into the current one's posterior."""
    return _sha(EXTRACT_PROMPT)


def _extractor_outcomes(outcomes_path: Path) -> list[float]:
    """Tally the extractor's graded outcomes (1 = correct, 0 = wrong) for the CURRENT extract
    instrument (§2): audit outcomes on the extract instrument + the lookup eval's per-candidate
    claim outcomes (the none-claim grades the posterior, not the instrument — excluded). Pure
    data-reading: the Bernoulli stream the wire folds, no host belief arithmetic."""
    current = extract_instrument_hash()
    obs: list[float] = []
    for event in O.read(outcomes_path):
        if event.instrument_identity.get("extract_prompt_hash") != current:
            continue
        producer = event.instrument_identity.get("producer_name")
        if event.grader == "audit" and producer == "life_agent.ask.lookup_extract":
            obs.append(1.0 if event.grade in O.CORRECT_GRADES["audit"] else 0.0)
        elif (event.grader == "eval_lookup"
                and producer == "life_agent.ask.lookup_answer"
                and event.claim != _NONE_CLAIM):
            obs.append(1.0 if event.grade in O.CORRECT_GRADES["eval_lookup"] else 0.0)
    return obs


def _extractor_rho_state(brain: Brain, outcomes_path: Path) -> str:
    """The rho Beta(4,4) prior CONDITIONED OVER THE WIRE on the extractor's graded outcomes
    (audit + eval_lookup). The live state id; the caller reads + destroys it. Never a host
    `prior + correct` fold (Invariant 1: condition is the one learning mechanism, even though
    Beta-Bernoulli conjugacy is exact)."""
    sid = brain.create_state({"type": "beta", "alpha": _RHO_PRIOR_A, "beta": _RHO_PRIOR_B})
    for o in _extractor_outcomes(outcomes_path):
        brain.condition(sid, kernel={"type": "bernoulli"}, observation=o)
    return sid


def extractor_reliability(brain: Brain, outcomes_path: Path = config.OUTCOMES_LOG
                          ) -> tuple[float, float]:
    """rho for "this observation's value is the true V" as a Beta (alpha, beta) — the wide Beta(4,4)
    prior conditioned over the wire on the graded evidence, read back via `read_params`. The
    full posterior (not just its mean) so the lookup rho-latent carries the extractor's reliability
    uncertainty exactly (the `reliability_categorical` rho prior, integrated analytically by the
    engine). The system learns whether to trust its own extractor from its own outcomes log — the
    §8 loop, closed, on the wire."""
    sid = _extractor_rho_state(brain, outcomes_path)
    try:
        spec = brain.read_params(sid)
        return float(spec["alpha"]), float(spec["beta"])
    finally:
        brain.destroy_state(sid)


def extractor_reliability_mean(brain: Brain | None = None,
                               outcomes_path: Path = config.OUTCOMES_LOG) -> float:
    """The rho posterior MEAN (a wire readout via `mean`, not a host a/(a+b)) — the scalar the
    string-blind bridge relays to the answer-brain. Same wire-conditioned Beta as
    :func:`extractor_reliability`; `brain` defaults to the shared skin (bridge convenience)."""
    b = brain if brain is not None else shared_brain()
    sid = _extractor_rho_state(b, outcomes_path)
    try:
        return b.mean(sid)
    finally:
        b.destroy_state(sid)


# --- route + observe (cached local-model instruments, the subject.py pattern) ----------

def _client() -> Any:
    return INSTR.instrument_client(LOOKUP_MODEL)


def route_question(root: Path, question: str, *,
                   client: Any | None = None,
                   meter: list[float] | None = None) -> Route | None:
    """The cached route verdict: the Route (construct + time-indexedness) if this is
    a typed lookup, else None. A verdict outside the schema raises and is never
    recorded. ``meter``, when given, accumulates the realised USD cost of cache-miss
    model calls (warm replays append nothing — $0 by construction, §18.9)."""
    if client is None:
        client = _client()
    key = D.lookup_route_key(question, model=LOOKUP_MODEL,
                             prompt_template=ROUTE_PROMPT,
                             engine_version=str(client.engine_version),
                             output_schema=ROUTE_SCHEMA)
    cached = D.lookup(root, key.cache_key)
    if cached is not None:
        parsed = json.loads(cached.decode("utf-8"))
    else:
        response = client.complete(ROUTE_PROMPT.replace("{question}", question),
                                   ROUTE_SCHEMA)
        if meter is not None:
            meter.append(float(getattr(response, "cost_usd", 0.0) or 0.0))
        parsed = json.loads(response.raw_text)
        if not isinstance(parsed.get("lookup"), bool):
            raise ValueError(f"lookup_route emitted junk: {parsed!r}")
        D.record(root, key,
                 json.dumps({"format_version": 1, **parsed}, sort_keys=True,
                            ensure_ascii=False).encode("utf-8"),
                 lineage=[])
    if not parsed.get("lookup"):
        return None
    return Route(construct=str(parsed.get("construct") or "the asked value"),
                 time_indexed=bool(parsed.get("time_indexed", False)))


def observe_hits(root: Path, question: str, hits: list[dict[str, Any]], *,
                 client: Any | None = None,
                 reliability: float | None = None,
                 covariates: HitCovariates | None = None,
                 time_indexed: bool = False,
                 today: date | None = None,
                 half_life_years: float = _TIME_HALF_LIFE_YEARS,
                 meter: list[float] | None = None,
                 ) -> tuple[list[Observation], int]:
    """One grounded extraction per hit (cached). Returns (grounded observations,
    indeterminate count). Indeterminate = the instrument returned ⊥ (not found) or its
    quote failed the grounding gate — recorded either way, counted, never silently
    dropped (§4.2's indeterminacy term). ``covariates`` carries the §4.1 doc_subject /
    doc_date factors into each observation's a_i. ``meter``, when given, accumulates
    the realised USD cost of cache-miss model calls (warm replays append nothing)."""
    if client is None:
        client = _client()
    cov = covariates if covariates is not None else HitCovariates()
    observations: list[Observation] = []
    indeterminate = 0
    for i, hit in enumerate(hits):
        chunk = str(hit["chunk_text"])
        key = D.lookup_extract_key(question, _sha(chunk), model=LOOKUP_MODEL,
                                   prompt_template=EXTRACT_PROMPT,
                                   engine_version=str(client.engine_version),
                                   output_schema=EXTRACT_SCHEMA)
        cached = D.lookup(root, key.cache_key)
        if cached is not None:
            parsed = json.loads(cached.decode("utf-8"))
        else:
            prompt = EXTRACT_PROMPT.replace("{question}", question).replace(
                "{chunk}", chunk)
            response = client.complete(prompt, EXTRACT_SCHEMA)
            if meter is not None:
                meter.append(float(getattr(response, "cost_usd", 0.0) or 0.0))
            raw = json.loads(response.raw_text)
            found = bool(raw.get("found")) and bool(str(raw.get("value") or "").strip())
            parsed = {"format_version": 1, "found": found,
                      "value": str(raw.get("value") or ""),
                      "quote": str(raw.get("quote") or "")}
            D.record(root, key,
                     json.dumps(parsed, sort_keys=True,
                                ensure_ascii=False).encode("utf-8"),
                     lineage=[{"cache_key": str(hit["artifact_cache_key"]),
                               "role": "source"}])
        # The grounding gate is consumer-side policy over the RAW recorded reply
        # (the expand/_clean_terms precedent): gate surgery re-gates replayed
        # records instead of orphaning them. Records predating this carry a
        # write-time "grounded" field — ignored, recomputed here.
        if not (parsed.get("found")
                and _grounded(str(parsed.get("quote") or ""),
                              str(parsed.get("value") or ""), chunk)):
            indeterminate += 1
            continue
        klass, authority = authority_for(str(hit.get("origin", "")))
        artifact_key = str(hit["artifact_cache_key"])
        # the doc_date covariate distinguishes "channel not projected" (key absent,
        # factor 1.0) from "projected but unknown" (None — the stated attenuation)
        t_factor = (time_factor(cov.doc_date[artifact_key],
                                time_indexed=time_indexed, today=today,
                                half_life_years=half_life_years)
                    if artifact_key in cov.doc_date else 1.0)
        # §4.2's competition term, detected at the source (consumer-side over the RAW
        # record, like the grounding gate above — warm replays re-detect): a same-shape
        # value inside the extractor's own quote window halves this observation's r.
        n_comp = MATCH.quote_scoped_competitors(
            str(parsed["value"]).strip(), chunk, str(parsed["quote"]))
        observations.append(Observation(
            card_n=i + 1,
            artifact_cache_key=artifact_key,
            obs_cache_key=key.cache_key,
            value_raw=str(parsed["value"]).strip(),
            value_norm=_norm_value(str(parsed["value"])),
            quote=str(parsed["quote"]),
            authority_class=klass,
            authority=authority,
            subject_factor=subject_factor(cov.subject_state.get(artifact_key)),
            time_factor=t_factor,
            doc_date=cov.doc_date.get(artifact_key),
            n_competing=n_comp,
            competition_factor=competition_factor(n_comp),
        ))
    # §5 dedup-as-inference at the SHARED shaper: collapse correlated duplicate documents
    # (identical-quote forward/reply chains, re-filed copies) to one witness here, BEFORE the
    # shaping→deciding split, so a duplicate cannot saturate the posterior on EITHER decider — the
    # host lookup_posterior OR the daemon's reliability_categorical (which consumes this verbatim
    # through to_abstract_observations). Placed in the decider alone (commit 546f1a5), the §4.2
    # temper never reached the executor path; observe_hits is the single seam both consume.
    return dedup_correlated(observations), indeterminate


def confirm_prefilter(value: str, hits: list[dict[str, Any]],
                      exclude_artifacts: set[str]) -> list[tuple[int, dict[str, Any]]]:
    """$0: the chunks an independent confirmation could come from — hits whose artifact
    is NOT already supporting the value and whose text carries it in the gate's own
    grading currency (token-boundary containment, ``matching.answer_matches``). Returns
    (original hit index, hit) pairs so citations stay aligned. Pure."""
    return [(i, h) for i, h in enumerate(hits)
            if str(h["artifact_cache_key"]) not in exclude_artifacts
            and MATCH.answer_matches(value, [], str(h["chunk_text"]))]


def confirm_hits(root: Path, question: str, value: str, hits: list[dict[str, Any]], *,
                 exclude_artifacts: set[str],
                 client: Any | None = None,
                 covariates: HitCovariates | None = None,
                 time_indexed: bool = False,
                 today: date | None = None,
                 half_life_years: float = _TIME_HALF_LIFE_YEARS,
                 m: int = 2,
                 meter: list[float] | None = None,
                 ) -> tuple[list[Observation], int]:
    """Value-targeted independent confirmation (§14 confirm_indep): for up to ``m``
    prefiltered chunks (independent artifact + carries the value), a cached CONFIRM
    read — "does this excerpt state the value as the current answer?" — whose grounded
    yes becomes a REAL Observation on the confirming chunk's OWN artifact, with its own
    authority/subject/time covariates and its own quote-window competition factor (§2:
    competition is a property of the corpus row, never inherited from the target's).
    Returns (grounded confirmations, indeterminate count) — a decline or a failed
    grounding gate is counted, never silently dropped, and never disagrees: the probe
    is one-sided by construction (it can only add support for ``value``)."""
    if client is None:
        client = _client()
    cov = covariates if covariates is not None else HitCovariates()
    value = value.strip()
    observations: list[Observation] = []
    indeterminate = 0
    for i, hit in confirm_prefilter(value, hits, exclude_artifacts)[:max(m, 0)]:
        chunk = str(hit["chunk_text"])
        key = D.lookup_confirm_key(question, _sha(chunk), _norm_value(value),
                                   model=LOOKUP_MODEL,
                                   prompt_template=CONFIRM_PROMPT,
                                   engine_version=str(client.engine_version),
                                   output_schema=CONFIRM_SCHEMA)
        cached = D.lookup(root, key.cache_key)
        if cached is not None:
            parsed = json.loads(cached.decode("utf-8"))
        else:
            prompt = (CONFIRM_PROMPT.replace("{question}", question)
                      .replace("{value}", value).replace("{chunk}", chunk))
            response = client.complete(prompt, CONFIRM_SCHEMA)
            if meter is not None:
                meter.append(float(getattr(response, "cost_usd", 0.0) or 0.0))
            raw = json.loads(response.raw_text)
            parsed = {"format_version": 1, "confirms": bool(raw.get("confirms")),
                      "quote": str(raw.get("quote") or "")}
            D.record(root, key,
                     json.dumps(parsed, sort_keys=True,
                                ensure_ascii=False).encode("utf-8"),
                     lineage=[{"cache_key": str(hit["artifact_cache_key"]),
                               "role": "source"}])
        # consumer-side gate over the RAW record (the observe_hits precedent): the
        # quote (or the exact value string) must be verbatim in the chunk — a
        # confirm-happy reply with a hallucinated quote on a tokenization-divergent
        # chunk stays indeterminate.
        if not (parsed.get("confirms")
                and _grounded(str(parsed.get("quote") or ""), value, chunk)):
            indeterminate += 1
            continue
        klass, authority = authority_for(str(hit.get("origin", "")))
        artifact_key = str(hit["artifact_cache_key"])
        t_factor = (time_factor(cov.doc_date[artifact_key],
                                time_indexed=time_indexed, today=today,
                                half_life_years=half_life_years)
                    if artifact_key in cov.doc_date else 1.0)
        n_comp = MATCH.quote_scoped_competitors(
            value, chunk, str(parsed["quote"]))
        observations.append(Observation(
            card_n=i + 1,
            artifact_cache_key=artifact_key,
            obs_cache_key=key.cache_key,
            value_raw=value,
            value_norm=_norm_value(value),
            quote=str(parsed["quote"]),
            authority_class=klass,
            authority=authority,
            subject_factor=subject_factor(cov.subject_state.get(artifact_key)),
            time_factor=t_factor,
            doc_date=cov.doc_date.get(artifact_key),
            n_competing=n_comp,
            competition_factor=competition_factor(n_comp),
        ))
    return observations, indeterminate


# --- the posterior (pure builders; conditioning through the credence skin) -------------

def candidates_from(observations: list[Observation]) -> list[str]:
    """Distinct candidate values in first-seen order; display form = first raw form.
    Identity is the §4.2 canonical key, so OCR/format variants of one number collapse."""
    seen: dict[str, str] = {}
    for o in observations:
        seen.setdefault(_candidate_key(o.value_raw), o.value_raw)
    return list(seen.values())


def _covariate(o: Observation) -> float:
    """The §4.1 evidence covariate folded into the group channel: authority·subject·time."""
    return o.authority * o.subject_factor * o.time_factor


def _quote_key(quote: str) -> str:
    """Normalised quote for correlation dedup (whitespace-collapsed, casefolded)."""
    return " ".join((quote or "").split()).casefold()


def dedup_correlated(observations: list[Observation]) -> list[Observation]:
    """Collapse correlated DUPLICATE observations to one witness each (§5 dedup-as-inference).

    Observations carrying a near-identical quote across DIFFERENT documents are the same
    underlying text duplicated (a forwarded/replied email chain, a re-filed copy), not
    independent witnesses — counting them independently saturates the posterior (the regression
    c71481f introduced when it retired the §4.2 ancestry temper: q-002's 6 emails → 0.99 on a
    wrong value, q-014's 9 stale copies → 0.80). Each substantial-quote cluster spanning
    multiple documents is reduced to the MAX-covariate document's observations — the
    strongest/freshest copy, so a recent re-attestation keeps its recency. Within a single
    document, and for value-ONLY quotes (no shared context), nothing collapses: genuine
    independent corroboration must still accumulate; only duplicates collapse. Order-preserving
    and pure."""
    rows = [(o.quote, o.artifact_cache_key, o.value_norm, _covariate(o))
            for o in observations]
    drop = dedup_drop_rows(rows)
    return [o for i, o in enumerate(observations) if i not in drop]


def dedup_drop_rows(rows: list[tuple[str, str, str, float]]) -> set[int]:
    """THE §5 clustering rule over ``(quote, doc_key, value_norm, covariate)`` rows — the
    index set to drop. :func:`dedup_correlated` and the wire join
    (``bridge/observations.join_wire_observations``, r09 D2) both call this; a second
    implementation of the rule anywhere is a defect (§6.8)."""
    by_quote: dict[str, list[int]] = {}
    for i, (quote, _doc, _vn, _cov) in enumerate(rows):
        by_quote.setdefault(_quote_key(quote), []).append(i)
    drop: set[int] = set()
    for qkey, idxs in by_quote.items():
        # Declared FIRST-SEEN order, not a set: `max` returns the first maximal element, so
        # at equal covariate the survivor is a function of the observations rather than of the
        # interpreter's per-process hash seed (M0.5 — the tie moved 24.5% of the recorded
        # battery's decisions between two runs of the same code on the same corpus).
        docs = list(dict.fromkeys(rows[i][1] for i in idxs))
        if len(docs) <= 1:
            continue  # within one document — the per-document group already counts it once
        # Dedupe only when the shared quote carries CONTEXT beyond the bare value: identical
        # SURROUNDING text across documents is the duplicate signal (a forwarded/quoted chain or
        # a re-filed copy). A value-only quote is kept — the same value with no shared context
        # may be genuine independent corroboration, not a copy. (q-002's wrong cluster shares the
        # 2-token quote "Israeli <id>"; the gold its own scan-OCR quote — both carry context.)
        value_tokens = set((rows[idxs[0]][2] or "").split())
        if not any(t not in value_tokens for t in qkey.split()):
            continue
        best = max(docs, key=lambda d: max(
            rows[i][3] for i in idxs if rows[i][1] == d))
        drop.update(i for i in idxs if rows[i][1] != best)
    return drop


def _v_marginal(brain: Brain, state_id: str) -> list[float]:
    """The V posterior MARGINALISED over the continuous rho-latent: the `reliability_categorical`'s
    `weights` — the engine integrates rho analytically (an exact Beta-moment sum). A readout
    (render order / p_none / p_attested / gather ranking) — the body never folds rho itself
    (Invariant 1). Layout: candidates 0..k-1 then NONE last."""
    return brain.weights(state_id)


def lookup_posterior(brain: Brain, observations: list[Observation],
                     candidates: list[str], rho_ab: tuple[float, float]
                     ) -> tuple[list[float], str]:
    """The candidate+NONE posterior under the EXACT correlated-evidence model (replacing the §4.2
    host tempering): a `reliability_categorical` — a categorical over the K candidates + NONE with a
    CONTINUOUS Beta reliability latent rho (the carried extractor reliability, prior = the Beta
    `rho_ab`). Observations group BY DOCUMENT (artifact); each group conditions via a
    `group_noisy_channel` (covariate = authority·subject·time of the doc, A alternatives) on the
    group's reported candidate-positions (1-based atom values; same-doc reports are correlated,
    sharing r_d = rho·covariate, rho coupling the groups). The engine integrates rho ANALYTICALLY —
    the group-channel is linear in rho, so a Beta prior stays a polynomial-in-rho x Beta and the
    V-marginal is an exact Beta-moment sum, NO grid. Returns (the rho-marginalised V weights with
    NONE last, the live state id — open for `optimise`; the caller destroys it)."""
    k = len(candidates)
    # stated V prior: _P_NONE_PRIOR on none-of-the-retrieved, the rest uniform over candidates.
    v_prior = [(1.0 - _P_NONE_PRIOR) / k] * k + [_P_NONE_PRIOR]
    alpha, beta = rho_ab
    state_id = brain.create_state({
        "type": "reliability_categorical",
        "v_log_weights": [math.log(w) for w in v_prior],
        "alpha": alpha, "beta": beta,
    })
    keys = [_candidate_key(c) for c in candidates]
    # NB: correlated-duplicate collapse (§5 dedup-as-inference) happens UPSTREAM in observe_hits,
    # the shared shaper both deciders consume — so this builder and the daemon's
    # reliability_categorical see identical, already-deduped evidence. Do not re-dedup here: that
    # asymmetry (host deciding-time temper the daemon lacked) was the regression 546f1a5 half-fixed.
    groups: dict[str, list[Observation]] = {}
    for o in observations:
        groups.setdefault(o.artifact_cache_key, []).append(o)
    for group in groups.values():
        o0 = group[0]  # one document's covariates are shared by all its chunks
        # §4.2's competition term: chunk-level, so the group covariate takes the group's
        # most-competed observation (min factor — the conservative fold; mirrors the
        # daemon's per-observation r product on the executor path).
        covariate = _covariate(o0) * min(o.competition_factor for o in group)
        reports = [keys.index(_candidate_key(o.value_raw)) + 1 for o in group]  # 1-based atom value
        kernel = {"type": "group_noisy_channel", "covariate": covariate,
                  "n_alternatives": _A_ALTERNATIVES}
        brain.condition(state_id, kernel=kernel, observation=reports)
    return _v_marginal(brain, state_id), state_id


def action_utilities(weights: list[float], u_bar: dict[str, float],
                     scoped_eu: float) -> dict[str, list[float]]:
    """Per-action utility vectors over the hypothesis atoms (K candidates + NONE), derived from
    :func:`life_agent.core.decide.u_assert` (the one written atom). `report_j` (one per candidate)
    asserts candidate j — ``u_assert(1)`` at j, ``u_assert(0)`` = u_wrong elsewhere incl NONE — so
    `optimise` picks the best report and the MAP candidate emerges from the ENGINE, never a host
    argmax. hedge asserts the candidate set (misleading only when the truth is NONE); ask_clarify
    is the oracle price (NOT a u_assert outcome); abstain is the gauge zero.

    ``report_scoped`` asserts a TRUE time-scoped claim ("as of <date>, X"). Its truth is about the
    *record*, not which V_now holds, so its row is **flat** at ``scoped_eu`` — the attested-record
    EU computed SERVER-SIDE off the recency-off posterior (``expect`` in :func:`_scoped_option`),
    never a host ``p_attested*u_hedged + …``. (0.0 ⇒ no datable record ⇒ stays below abstain.)"""
    k = len(weights) - 1
    u_correct = u_assert(1.0, u_bar)
    u_wrong = u_assert(0.0, u_bar)
    out: dict[str, list[float]] = {}
    for j in range(k):
        out[f"report_{j}"] = [(u_correct if i == j else u_wrong) for i in range(k)] + [u_wrong]
    out["hedge"] = [u_bar["u_hedged"]] * k + [u_wrong]
    out["ask_clarify"] = [_ORACLE_P * u_bar["u_correct"] - u_bar["lambda_int"]] * (k + 1)
    out["abstain"] = [u_bar["u_abstain"]] * (k + 1)
    out["report_scoped"] = [scoped_eu] * (k + 1)
    return out


# functional_per_action ignores the action space; a placeholder keeps the protocol shape.
_LOOKUP_ACTIONS: dict[str, Any] = {"type": "finite", "values": [0.0]}


def decide(brain: Brain, state_id: str, weights: list[float],
           u_bar: dict[str, float], scoped_eu: float = 0.0) -> tuple[str, float]:
    """`optimise` over the response actions on the live rho-latent state, committed through
    the ONE act seam (:func:`life_agent.core.seam.commit` — roadmap M0). `report` expands into
    a per-candidate `report_j` so the engine picks the asserted candidate (no host argmax); a
    `report_j` winner maps to action ``report`` (its candidate is the weight-MAP = the weight-sorted
    ``candidates[0]`` the caller renders — a render label, not a second decision).
    ``scoped_eu`` prices report_scoped (0.0 ⇒ never wins)."""
    utilities = action_utilities(weights, u_bar, scoped_eu)
    preference = {
        "type": "functional_per_action",
        "actions": {name: {"type": "tabular", "values": vec} for name, vec in utilities.items()},
    }
    dec = SEAM.commit(SEAM.SkinOptimise(brain=brain, state_id=state_id,
                                        actions=_LOOKUP_ACTIONS, preference=preference))
    action, eu = dec.action, dec.eu
    assert eu is not None  # a SkinOptimise commit always carries the engine's EU
    if isinstance(action, str) and action.startswith("report_") and action != "report_scoped":
        action = "report"  # report_j → report; the asserted value is the weight-MAP candidate
    return action, eu


# --- render (deterministic — the render IS the claim set) -------------------------------

def render(result: LookupResult) -> str:
    """The credence grammar (interaction contract): claims with credences, citations
    per observation, the posterior named in the footer — nothing silent."""
    by_value: dict[str, list[int]] = {}
    for o in result.observations:
        by_value.setdefault(_candidate_key(o.value_raw), []).append(o.card_n)

    def _cites(value: str) -> str:
        ns = sorted(set(by_value.get(_candidate_key(value), [])))
        return "".join(f"[{n}]" for n in ns)

    alts = " · ".join(
        f"{v} ({p:.3f}) {_cites(v)}".rstrip()
        for v, p in zip(result.candidates, result.credences, strict=True))
    if result.action == "report":
        v = result.candidates[0]
        body = GRAMMAR["report"].format(value=v, p=result.credences[0],
                                        cites=_cites(v))
    elif result.action == "report_scoped":
        v = result.scoped_value or ""
        body = GRAMMAR["report_scoped"].format(value=v, as_of=result.as_of,
                                               p=result.scoped_p, cites=_cites(v))
    elif result.action == "hedge":
        body = GRAMMAR["hedge"].format(alts=alts)
    elif result.action == "ask_clarify":
        body = GRAMMAR["ask_clarify"].format(alts=alts)
    elif result.action == "abstain" and result.candidates:
        body = GRAMMAR["abstain_withheld"].format(reason=REASON_DISPERSED, alts=alts)
    else:
        # zero candidates ⇒ no posterior existed, so "dispersed" would be a false reason
        # (interaction contract: the named reason must be the true one).
        body = GRAMMAR["abstain"].format(reason=REASON_NO_OBSERVATIONS)
    footer = GRAMMAR["footer"].format(
        n_hits=result.n_hits, n_obs=len(result.observations),
        n_ind=result.n_indeterminate, p_none=result.p_none,
        action=result.action, eu=result.eu)
    return f"{body}\n\n{footer}"


# --- the shared brain + utility fold (per-process, lazily) -------------------------------

_BRAIN: Brain | None = None
_U_BAR: tuple[str, dict[str, float]] | None = None  # (fold_version, u_bar)


def shared_brain() -> Brain:
    """One skin process per ask session (REPL pays the spawn once; one-shot per run —
    the §14 throughput question measures exactly this)."""
    global _BRAIN
    if _BRAIN is None:
        _BRAIN = Brain.spawn()
        _BRAIN.initialize()
        atexit.register(_shutdown)
    return _BRAIN


def _shutdown() -> None:
    global _BRAIN
    if _BRAIN is not None:
        _BRAIN.shutdown()
        _BRAIN = None


def set_shared_brain(brain: Brain | None) -> None:
    """Install (or clear) the process's shared skin — **the instrument seam, not a lane**.

    The only sanctioned caller is the module-collapse equivalence instrument
    (:mod:`life_agent.collapse`), which records the engine wire once and replays it with no
    engine present; :func:`life_agent.core.narrative.narrative_answer` reaches the skin
    through :func:`shared_brain` rather than a parameter, so an off-path replay needs this
    seam to reach it. Nothing on the decision path may call it — a second installer would be
    a way to swap the engine underneath a live decision, which is precisely the fork the one
    act seam exists to prevent. Drift-gated in ``tests/test_collapse_record.py``.
    """
    global _BRAIN
    _BRAIN = brain


def current_u_bar(brain: Brain) -> tuple[dict[str, float], str]:
    """Ū from the utility posterior (fold of model + elicitations), cached per fold
    version within the process — the fold is recomputed only when evidence moves."""
    global _U_BAR
    model = UT.load_model(config.UTILITY_MODEL)
    events: list[UT.Evidence] = list(
        UT.load_elicitations(config.UTILITY_ELICITATIONS, model))
    # §4.4 reaction loop: the owner's clean abstain-verdicts, joined to the decision log,
    # condition u(wrong). fold_version covers them, so a new verdict re-folds Ū demand-led.
    events += R.load_reactions(config.REACTIONS_LOG, config.DECISIONS_LOG)
    version = UT.fold_version(model, events)
    if _U_BAR is not None and _U_BAR[0] == version:
        return _U_BAR[1], version
    post = UT.posterior(brain, model, events)
    for warning in post.endpoint_warnings(model.endpoint_mass_warn):
        print(f"  ⚠ {warning}")
    _U_BAR = (version, post.u_bar())
    return _U_BAR[1], version


# --- the family, end to end --------------------------------------------------------------

def _scoped_option(brain: Brain, observations: list[Observation],
                   candidates: list[str], rho_ab: tuple[float, float], *,
                   u_bar: dict[str, float], state_current: str,
                   weights_current: list[float], time_indexed: bool,
                   ) -> tuple[float, float, str | None, str | None]:
    """The report_scoped inputs (scoped-claims design): the freshest DATED observation gives the
    scoped value V_s ("most recent record on file") and its as-of date. Returns ``(scoped_eu,
    p_attested, V_s, as_of)``. ``scoped_eu`` is the attested-record EU computed SERVER-SIDE —
    ``expect(recency-off posterior, tabular[u_hedged @ V_s, u_wrong_scoped elsewhere])`` =
    P_attested(V_s)·u_hedged + (1-P_attested(V_s))·u_wrong_scoped — never a host product on a
    belief value. ``p_attested`` = V_s's recency-off V-marginal (recorded). Both 0.0 / None when
    no observation carries a date (scoped disabled — the flat row sits below abstain). The attested
    posterior is the current one when recency was already off (a permanent fact), else a second
    pass with the time decay removed."""
    dated = [o for o in observations if o.doc_date]
    if not dated:
        return 0.0, 0.0, None, None
    freshest = max(dated, key=lambda o: o.doc_date or "")  # ISO dates sort lexicographically
    keys = [_candidate_key(c) for c in candidates]
    idx_vs = keys.index(_candidate_key(freshest.value_raw))
    k = len(candidates)
    # tabular over K candidates + NONE: u_hedged at the attested value, u_wrong_scoped elsewhere.
    scoped_tab = {"type": "tabular",
                  "values": [(u_bar["u_hedged"] if i == idx_vs else u_bar["u_wrong_scoped"])
                             for i in range(k)] + [u_bar["u_wrong_scoped"]]}
    if time_indexed:
        attested_obs = [dataclasses.replace(o, time_factor=1.0) for o in observations]
        weights_attested, sid = lookup_posterior(brain, attested_obs, candidates, rho_ab)
        try:
            scoped_eu = brain.expect(sid, function=scoped_tab)
        finally:
            brain.destroy_state(sid)
    else:
        weights_attested = weights_current
        scoped_eu = brain.expect(state_current, function=scoped_tab)
    return scoped_eu, weights_attested[idx_vs], freshest.value_raw, freshest.doc_date


def decide_and_record(root: Path, question: str, construct: str,
                      observations: list[Observation], indeterminate: int, *,
                      n_hits: int, time_indexed: bool,
                      brain: Brain | None = None,
                      decisions_path: Path | None = None,
                      run_id: str = "ask",
                      rho_override: tuple[float, float] | None = None) -> LookupResult:
    """The lookup family's tail: a grounded observation set → the rho-latent correlated-evidence
    posterior → EU decision under Ū → recorded answer (§18.9) + logged decision (§8). Shared by
    the single-pass :func:`lookup_answer` and the gather-augmented loop
    (:mod:`life_agent.core.gather`): both produce observations, then value and record them
    identically. ``time_indexed`` enters the answer key + content (an auditable decision
    input — the gather loop may set it differently from the route). Assumes
    ``observations`` is non-empty (its caller routes the empty case to narrative).

    ``rho_override`` replaces the local-extractor reliability Beta for an observation set
    produced by a DIFFERENT instrument (the ``extract@<model>`` joint edge folds its calibrated
    confidence here, not the local ``extractor_reliability``)."""
    b = brain if brain is not None else shared_brain()
    u_bar, fold_ver = current_u_bar(b)
    rho = rho_override if rho_override is not None else extractor_reliability(b)
    candidates = candidates_from(observations)
    weights, state_id = lookup_posterior(b, observations, candidates, rho)
    try:
        scoped_eu, p_attested, scoped_value, as_of = _scoped_option(
            b, observations, candidates, rho,
            u_bar=u_bar, state_current=state_id,
            weights_current=weights, time_indexed=time_indexed)
        action, eu = decide(b, state_id, weights, u_bar, scoped_eu)
    finally:
        b.destroy_state(state_id)

    # posterior order for rendering: candidates by weight, NONE mass separate
    order = sorted(range(len(candidates)), key=lambda j: weights[j], reverse=True)
    cands = tuple(candidates[j] for j in order)
    creds = tuple(weights[j] for j in order)
    p_none = weights[-1]

    # the answer artifact (§18.9): claim set + posterior + decision inputs, lineage to
    # every observation — the lookup family's computation stays on the ledger. The
    # per-observation covariate factors are decision inputs, so they enter both the
    # key (via params) and the recorded content (auditability).
    obs_covariates = [
        {"obs": o.obs_cache_key, "subject_factor": o.subject_factor,
         "time_factor": o.time_factor, "n_competing": o.n_competing,
         "competition_factor": o.competition_factor}
        for o in observations]
    params = {"A": _A_ALTERNATIVES, "oracle_p": _ORACLE_P,
              "competition_cap": _COMPETITION_CAP,
              "p_none_prior": _P_NONE_PRIOR, "rho": list(rho),
              "a_subject_other": _A_SUBJECT_OTHER,
              "p_owner_indet": _P_OWNER_GIVEN_INDET,
              "time_half_life_years": _TIME_HALF_LIFE_YEARS,
              "a_time_unknown": _A_TIME_UNKNOWN,
              "time_indexed": time_indexed,
              "p_attested": round(p_attested, 6),  # the report_scoped decision input
              "covariates": _sha(json.dumps(obs_covariates, sort_keys=True))}
    obs_hash = _sha(json.dumps(sorted(o.obs_cache_key for o in observations)))
    akey = D.lookup_answer_key(question, obs_hash, fold_ver, params)
    content = json.dumps({
        "format_version": 1, "question": question, "construct": construct,
        "time_indexed": time_indexed, "covariates": obs_covariates,
        "candidates": list(cands), "credences": list(creds), "p_none": p_none,
        "action": action, "eu": eu, "utility_fold_version": fold_ver,
        # the scoped option recorded whether or not it was chosen — the deferred upgrade
        # governor's evidence (scoped-claims design §6): the true partial that was available.
        "scoped": {"value": scoped_value, "as_of": as_of,
                   "p_attested": round(p_attested, 6)},
    }, sort_keys=True, ensure_ascii=False).encode("utf-8")
    # unique inputs, first-occurrence order: two observations can share one extract key
    # (identical chunk text — observe_hits keys on the chunk, not the artefact); the
    # catalogue's lineage key is (artifact, input), so the observation is ONE input (§18.9)
    D.record(root, akey, content,
             lineage=[{"cache_key": k, "role": "observation"}
                      for k in dict.fromkeys(o.obs_cache_key for o in observations)])

    result = LookupResult(
        question=question, construct=construct, action=action, eu=eu,
        candidates=cands, credences=creds, p_none=p_none,
        observations=tuple(observations), n_hits=n_hits,
        n_indeterminate=indeterminate, utility_fold_version=fold_ver,
        answer_cache_key=akey.cache_key, rendered="",
        as_of=as_of, scoped_value=scoped_value, scoped_p=p_attested,
        time_indexed=time_indexed)
    result = dataclasses.replace(result, rendered=render(result))

    DEC.append(decisions_path if decisions_path is not None else config.DECISIONS_LOG,
               DEC.DecisionEvent(
                   tx_time=O.now_iso(), run_id=run_id,
                   question_id=DEC.question_id(question),
                   family="lookup",
                   action_set=_ACTION_ORDER,
                   posterior_summary={
                       "candidates": list(cands), "credences": list(creds),
                       "p_none": p_none, "n_obs": len(observations),
                       "n_indeterminate": indeterminate,
                       "n_competing": sum(1 for o in observations if o.n_competing),
                   },
                   utility_fold_version=fold_ver,
                   chosen_action=action, predicted_eu=eu,
                   decision_id=akey.cache_key))
    return result


def lookup_answer(root: Path, question: str, hits: list[dict[str, Any]], *,
                  scope: str = "unscoped",
                  brain: Brain | None = None,
                  route_client: Any | None = None,
                  extract_client: Any | None = None,
                  covariates: HitCovariates | None = None,
                  decisions_path: Path | None = None,
                  run_id: str = "ask",
                  ) -> LookupResult | None:
    """Run the single-pass lookup family over admitted hits. None ⇒ the narrative path
    answers (not routed as a lookup, or zero grounded observations — a coverage statement,
    not an abstention; the caller names the fallthrough). The gather-augmented variant is
    :func:`life_agent.core.gather.gather_answer`; both share :func:`decide_and_record`.

    ``scope`` is the question's temporal intent (:mod:`life_agent.core.temporal_intent`). The
    recency decay assumes a PRESENT reading; a ``historical``/``as_of`` question must NOT penalise
    old attested values (you want the era value, not the current one), so it suppresses the decay
    (``time_indexed`` off). ``present``/``unscoped`` keep the construct's volatility verdict —
    unchanged on the present-tense path. Gate-safe: it only ever REMOVES a penalty."""
    route = route_question(root, question, client=route_client)
    if route is None:
        return None
    effective_ti = route.time_indexed and scope not in ("historical", "as_of")
    observations, indeterminate = observe_hits(root, question, hits,
                                               client=extract_client,
                                               covariates=covariates,
                                               time_indexed=effective_ti)
    if not observations:
        return None
    return decide_and_record(
        root, question, route.construct, observations, indeterminate,
        n_hits=len(hits), time_indexed=effective_ti, brain=brain,
        decisions_path=decisions_path, run_id=run_id)
