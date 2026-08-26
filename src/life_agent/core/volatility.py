"""Per-construct volatility — the world-knowledge prior on how fast an attribute changes.

A *volatile* attribute's attestation decays with document age (the `lookup.time_factor` recency
covariate); a *permanent* one does not. The HALF-LIFE — years to a ~50% chance the value has
changed — is a **world-knowledge prior**: the model already knows a date of birth never changes and
a phone number changes every few years (elicited 2026-06-19 from the answer model: DOB / national-id
≈ permanent, passport / email ≈ 10y, phone ≈ 8, address ≈ 7, employer ≈ 4, salary ≈ 2). It is a
prior, not a fact (a specific person may move yearly); the corpus's own evidence can refine it.

v0 reads a keyword-classified seed of that elicitation — deterministic and offline, which keeps the
eval reproducible. The named successor is an LLM-elicited half-life **cached per construct** (the
same world-knowledge prior, generalised to any construct string) — a content-addressed derivation
like any other; the keyword seed is the cold-start.

This never reaches the credence brain: the bridge folds the half-life into each observation's
`time_factor` (the parity boundary — the brain sees only the already-multiplied covariate). It is
the *currency* axis, distinct from *reliability* (calibrated from verdicts): a faithful read of a
stale document is reliable but not current — two mechanisms, two knowledge sources.
"""
from __future__ import annotations

PERMANENT = 9999.0   # a permanent fact (DOB, national id): 0.5^(age/9999) ≈ 1 ⇒ no decay
DEFAULT = 5.0        # current-state half-life for an unclassified construct (the global default)

# keyword groups → half-life in years (the elicited world-knowledge prior). Checked IN ORDER; the
# first group with a keyword substring-present in the (lower-cased) construct wins, so a more
# specific group precedes a more general one (passport before the permanent national-id group, so
# "passport number" is decayable, not permanent).
_SEED: tuple[tuple[tuple[str, ...], float], ...] = (
    (("birth", "dob", "born"), PERMANENT),
    (("passport",), 10.0),
    (("national id", "id number", "identity number", "identity card", "social security", "ssn",
      "tax id", "tax number"), PERMANENT),
    (("email",), 10.0),
    (("phone", "mobile", "cell", "telephone", "whatsapp"), 8.0),
    (("address", "residence", "street", "home"), 7.0),
    (("marital", "marriage", "spouse"), 15.0),
    (("visa", "permit", "immigration", "residency status"), 3.0),
    (("bank", "iban", "account number"), 8.0),
    (("employer", "company", "workplace", "occupation", "job", "title"), 4.0),
    (("salary", "income", "wage", "compensation"), 2.0),
)


def half_life(construct: str | None) -> float:
    """[§3.3 · V-1] The construct's volatility half-life in years. A permanent
    attribute → ``PERMANENT`` (no
    decay); a volatile one → its world-knowledge half-life; an unclassified construct → ``DEFAULT``
    (the global current-state half-life). Pure, deterministic — the v0 keyword seed."""
    if not construct:
        return DEFAULT
    c = construct.lower()
    for keywords, hl in _SEED:
        if any(kw in c for kw in keywords):
            return hl
    return DEFAULT
