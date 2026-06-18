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
``_A_ALTERNATIVES`` (effective wrong-value alternatives), ``_BETA_ANCESTRY`` /
``_BETA_MODEL`` (the §4.2 tempering exponents), ``_RHO_PRIOR_*`` (the
grounded-extraction reliability prior, moved by audit outcomes), ``_ORACLE_P``
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
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from life_agent.core import config
from life_agent.core import decisions as DEC
from life_agent.core import derivations as D
from life_agent.core import outcomes as O
from life_agent.core import reactions as R
from life_agent.core import utility as UT
from life_agent.core.brain import Brain
from life_agent.core.decide import u_assert

# The local model for route + extract (the 8 GB card's working model; both verdicts are
# cached, so call counts are bounded by distinct questions x distinct chunks).
LOOKUP_MODEL = "qwen2.5:7b-instruct"

ROUTE_PROMPT = """\
Classify this question. A LOOKUP asks for exactly ONE specific factual value that could
be read off a personal document: a number, ID, date, name, address, amount, or similar
point fact. NOT a lookup: anything needing summarising, listing, aggregating, comparing,
or explaining — and any question asking for MULTIPLE values at once (e.g. "lender,
amount, and end date" asks three).

If it IS a lookup, also classify the value's persistence. TIME-INDEXED means the value
is a current state that can change over a life: an address, phone number, employer,
salary, balance, status, expiry. NOT time-indexed means the value is permanent or
historical once set: a birth date, a national ID, the date an event happened.

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

# --- stated channel parameters (priors; calibration moves them — §2/§14) ---------------
_A_ALTERNATIVES = 10.0   # effective number of wrong values a misreport spreads over
_BETA_ANCESTRY = 0.3     # within one source document, m observations count as 1+beta*(m-1)
_BETA_MODEL = 0.7        # across documents (one shared extractor), G groups likewise
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
REASON_DISPERSED = "dispersed posterior"

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
    # than a blind "should you have answered?". Used when the posterior held ≥1 candidate.
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
                today: date | None = None) -> float:
    """The doc_date covariate on a_i: for a time-indexed construct, the probability a
    document's assertion is still current decays with document age (stated half-life).
    ``date_iso`` None = projected but unknown (undated/underived) — the stated marginal
    attenuation. Future-dated documents clamp to 1.0 (no covariate bonus)."""
    if not time_indexed:
        return 1.0
    if date_iso is None:
        return _A_TIME_UNKNOWN
    now = today if today is not None else datetime.now(UTC).date()
    age_years = max((now - date.fromisoformat(date_iso)).days, 0) / 365.25
    return float(0.5 ** (age_years / _TIME_HALF_LIFE_YEARS))


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


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _norm_value(value: str) -> str:
    return " ".join(value.split()).casefold()


_MONTH_NAMES: dict[str, int] = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _iso_or_none(y: int, mo: int, d: int) -> str | None:
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def _parse_date(value: str) -> str | None:
    """An ISO date string iff ``value`` is an UNAMBIGUOUS calendar date, else None. A numeric
    D/M/Y is parsed only when one of the first two components is > 12 (so day-vs-month is
    forced); a fully ambiguous numeric date (both <= 12) stays unparsed — keeping two such
    values as separate candidates is safer than risking a merge of two DIFFERENT dates."""
    v = " ".join(value.split())
    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", v)
    if m:
        return _iso_or_none(int(m[1]), int(m[2]), int(m[3]))
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})", v)
    if m and m[2].lower() in _MONTH_NAMES:
        return _iso_or_none(int(m[3]), _MONTH_NAMES[m[2].lower()], int(m[1]))
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", v)
    if m and m[1].lower() in _MONTH_NAMES:
        return _iso_or_none(int(m[3]), _MONTH_NAMES[m[1].lower()], int(m[2]))
    m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", v)
    if m:
        a, b, y = int(m[1]), int(m[2]), int(m[3])
        if a > 12 and b <= 12:
            return _iso_or_none(y, b, a)
        if b > 12 and a <= 12:
            return _iso_or_none(y, a, b)
    return None


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


def extractor_reliability(outcomes_path: Path = config.OUTCOMES_LOG) -> float:
    """rho for "this observation's value is the true V": the wide Beta(4,4) prior
    conditioned on the graded evidence — audit outcomes on the extract instrument, and
    the lookup eval's per-candidate claim outcomes (each candidate claim grades one
    observed value against ground truth; the none-claim grades the posterior, not the
    instrument, and is excluded). Only outcomes carrying the CURRENT extract instrument
    hash condition (§2 — reliability is per exact identity; a prompt change starts the
    new instrument at the prior, and events predating the hash field stay with their
    old instrument). The system learns whether to trust its own extractor from its own
    outcomes log — the §8 loop, closed."""
    current = extract_instrument_hash()
    correct = 0
    n = 0
    for event in O.read(outcomes_path):
        if event.instrument_identity.get("extract_prompt_hash") != current:
            continue
        producer = event.instrument_identity.get("producer_name")
        if event.grader == "audit" and producer == "life_agent.ask.lookup_extract":
            n += 1
            correct += event.grade in O.CORRECT_GRADES["audit"]
        elif (event.grader == "eval_lookup"
                and producer == "life_agent.ask.lookup_answer"
                and event.claim != _NONE_CLAIM):
            n += 1
            correct += event.grade in O.CORRECT_GRADES["eval_lookup"]
    return (_RHO_PRIOR_A + correct) / (_RHO_PRIOR_A + _RHO_PRIOR_B + n)


# --- route + observe (cached local-model instruments, the subject.py pattern) ----------

def _client() -> Any:
    from pkm.transforms._shared import make_model_client

    return make_model_client({
        "provider": "ollama", "model": LOOKUP_MODEL,
        "inference_params": {"temperature": 0.0},
    })


def route_question(root: Path, question: str, *,
                   client: Any | None = None) -> Route | None:
    """The cached route verdict: the Route (construct + time-indexedness) if this is
    a typed lookup, else None. A verdict outside the schema raises and is never
    recorded."""
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
                 ) -> tuple[list[Observation], int]:
    """One grounded extraction per hit (cached). Returns (grounded observations,
    indeterminate count). Indeterminate = the instrument returned ⊥ (not found) or its
    quote failed the grounding gate — recorded either way, counted, never silently
    dropped (§4.2's indeterminacy term). ``covariates`` carries the §4.1 doc_subject /
    doc_date factors into each observation's a_i."""
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
                                time_indexed=time_indexed, today=today)
                    if artifact_key in cov.doc_date else 1.0)
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


