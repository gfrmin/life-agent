"""life_agent.membrane — the proplang membrane shadow.

A Python host driving the frozen `proplang-govhost` decider binary over JSON-lines
stdio, shadow-logging its choices beside the production answer executor (never on the
decision path itself — see the feature's design doc).

Task 1 (:mod:`life_agent.membrane.client`) is the transport only: a spawnable,
dependency-injectable ``MembraneClient`` plus the wire's compact-JSON encoding
contract. World/session/supervisor land in later tasks.
"""
