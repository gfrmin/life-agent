"""life_agent.tasks — the action faculty: email → grounded GTD tasks (M2).

A thin **projection** of pkm's grounded extraction into the mutable GTD store:
``read.py`` queries the newest cached ``action_items`` artifact per email and
traces each to its source (Message-ID); ``project.py`` files every not-yet-open
assertion once into the in-tree jarvis inbox with a ``[src:email <Message-ID>]``
citation. "Already handled" is a property of an append-only **event ledger**
(``events.py``) — the task set is ``fold(ledger)``, keyed on a content+grounding
assertion identity — not a marker file. No pkm changes: the grounded extraction
lives in pkm; only the immutable→mutable bridge lives here.
"""