def temper_scales(observations: list[Observation]) -> list[float]:
    """§4.2's lineage temper, per observation: within an ancestry group of size m the
    group counts as 1 + beta_anc*(m-1) effective observations; across the G groups (every
    observation shares the one extractor's model identity) the groups count as
    1 + beta_mod*(G-1). Single observation ⇒ scale 1 — no phantom discount."""
    groups: dict[str, int] = {}
    for o in observations:
        groups[o.artifact_cache_key] = groups.get(o.artifact_cache_key, 0) + 1
    n_groups = len(groups)
    s_mod = ((1.0 + _BETA_MODEL * (n_groups - 1)) / n_groups) if n_groups else 1.0
    scales: list[float] = []
    for o in observations:
        m = groups[o.artifact_cache_key]
        s_anc = (1.0 + _BETA_ANCESTRY * (m - 1)) / m
        scales.append(s_anc * s_mod)
    return scales


def observation_densities(observation: Observation, candidates: list[str],
                          rho: float, scale: float) -> list[list[float]]:
    """The tempered tabular_log_density rows for one observation: source atoms are the
    K candidates + NONE (last), target atoms the K candidate indices. With reliability
    r = rho * a_i (authority composed with the §4.1 subject/time covariates), a match
    carries r + (1-r)/A and any miss (1-r)/A — NONE misses everything (§4.2's noisy
    channel)."""
    r = (rho * observation.authority
         * observation.subject_factor * observation.time_factor)
    log_match = scale * math.log(max(r + (1.0 - r) / _A_ALTERNATIVES, _PROB_EPS))
    log_miss = scale * math.log(max((1.0 - r) / _A_ALTERNATIVES, _PROB_EPS))
    k = len(candidates)
    # row j (hypothesis V = candidate j): the observation reports j with the match
    # probability and anything else with the miss probability; the NONE row (last)
    # never matches — under "the truth is not among the retrieved", every observation
    # is a misreport.
    rows = [[log_match if t == j else log_miss for t in range(k)] for j in range(k)]
    rows.append([log_miss] * k)
    return rows


