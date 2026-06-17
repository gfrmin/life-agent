"""life_agent.bridge — the capability bridge to the answer-brain body (Stage 2).

The answer-brain (credence `apps/answer-brain`) is a pi-mono agent that answers by governing
gather/answer/ask/abstain through a credence brain. Its tools reach this repo's retrieval,
extraction, and probes over a small JSON service (pi-mono has no MCP client — move-2-design §5 Q1).

Two pieces:

- :mod:`life_agent.bridge.observations` — the **parity boundary, Python side** (Move 2):
  :func:`~life_agent.bridge.observations.to_abstract_observations` maps grounded observations to
  the abstract integer/float form the brain reasons over; the brain never sees a candidate string.
- :mod:`life_agent.bridge.server` — the **capability bridge** (Move 3): a stateless
  JSON-over-HTTP service (`POST /route /retrieve /extract /probe/{recency,subject,authority,
  corroborate}`, `GET /utility /ready`), each endpoint a thin wrapper of an existing tested read.
  The bridge gathers and shapes evidence; the daemon (`/decide`, Move 2) decides. It holds no
  posterior and no per-question state; the owner profile + utility are read server-side and never
  cross the wire; `/extract` returns exactly ``to_abstract_observations``'s output, so the daemon
  receives the shape its parity tests pin. The pi-mono body + app + end-to-end gate are Move 4.
"""
