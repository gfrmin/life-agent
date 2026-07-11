"""life_agent.membrane — the proplang membrane shadow.

A Python host driving the frozen `proplang-govhost` decider binary over JSON-lines
stdio, shadow-logging its choices beside the production answer executor (never on the
decision path itself — see the feature's design doc).

Task 1 (:mod:`life_agent.membrane.client`) is the transport only: a spawnable,
dependency-injectable ``MembraneClient`` plus the wire's compact-JSON encoding
contract. Task 2 (:mod:`life_agent.membrane.world`) is the answer-domain world
declaration (features, menu, utility). Task 3 (:mod:`life_agent.membrane.session`) is
``MembraneSession`` — one booted world driving decide/verdict/outcome ticks. Task 4
(:mod:`life_agent.membrane.shadow`) is ``MembraneShadow`` — the supervisor: one worker
thread running every declared utility form's session off the same live traffic, a
bounded enqueue-only submit surface, respawn-with-fresh-snapshot on a session failure,
and the append-only shadow log. Wiring `submit_*` into the real bridge/executor is a
later task.
"""