def lookup_posterior(brain: Brain, observations: list[Observation],
                     candidates: list[str], rho: float) -> tuple[list[float], str]:
    """Condition the candidate+NONE categorical on every observation (in hit order —
    the canonical order), tempered per §4.2. Returns (weights with NONE last, the live
    state id — still open for `optimise`; the caller destroys it)."""
    k = len(candidates)
    atoms = [float(j) for j in range(k + 1)]
    # stated prior: _P_NONE_PRIOR on none-of-the-retrieved, the rest uniform over
    # candidates (the complement of an unproven extraction channel)
    prior = [(1.0 - _P_NONE_PRIOR) / k] * k + [_P_NONE_PRIOR]
    state_id = brain.create_state({
        "type": "categorical",
        "space": {"type": "finite", "values": atoms},
        "log_weights": [math.log(w) for w in prior],
    })
    scales = temper_scales(observations)
    keys = [_candidate_key(c) for c in candidates]
    for o, scale in zip(observations, scales, strict=True):
        kernel = {"type": "tabular_log_density",
                  "source_vals": atoms,
                  "target_vals": [float(t) for t in range(k)],
                  "densities": observation_densities(o, candidates, rho, scale)}
        brain.condition(state_id, kernel=kernel,
                        observation=float(keys.index(_candidate_key(o.value_raw))))
    weights = brain.weights(state_id)
    return weights, state_id


def action_utilities(weights: list[float], u_bar: dict[str, float],
                     p_attested: float) -> dict[str, list[float]]:
    """Per-action utility vectors over the hypothesis atoms (K candidates + NONE),
    under the §4.4 posterior mean (the collapse theorem). The correctness slots derive
    from :func:`life_agent.core.decide.u_assert` (the one written atom): report asserts
    the MAP candidate (``u_assert(1)``); every other atom and NONE is a wrong report
    (``u_assert(0)`` = u_wrong); hedge asserts the candidate set (``u_hedged``), misleading
    only when the truth is NONE; ask_clarify is the oracle price (NOT a u_assert outcome —
    the oracle is infallible when it knows); abstain is the gauge zero.

    ``report_scoped`` (scoped-claims design) asserts a TRUE time-scoped claim ("as of
    <date>, X"). Its truth is about the *record*, not which current-value hypothesis holds,
    so its row is **flat** — the optimise values it at exactly
    ``p_attested*u_hedged + (1-p_attested)*u_wrong_scoped`` whatever the V_now posterior. A
    miss is a citable misread (``u_wrong_scoped``), never the catastrophic current-value
    ``u_wrong``. ``p_attested`` = P(the record attests the scoped value), the caller's
    recency-off leader weight (0.0 ⇒ no datable record ⇒ the row stays below abstain)."""
    k = len(weights) - 1
    j_star = max(range(k), key=lambda j: weights[j]) if k else None
    u_correct_report = u_assert(1.0, u_bar)
    u_wrong_report = u_assert(0.0, u_bar)
    report = [(u_correct_report if j == j_star else u_wrong_report) for j in range(k)]
    report.append(u_wrong_report)  # NONE: the report misleads
    hedge = [u_bar["u_hedged"]] * k + [u_wrong_report]
    ask = [_ORACLE_P * u_bar["u_correct"] - u_bar["lambda_int"]] * (k + 1)
    abstain = [u_bar["u_abstain"]] * (k + 1)
    scoped_eu = p_attested * u_bar["u_hedged"] + (1.0 - p_attested) * u_bar["u_wrong_scoped"]
    report_scoped = [scoped_eu] * (k + 1)
    return {"report": report, "report_scoped": report_scoped,
            "hedge": hedge, "ask_clarify": ask, "abstain": abstain}


def decide(brain: Brain, state_id: str, weights: list[float],
           u_bar: dict[str, float], p_attested: float = 0.0) -> tuple[str, float]:
    """`optimise` over the response actions (M4) on the live posterior state. ``p_attested``
    prices the report_scoped action (0.0 ⇒ no datable record ⇒ scoped never wins)."""
    utilities = action_utilities(weights, u_bar, p_attested)
    preference = {
        "type": "functional_per_action",
        "actions": {str(i): {"type": "tabular", "values": utilities[name]}
                    for i, name in enumerate(_ACTION_ORDER)},
    }
    actions = {"type": "finite", "values": [float(i) for i in range(len(_ACTION_ORDER))]}
    action_value, eu = brain.optimise(state_id, actions=actions, preference=preference)
    return _ACTION_ORDER[int(action_value)], eu


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
        body = GRAMMAR["abstain"].format(reason=REASON_DISPERSED)
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
                   candidates: list[str], rho: float, *,
                   weights_current: list[float], time_indexed: bool,
                   ) -> tuple[float, str | None, str | None]:
    """The report_scoped inputs (scoped-claims design): the freshest DATED observation gives
    the scoped value V_s ("most recent record on file") and its as-of date; ``p_attested`` =
    V_s's RECENCY-OFF posterior weight — what the record attests, ignoring currency. Returns
    ``(p_attested, V_s, as_of)``; ``p_attested`` is 0.0 (scoped disabled — the flat row sits
    below abstain) when no observation carries a date. The attested posterior is the current
    one when recency was already off (a permanent fact), else a second pass with the time
    decay removed — pure credence math, no new model calls."""
    dated = [o for o in observations if o.doc_date]
    if not dated:
        return 0.0, None, None
    freshest = max(dated, key=lambda o: o.doc_date or "")  # ISO dates sort lexicographically
    if time_indexed:
        attested_obs = [dataclasses.replace(o, time_factor=1.0) for o in observations]
        weights_attested, sid = lookup_posterior(brain, attested_obs, candidates, rho)
        brain.destroy_state(sid)
    else:
        weights_attested = weights_current
    keys = [_candidate_key(c) for c in candidates]
    p_attested = weights_attested[keys.index(_candidate_key(freshest.value_raw))]
    return p_attested, freshest.value_raw, freshest.doc_date


