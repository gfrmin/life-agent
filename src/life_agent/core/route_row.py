"""The route row, measured: what attempting a question is worth given the router's verdict.

Before any retrieval the router says whether the question has one specific value to read off
a document (a lookup) or is a list, an aggregate, a summary or several values at once. That
verdict is an OBSERVATION of the answer type, and the decider
(:func:`life_agent.core.decide.route_options`) prices attempting the question from it. The
numbers, all read from ``u_bar``:

- ``route_q@accept`` / ``route_q@reject``: P(the question truly has a single-span answer | the
  router's verdict), one per verdict, a Beta(1, 1) posterior mean over the labelled route
  audit (label x verdict counts);
- ``route_right`` / ``route_wrong``: the measured right / wrong rates of attempted lookups
  (a Dirichlet(2, 2, 2) posterior mean over the pinned typed archives; the remainder declines);
- ``route_wrong_other``: the wrong rate of attempting a question whose answer is not a span.
  Nothing measures it: the fit sets it to ``route_wrong``, the ASSUMPTION that such a question
  is committed wrong as often as a lookup is. It is never right;
- ``route_price``: the first pass's price in utility. Not stored in a row: the caller converts
  the declared dollars (:data:`life_agent.core.pricing.FIRST_PASS_USD`) with ``lambda_usd`` and
  the decider sets the key from the request.

The fit is ``scripts/fit_route_row.py``. The starting row for a KB with no fit is the shipped
:data:`EXAMPLE`; with neither file, the decider reads :data:`PRIOR`.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

#: This row's prefix in ``u_bar``.
PREFIX = "route"

RIGHT_KEY = f"{PREFIX}_right"
WRONG_KEY = f"{PREFIX}_wrong"
WRONG_OTHER_KEY = f"{PREFIX}_wrong_other"

#: The first pass's price in utility, set per request by the decider (not fitted).
PRICE_KEY = f"{PREFIX}_price"

#: The router's two verdicts, as ``q_key`` names them.
VERDICTS: dict[bool, str] = {True: "accept", False: "reject"}


def q_key(lookup: bool) -> str:
    """The u_bar key of P(single-span answer | the router's verdict ``lookup``)."""
    return f"{PREFIX}_q@{VERDICTS[lookup]}"


#: The fitted keys (the price is not one of them).
KEYS: tuple[str, ...] = (q_key(True), q_key(False), RIGHT_KEY, WRONG_KEY, WRONG_OTHER_KEY)

#: What an unmeasured row reads: the Beta(1, 1) mean 1/2 for each ``q`` (the router is no
#: evidence at all) and the Dirichlet(2, 2, 2) mean 1/3 for each outcome rate. At
#: ``u_wrong = -9`` this prices attempting at about ``-2.8`` under either verdict, so the
#: decider DECLINES EVERY QUESTION: an unmeasured attempt is as likely to be wrong as right.
#: That is why a KB with no fit starts from the shipped row, never from this prior.
PRIOR: dict[str, float] = {q_key(True): 0.5, q_key(False): 0.5, RIGHT_KEY: 1 / 3,
                           WRONG_KEY: 1 / 3, WRONG_OTHER_KEY: 1 / 3}

#: The row shipped with the repo, fitted on the author's corpus and published as aggregate
#: rates (no question, document or value is recoverable from five rates). It is the STARTING
#: row for a KB that has recorded nothing yet, see :func:`load`.
EXAMPLE = Path(__file__).resolve().parents[3] / "config" / "route-row.example.json"


def _row(path: Path) -> dict[str, float]:
    row = json.loads(path.read_text(encoding="utf-8"))["row"]
    return {k: float(row[k]) for k in KEYS}


def load(path: Path) -> dict[str, float]:
    """The fitted row recorded at ``path`` as u_bar keys.

    A KB with no fit falls back to the shipped row (:data:`EXAMPLE`), because the prior
    declines every question (:data:`PRIOR`): a fresh clone must be able to attempt what the
    router accepts. The fallback is a starting point, not a claim about your corpus;
    ``scripts/fit_route_row.py`` replaces it with your own. Returns ``{}`` only when neither
    file exists, and then the decider reads :data:`PRIOR`: stated, never silent.
    """
    if path.is_file():
        return _row(path)
    return _row(EXAMPLE) if EXAMPLE.is_file() else {}


def as_u_bar(q_accept: float, q_reject: float, right: float, wrong: float) -> dict[str, float]:
    """The fitted row's u_bar keys; ``route_wrong_other`` is set to ``wrong`` (the stated
    assumption in the module docstring)."""
    return {q_key(True): q_accept, q_key(False): q_reject, RIGHT_KEY: right,
            WRONG_KEY: wrong, WRONG_OTHER_KEY: wrong}


def beta_mean(hits: int, n: int) -> float:
    """The Beta(1, 1) posterior mean of a rate seen ``hits`` times in ``n``."""
    return (hits + 1.0) / (n + 2.0)


def dirichlet_means(counts: Mapping[str, int], *, alpha: float = 2.0) -> dict[str, float]:
    """The Dirichlet(alpha, ..) posterior mean of each outcome's rate."""
    total = sum(counts.values()) + alpha * len(counts)
    return {o: (c + alpha) / total for o, c in counts.items()}
