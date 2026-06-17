"""life_agent.bridge — the capability bridge to the answer-brain body (Stage 2).

The answer-brain (credence `apps/answer-brain`) is a pi-mono agent that answers by governing
gather/answer/ask/abstain through a credence brain. Its tools reach this repo's retrieval,
extraction, and probes over a small JSON service (pi-mono has no MCP client — move-2-design §5 Q1).

This package's Stage-2a (Move 2) content is the **parity boundary, Python side**:
:func:`observations.to_abstract_observations` maps grounded observations to the abstract
integer/float form the brain reasons over. The HTTP service exposing retrieve/extract/probe lands in
Move 3, built and validated end-to-end with its pi-mono consumer.
"""