def decide_and_record(root: Path, question: str, construct: str,
                      observations: list[Observation], indeterminate: int, *,
                      n_hits: int, time_indexed: bool,
                      brain: Brain | None = None,
                      decisions_path: Path | None = None,
                      run_id: str = "ask",
                      rho_override: float | None = None) -> LookupResult:
    """The lookup family's tail: a grounded observation set → tempered posterior → EU
    decision under Ū → recorded answer artifact (§18.9) + logged decision (§8). Shared by
    the single-pass :func:`lookup_answer` and the gather-augmented loop
    (:mod:`life_agent.core.gather`): both produce observations, then value and record them
    identically. ``time_indexed`` enters the answer key + content (an auditable decision
    input — the gather loop may set it differently from the route). Assumes
    ``observations`` is non-empty (its caller routes the empty case to narrative).

    ``rho_override`` replaces the local-extractor reliability for an observation set produced
    by a DIFFERENT instrument (the ``extract@<model>`` joint edge folds its calibrated
    confidence here, not the local ``extractor_reliability``)."""
    b = brain if brain is not None else shared_brain()
    u_bar, fold_ver = current_u_bar(b)
    rho = rho_override if rho_override is not None else extractor_reliability()
    candidates = candidates_from(observations)
    weights, state_id = lookup_posterior(b, observations, candidates, rho)
    p_attested, scoped_value, as_of = _scoped_option(
        b, observations, candidates, rho,
        weights_current=weights, time_indexed=time_indexed)
    try:
        action, eu = decide(b, state_id, weights, u_bar, p_attested)
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
         "time_factor": o.time_factor}
        for o in observations]
    params = {"A": _A_ALTERNATIVES, "beta_ancestry": _BETA_ANCESTRY,
              "beta_model": _BETA_MODEL, "oracle_p": _ORACLE_P,
              "p_none_prior": _P_NONE_PRIOR, "rho": rho,
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
    D.record(root, akey, content,
             lineage=[{"cache_key": o.obs_cache_key, "role": "observation"}
                      for o in observations])

    result = LookupResult(
        question=question, construct=construct, action=action, eu=eu,
        candidates=cands, credences=creds, p_none=p_none,
        observations=tuple(observations), n_hits=n_hits,
        n_indeterminate=indeterminate, utility_fold_version=fold_ver,
        answer_cache_key=akey.cache_key, rendered="",
        as_of=as_of, scoped_value=scoped_value, scoped_p=p_attested)
    result = dataclasses.replace(result, rendered=render(result))

    DEC.append(decisions_path if decisions_path is not None else config.DECISIONS_LOG,
               DEC.DecisionEvent(
                   tx_time=O.now_iso(), run_id=run_id,
                   question_id=_sha(question)[:16],
                   family="lookup",
                   action_set=_ACTION_ORDER,
                   posterior_summary={
                       "candidates": list(cands), "credences": list(creds),
                       "p_none": p_none, "n_obs": len(observations),
                       "n_indeterminate": indeterminate,
                   },
                   utility_fold_version=fold_ver,
                   chosen_action=action, predicted_eu=eu,
                   decision_id=akey.cache_key))
    return result


def lookup_answer(root: Path, question: str, hits: list[dict[str, Any]], *,
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
    :func:`life_agent.core.gather.gather_answer`; both share :func:`decide_and_record`."""
    route = route_question(root, question, client=route_client)
    if route is None:
        return None
    observations, indeterminate = observe_hits(root, question, hits,
                                               client=extract_client,
                                               covariates=covariates,
                                               time_indexed=route.time_indexed)
    if not observations:
        return None
    return decide_and_record(
        root, question, route.construct, observations, indeterminate,
        n_hits=len(hits), time_indexed=route.time_indexed, brain=brain,
        decisions_path=decisions_path, run_id=run_id)
