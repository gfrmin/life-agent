"""The lookup family's evidence shaping — a point-fact question into observations.

V is a point fact ("what is my ID?", "when is the appointment?"). Every stage is on the
ledger (system-design §3) and every modelling choice is stated:

    route      cached model verdict: is this a verbatim point fact? A question that is not
               is declined (the MVP bar, CLAUDE.md)
    observe    per retrieval hit, a question-parameterised grounded extraction (§18.9,
               cached on (question, chunk content); an ungrounded quote is recorded and
               treated as indeterminate — the grounding gate is error-model surgery)
    dedup      correlated duplicates collapse before any posterior sees them
    render     deterministic templates from one grammar table (no LLM — the render IS the
               claim set), citations per observation

The candidate posterior is :mod:`life_agent.core.posterior`; the act is
:func:`life_agent.core.decide.bayes_act`, reached through :mod:`life_agent.core.decider`.

Stated channel parameters (each a prior choice calibration will move — §2, §14):
``reliability.PRIORS`` (the grounded-extraction reliability Beta prior, moved by audit
outcomes), the declared source-authority classes (§4.1's v0 lattice), and the §4.1
covariate factors (``_A_SUBJECT_*`` / ``_TIME_HALF_LIFE_YEARS`` / ``_A_TIME_UNKNOWN`` —
doc_subject and doc_date enter a_i: a document about someone else, or from the wrong era,
supports a different variable; construct validity, not noise).
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from life_agent.core import answer_shape as AS
from life_agent.core import config
from life_agent.core import derivations as D
from life_agent.core import instrument as INSTR
from life_agent.core import matching as MATCH
from life_agent.core import outcomes as O
from life_agent.core import reactions as R
from life_agent.core import reliability as REL
from life_agent.core import utility as UT
from life_agent.core.dates import parse_date as _parse_date
from life_agent.core.decide import shaped_u_bar

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

# --- stated channel parameters: their one home is core/pricing.py (the channel half) ------
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

# Closed abstention reasons (the credence grammar — interaction contract).
# The reason must be the TRUE one. These are not interchangeable labels: DISPERSED is a
# statement about a posterior that existed and lost the EU argmax; NO_OBSERVATIONS is the
# absence of any posterior at all (nothing was grounded, so nothing was dispersed);
# UNAVAILABLE is a statement about the corpus, not about belief — the evidence is not in
# this machine's catalogue, so no amount of thinking here would have found it.
REASON_DISPERSED = "dispersed posterior"
REASON_NO_OBSERVATIONS = "no admitted evidence"
# (REASON_UNAVAILABLE was retired at r33 A4: defined since M5 and never bound by any
# render branch — the §6.5 reply is ask_client.DOWN, its own contract string.)

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
    # r30b: the `quantity` shape's claim — a RANGE, asserted at its own coverage credence.
    # The endpoints are the candidates' own display strings (never a reformatted float: no
    # invented precision, no currency the corpus did not carry), and the credence is the
    # posterior mass the range covers, so a wider claim visibly buys its confidence.
    "hedge": "Unresolved — candidates: {alts}",
    "ask_clarify": "Worth asking you directly — the evidence does not settle it: {alts}",
    "abstain": "No answer asserted ({reason}).",
    # abstain still shows the candidate(s) it withheld below the assert threshold — the
    # held-back "thinking" that makes the decision verdictable (is that value right?) rather
    # than a blind "should you have answered?". Used when the posterior held >=1 candidate.
    "abstain_withheld": "No answer asserted ({reason}). Held back: {alts}",
    # r33 RC-3: {p_none}/{eu} arrive PRE-FORMATTED — a number only when a posterior
    # produced one; a miss (None) renders "—", never a fabricated 0.000 (an "I found
    # nothing" must not print identically to "zero mass on NONE").
    "footer": ("lookup: {n_hits} hits → {n_obs} grounded observations"
               " · {n_ind} indeterminate · none-of-retrieved {p_none}"
               " · decision {action} (EU {eu})"),
    "fallthrough": "(lookup: {reason} — narrative path)",
    # J2: the FIRST line of every reply names where the answer came from (rule 3):
    # a span in your documents, a named rung, or a decline with its reason.
    "origin_documents": "From your documents.",
    "origin_rung": ("Answered by the {rung} rung; {n_hits} retrieved document(s) were "
                    "shared with it."),
    "origin_declined": "Declined: {reason}.",
}

#: The declined reasons in the reply's words, keyed by decisions.origin()'s reason.
ORIGIN_REASONS: dict[str, str] = {
    "unavailable": "the decider is unavailable",
    "miss": "no admitted evidence",
    "dispersed": "the evidence does not settle on one answer",
    "asked": "the evidence does not settle it; worth asking you directly",
    "not a point fact": "not a question with a single verbatim answer",
}


def origin_line(kind: str, *, rung: str = "", reason: str = "", n_hits: int = 0) -> str:
    """The reply's first line for an origin (``decisions.origin``), in the grammar."""
    if kind == "documents":
        return GRAMMAR["origin_documents"]
    if kind == "rung":
        return GRAMMAR["origin_rung"].format(rung=rung, n_hits=n_hits)
    if kind == "declined":
        return GRAMMAR["origin_declined"].format(reason=ORIGIN_REASONS.get(reason, reason))
    raise ValueError(f"unknown origin kind {kind!r}")


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
    """[§3.3 · L-7] The doc_subject covariate on a_i. None = no covariate (not an owner-scoped
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


def source_date_iso(dated: list[str | None], as_of_iso: str | None) -> str | None:
    """[§3.3 · D-14] (with L-6/N-4/BR-3/P-1): THE date-selection of the one recency
    policy — which date feeds :func:`time_factor` for a whole-question/re-read
    observation. Recency is a document property, independent of WHOSE value it is, so
    a value is as current as its freshest SOURCE attestation: the max among the
    doc_dates of the value-carrying hits; else the instrument's self-reported
    (already-normalised) ``as_of``; else ``None`` (undated time-indexed ⇒ the stated
    marginal attenuation inside ``time_factor``). The policy's other two declared
    branches live with their inputs: the projection-side date-SOURCE rule (P-1 — the
    email-header fallback in ``probes``' doc_date covariate) and the claim-side branch
    (N-4 — ``narrative.scope_decay`` reads the claim's own ``as_of``, present scope
    only). Different inputs, one policy; a second spelling of this chain may not
    exist."""
    known = sorted(d for d in dated if d)
    return known[-1] if known else as_of_iso


def time_factor(date_iso: str | None, *, time_indexed: bool,
                today: date | None = None,
                half_life_years: float = _TIME_HALF_LIFE_YEARS) -> float:
    """[§3.3 · L-6] The doc_date covariate on a_i: for a time-indexed construct, the probability a
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


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _norm_value(value: str) -> str:
    # [§3.3 · L-4] candidate identity — the observation equivalence relation
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


def era_split(  # [§3.3 · L-5/GA-3] the era structure of the observation set
        observations: list[Observation], doc_date: dict[str, str | None],
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
    """[§3.3 · L-1/E-10] The grounding predicate — a likelihood term of the observation
    model (an ungrounded quote is not an observation; a retrieval grow re-enters here).
    Whitespace-normalised verbatim containment of the quote OR the value (the
    action_items precedent, widened): the gate ties the observation to the excerpt
    (anti-hallucination), and must not fail a value that is plainly present just
    because RTL PDF extraction scrambled the visual order the model quoted in.
    Either anchor suffices; neither present = ungrounded."""
    norm_chunk = " ".join(chunk.split())
    quote_in = bool(quote.strip()) and " ".join(quote.split()) in norm_chunk
    value_in = bool(value.strip()) and " ".join(value.split()) in norm_chunk
    return quote_in or value_in


def authority_for(origin: str) -> tuple[str, float]:
    """[§3.3 · L-8] The declared v0 authority class for a hit's origin path (stated prior)."""
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


def extractor_reliability(outcomes_path: Path = config.OUTCOMES_LOG) -> tuple[float, float]:
    """rho for "this observation's value is the true V" as a Beta (alpha, beta): the wide
    Beta(4,4) prior conditioned on the extractor's graded outcomes. The system learns whether
    to trust its own extractor from its own outcomes log — the §8 loop, closed."""
    return REL.reliability("extract", "value", _extractor_outcomes(outcomes_path))


def extractor_reliability_mean(outcomes_path: Path = config.OUTCOMES_LOG) -> float:
    """The rho posterior mean — the scalar the string-blind bridge relays to the decider."""
    return REL.mean("extract", "value", _extractor_outcomes(outcomes_path))


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
    # §5 dedup (correlation collapse) at the SHARED shaper: collapse correlated duplicate documents
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


# --- evidence shaping (pure builders) ----------------------------------------------------

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
    """[§3.3 · L-2] The correlation structure — correlated duplicates are one attestation.
    Collapse correlated DUPLICATE observations to one witness each (§5 dedup —
    correlation collapse; the inference half is the aggregate family's component 3,
    a different object).

    Observations carrying a near-identical quote across DIFFERENT documents are the same
    underlying text duplicated (a forwarded/replied email chain, a re-filed copy), not
    independent witnesses — counting them independently saturates the posterior (the regression
    c71481f introduced when it retired the §4.2 ancestry temper: q-002's 6 emails → 0.99 on a
    wrong value, q-014's 9 stale copies → 0.80). Each substantial-quote cluster spanning
    multiple documents is reduced to the MAX-covariate document's observations — the
    strongest/freshest copy, so a recent re-attestation keeps its recency. Within a single
    document, ONE VALUE IS ONE ATTESTATION (r09c A1): repeated carriers of the same value —
    identical quotes, near-duplicate boilerplate, page headers — collapse to the
    first-maximal-covariate row (q2-105: twelve same-doc rows rode the group coarsening to
    0.989; correlated is not once). Across documents, value-ONLY quotes (no shared context)
    do not collapse: genuine independent corroboration must still accumulate. Order-preserving
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
    drop: set[int] = set()
    # r09c A1 — one document attests one value once: doc-keyed rows collapse per
    # (doc_key, value_norm) to the first-maximal-covariate row, whatever the quotes (the
    # boilerplate/page-repetition class evades any quote key; the doc-keyed group only
    # CORRELATES the copies, it does not count them once). Value-only rows (no doc_key)
    # are synthesised and out of scope here.
    best_by_doc_value: dict[tuple[str, str], int] = {}
    for i, (_quote, doc, vn, cov) in enumerate(rows):
        if not doc:
            continue
        key = (doc, vn)
        if key not in best_by_doc_value or cov > rows[best_by_doc_value[key]][3]:
            best_by_doc_value[key] = i
    drop.update(i for i, (_quote, doc, vn, _cov) in enumerate(rows)
                if doc and best_by_doc_value[(doc, vn)] != i)
    # The cross-document pass runs over the SURVIVORS.
    by_quote: dict[str, list[int]] = {}
    for i, (quote, _doc, _vn, _cov) in enumerate(rows):
        if i not in drop:
            by_quote.setdefault(_quote_key(quote), []).append(i)
    for qkey, idxs in by_quote.items():
        # Declared FIRST-SEEN order, not a set: `max` returns the first maximal element, so
        # at equal covariate the survivor is a function of the observations rather than of the
        # interpreter's per-process hash seed (M0.5 — the tie moved 24.5% of the recorded
        # battery's decisions between two runs of the same code on the same corpus).
        docs = list(dict.fromkeys(rows[i][1] for i in idxs))
        if len(docs) <= 1:
            continue  # a single document's survivors — A1 above already reduced them
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


# --- the utility fold (per-process, lazily) ----------------------------------------------

# The fold is memoised per fold_version (recomputed only when evidence moves); the cheap,
# pure per-shape scaling (decide.shaped_u_bar) is memoised separately per (fold_version,
# shape), so a second question's DIFFERENT shape never re-runs the fold.
_U_BAR_RAW: tuple[str, dict[str, float]] | None = None       # (fold_version, raw u_bar)
_U_BAR_SHAPED: dict[tuple[str, str], dict[str, float]] = {}  # (fold_version, shape) -> Ū


U_BAR_POLICY = "all-to-date"  # the decider's declared evidence regime (design §3.1, Q-O5)


def current_u_bar(*, shape: str = AS.DEFAULT_SHAPE) -> tuple[dict[str, float], str, str]:
    """Ū from the utility posterior (fold of model + elicitations + the verdict→evidence
    projection — the ``all-to-date`` regime, declared once above), SCALED for one
    question's answer ``shape`` (r30, `decide.shaped_u_bar` — the ONLY place a scale
    applies; C5). The fold is cached per fold version within the process — it is
    recomputed only when evidence moves, never when only ``shape`` changes, so every
    caller (the bridge's decider and its grow-menu pricing) can classify its own
    question and ask for its own shape at no extra cost. Returns
    ``(u_bar, fold_version, policy)``: the policy the fold ACTUALLY ran under, so a record
    stamps what was used, never an independent literal (M3, r13)."""
    global _U_BAR_RAW
    model = UT.load_model(config.UTILITY_MODEL)
    events: list[UT.Evidence] = list(
        UT.load_elicitations(config.UTILITY_ELICITATIONS, model))
    # §4.4 reaction loop: the owner's clean abstain-verdicts, joined to the decision log,
    # condition u(wrong). fold_version covers them, so a new verdict re-folds Ū demand-led.
    events += R.load_reactions(config.REACTIONS_LOG, config.DECISIONS_LOG)
    version = UT.fold_version(model, events, U_BAR_POLICY)
    if _U_BAR_RAW is None or _U_BAR_RAW[0] != version:
        post = UT.posterior(model, events, policy=U_BAR_POLICY)
        for warning in post.endpoint_warnings(model.endpoint_mass_warn):
            print(f"  ⚠ {warning}")
        _U_BAR_RAW = (version, post.u_bar())
    cache_key = (version, shape)
    if cache_key not in _U_BAR_SHAPED:
        _U_BAR_SHAPED[cache_key] = shaped_u_bar(_U_BAR_RAW[1], shape)
    return _U_BAR_SHAPED[cache_key], version, U_BAR_POLICY


# --- the family, end to end --------------------------------------------------------------

