"""life_agent.bridge — the capability bridge: evidence shaping and the decider, over HTTP.

Two pieces:

- :mod:`life_agent.bridge.observations` — the **parity boundary**:
  :func:`~life_agent.bridge.observations.to_abstract_observations` maps grounded observations to
  the abstract integer/float form the decider reasons over; the decider never sees a candidate
  string.
- :mod:`life_agent.bridge.server` — the **capability bridge**: a JSON-over-HTTP service
  (`POST /route /retrieve /extract /probe/* /decide /log_*`, `GET /utility /ready`), each
  endpoint a thin wrapper of an existing tested read. The bridge gathers and shapes evidence;
  ``/decide`` runs the host decider (:mod:`life_agent.core.decider`). The owner profile and
  utility are read server-side and never cross the wire.
"""
