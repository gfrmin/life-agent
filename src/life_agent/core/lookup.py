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
(the owner-as-oracle prior for pricing ask_clarify), and the declared source-authority
classes (§4.1's v0 lattice).
"""
from __future__ import annotations

import atexit
import dataclasses
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from life_agent.core import config
from life_agent.core import decisions as DEC
from life_agent.core import derivations as D
from life_agent.core import outcomes as O
from life_agent.core import utility as UT
from life_agent.core.brain import Brain

# The local model for route + extract (the 8 GB card's working model; both verdicts are
# cached, so call counts are bounded by distinct questions x distinct chunks).
LOOKUP_MODEL = "qwen2.5:7b-instruct"

ROUTE_PROMPT = """\
Classify this question. A LOOKUP asks for one specific factual value that could be
read off a personal document: a number, ID, date, name, address, amount, or similar
point fact. Anything needing summarising, listing, aggregating, comparing, or
explaining is NOT a lookup.

QUESTION: {question}

Reply with JSON only:
{{"lookup": true, "construct": "<3-8 words naming the value asked for>"}}
or {{"lookup": false}}
"""

ROUTE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["lookup"],
    "properties": {
        "lookup": {"type": "boolean"},
        "construct": {"type": "string"},
    },
}

EXTRACT_PROMPT = """\
You are extracting ONE value from a document excerpt, if it is present.

QUESTION: {question}

EXCERPT:
{chunk}

If the excerpt contains a specific value that answers the question, reply with JSON:
{{"found": true, "value": "<the value, concise>", \
"quote": "<verbatim text copied from the excerpt containing the value>"}}
If it does not, reply: {{"found": false}}
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
_RHO_PRIOR_A = 17.0      # grounded-extraction reliability prior Beta(17,3): mean 0.85
_RHO_PRIOR_B = 3.0       # (post-surgery residual: wrong quote selected, quote misread)
_ORACLE_P = 0.9          # owner-as-oracle prior mean for pricing ask_clarify (§4.4)
_PROB_EPS = 1e-12

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

# The response actions, in the optimise action-space order. Names are the
# decisions.ACTIONS vocabulary; ask-about-U is deliberately absent (§4.4).
_ACTION_ORDER: tuple[str, ...] = ("report", "hedge", "ask_clarify", "abstain")

# Closed abstention reasons (the credence grammar — interaction contract).
REASON_DISPERSED = "dispersed posterior"

# One grammar table for every rendered string (drift-gated; interaction contract).
# Credences render at three decimals: two rounded 0.997 up to "1.00" on the first live
# answer — a certainty the posterior never asserted (presentation error, §3).
GRAMMAR: dict[str, str] = {
    "report": "{value} — credence {p:.3f} {cites}",
    "hedge": "Unresolved — candidates: {alts}",
    "ask_clarify": "Worth asking you directly — the evidence does not settle it: {alts}",
    "abstain": "No answer asserted ({reason}).",
    "footer": ("lookup: {n_hits} hits → {n_obs} grounded observations"
               " · {n_ind} indeterminate · none-of-retrieved {p_none:.3f}"
               " · decision {action} (EU {eu:.2f})"),
    "fallthrough": "(lookup: {reason} — narrative path)",
}


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


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _norm_value(value: str) -> str:
    return " ".join(value.split()).casefold()


def _grounded(quote: str, chunk: str) -> bool:
    """Whitespace-normalised verbatim containment (the action_items precedent)."""
    return " ".join(quote.split()) in " ".join(chunk.split())


def authority_for(origin: str) -> tuple[str, float]:
    """The declared v0 authority class for a hit's origin path (stated prior)."""
    low = origin.casefold()
    if any(marker in low for marker in _AUTHORITY_MAIL_MARKERS):
        return ("email", 0.90)
    for extensions, name, value in _AUTHORITY_CLASSES:
        if low.endswith(extensions):
            return (name, value)
    return _AUTHORITY_DEFAULT


def extractor_reliability(outcomes_path: Path = config.OUTCOMES_LOG) -> float:
    """rho for the lookup extractor: the Beta(17,3) grounded-extraction prior, moved by
    audit-grader outcomes attributed to this instrument (none exist yet — the prior
    carries v0, exactly as stated in §2)."""
    correct = 0
    n = 0
    for event in O.read(outcomes_path):
        if (event.grader == "audit"
                and event.instrument_identity.get("producer_name")
                == "life_agent.ask.lookup_extract"):
            n += 1
            correct += event.grade in O.CORRECT_GRADES["audit"]
    return (_RHO_PRIOR_A + correct) / (_RHO_PRIOR_A + _RHO_PRIOR_B + n)


# --- route + observe (cached local-model instruments, the subject.py pattern) ----------

def _client() -> Any:
    from pkm.transforms._shared import make_model_client

    return make_model_client({
        "provider": "ollama", "model": LOOKUP_MODEL,
        "inference_params": {"temperature": 0.0},
    })


def route_question(root: Path, question: str, *,
                   client: Any | None = None) -> str | None:
    """The cached route verdict: the construct name if this is a typed lookup, else
    None. A verdict outside the schema raises and is never recorded."""
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
    return str(parsed.get("construct") or "the asked value")


def observe_hits(root: Path, question: str, hits: list[dict[str, Any]], *,
                 client: Any | None = None,
                 reliability: float | None = None,
                 ) -> tuple[list[Observation], int]:
    """One grounded extraction per hit (cached). Returns (grounded observations,
    indeterminate count). Indeterminate = the instrument returned ⊥ (not found) or its
    quote failed the grounding gate — recorded either way, counted, never silently
    dropped (§4.2's indeterminacy term)."""
    if client is None:
        client = _client()
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
            quote = str(raw.get("quote") or "")
            grounded = found and _grounded(quote, chunk)
            parsed = {"format_version": 1, "found": found,
                      "value": str(raw.get("value") or ""), "quote": quote,
                      "grounded": grounded}
            D.record(root, key,
                     json.dumps(parsed, sort_keys=True,
                                ensure_ascii=False).encode("utf-8"),
                     lineage=[{"cache_key": str(hit["artifact_cache_key"]),
                               "role": "source"}])
        if not (parsed.get("found") and parsed.get("grounded")):
            indeterminate += 1
            continue
        klass, authority = authority_for(str(hit.get("origin", "")))
        observations.append(Observation(
            card_n=i + 1,
            artifact_cache_key=str(hit["artifact_cache_key"]),
            obs_cache_key=key.cache_key,
            value_raw=str(parsed["value"]).strip(),
            value_norm=_norm_value(str(parsed["value"])),
            quote=str(parsed["quote"]),
            authority_class=klass,
            authority=authority,
        ))
    return observations, indeterminate


# --- the posterior (pure builders; conditioning through the credence skin) -------------

def candidates_from(observations: list[Observation]) -> list[str]:
    """Distinct candidate values in first-seen order; display form = first raw form."""
    seen: dict[str, str] = {}
    for o in observations:
        seen.setdefault(o.value_norm, o.value_raw)
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
    r = rho*authority, a match carries r + (1-r)/A and any miss (1-r)/A — NONE misses
    everything (§4.2's noisy channel)."""
    r = rho * observation.authority
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
    prior = [1.0 / (k + 1)] * (k + 1)  # stated: uniform over candidates + NONE
    state_id = brain.create_state({
        "type": "categorical",
        "space": {"type": "finite", "values": atoms},
        "log_weights": [math.log(w) for w in prior],
    })
    scales = temper_scales(observations)
    norms = [_norm_value(c) for c in candidates]
    for o, scale in zip(observations, scales, strict=True):
        kernel = {"type": "tabular_log_density",
                  "source_vals": atoms,
                  "target_vals": [float(t) for t in range(k)],
                  "densities": observation_densities(o, candidates, rho, scale)}
        brain.condition(state_id, kernel=kernel,
                        observation=float(norms.index(o.value_norm)))
    weights = brain.weights(state_id)
    return weights, state_id


def action_utilities(weights: list[float], u_bar: dict[str, float]
                     ) -> dict[str, list[float]]:
    """Per-action utility vectors over the hypothesis atoms (K candidates + NONE),
    under the §4.4 posterior mean (the collapse theorem). report asserts the MAP
    candidate; hedge asserts the candidate set (misleading iff the truth is NONE);
    ask_clarify is priced flat by the oracle prior against λ_int; abstain is the
    gauge zero."""
    k = len(weights) - 1
    j_star = max(range(k), key=lambda j: weights[j]) if k else None
    u_wrong = u_bar["u_wrong"]
    report = [(u_bar["u_correct"] if j == j_star else u_wrong) for j in range(k)]
    report.append(u_wrong)  # NONE: the report misleads
    hedge = [u_bar["u_hedged"]] * k + [u_wrong]
    ask = [_ORACLE_P * u_bar["u_correct"] - u_bar["lambda_int"]] * (k + 1)
    abstain = [u_bar["u_abstain"]] * (k + 1)
    return {"report": report, "hedge": hedge, "ask_clarify": ask, "abstain": abstain}


def decide(brain: Brain, state_id: str, weights: list[float],
           u_bar: dict[str, float]) -> tuple[str, float]:
    """`optimise` over the response actions (M4) on the live posterior state."""
    utilities = action_utilities(weights, u_bar)
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
        by_value.setdefault(_norm_value(o.value_raw), []).append(o.card_n)

    def _cites(value: str) -> str:
        ns = sorted(set(by_value.get(_norm_value(value), [])))
        return "".join(f"[{n}]" for n in ns)

    alts = " · ".join(
        f"{v} ({p:.3f}) {_cites(v)}".rstrip()
        for v, p in zip(result.candidates, result.credences, strict=True))
    if result.action == "report":
        v = result.candidates[0]
        body = GRAMMAR["report"].format(value=v, p=result.credences[0],
                                        cites=_cites(v))
    elif result.action == "hedge":
        body = GRAMMAR["hedge"].format(alts=alts)
    elif result.action == "ask_clarify":
        body = GRAMMAR["ask_clarify"].format(alts=alts)
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
    version = UT.fold_version(model, events)
    if _U_BAR is not None and _U_BAR[0] == version:
        return _U_BAR[1], version
    post = UT.posterior(brain, model, events)
    for warning in post.endpoint_warnings(model.endpoint_mass_warn):
        print(f"  ⚠ {warning}")
    _U_BAR = (version, post.u_bar())
    return _U_BAR[1], version


# --- the family, end to end --------------------------------------------------------------

def lookup_answer(root: Path, question: str, hits: list[dict[str, Any]], *,
                  brain: Brain | None = None,
                  route_client: Any | None = None,
                  extract_client: Any | None = None,
                  decisions_path: Path | None = None,
                  run_id: str = "ask",
                  ) -> LookupResult | None:
    """Run the lookup family over admitted hits. None ⇒ the narrative path answers
    (not routed as a lookup, or zero grounded observations — a coverage statement,
    not an abstention; the caller names the fallthrough)."""
    construct = route_question(root, question, client=route_client)
    if construct is None:
        return None
    observations, indeterminate = observe_hits(root, question, hits,
                                               client=extract_client)
    if not observations:
        return None

    b = brain if brain is not None else shared_brain()
    u_bar, fold_ver = current_u_bar(b)
    rho = extractor_reliability()
    candidates = candidates_from(observations)
    weights, state_id = lookup_posterior(b, observations, candidates, rho)
    try:
        action, eu = decide(b, state_id, weights, u_bar)
    finally:
        b.destroy_state(state_id)

    # posterior order for rendering: candidates by weight, NONE mass separate
    order = sorted(range(len(candidates)), key=lambda j: weights[j], reverse=True)
    cands = tuple(candidates[j] for j in order)
    creds = tuple(weights[j] for j in order)
    p_none = weights[-1]

    # the answer artifact (§18.9): claim set + posterior + decision inputs, lineage to
    # every observation — the lookup family's computation stays on the ledger
    params = {"A": _A_ALTERNATIVES, "beta_ancestry": _BETA_ANCESTRY,
              "beta_model": _BETA_MODEL, "oracle_p": _ORACLE_P, "rho": rho}
    obs_hash = _sha(json.dumps(sorted(o.obs_cache_key for o in observations)))
    akey = D.lookup_answer_key(question, obs_hash, fold_ver, params)
    content = json.dumps({
        "format_version": 1, "question": question, "construct": construct,
        "candidates": list(cands), "credences": list(creds), "p_none": p_none,
        "action": action, "eu": eu, "utility_fold_version": fold_ver,
    }, sort_keys=True, ensure_ascii=False).encode("utf-8")
    D.record(root, akey, content,
             lineage=[{"cache_key": o.obs_cache_key, "role": "observation"}
                      for o in observations])

    result = LookupResult(
        question=question, construct=construct, action=action, eu=eu,
        candidates=cands, credences=creds, p_none=p_none,
        observations=tuple(observations), n_hits=len(hits),
        n_indeterminate=indeterminate, utility_fold_version=fold_ver,
        answer_cache_key=akey.cache_key, rendered="")
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
                   chosen_action=action, predicted_eu=eu))
    return result
