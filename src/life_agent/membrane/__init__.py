"""life_agent.membrane — the proplang engine client, DEFERRED off the ask path.

The decider is :mod:`life_agent.core.decider` (the Bayes act over the local posterior).
This package is kept green for the engine's return (``ROADMAP.md`` doors):
:mod:`~life_agent.membrane.client` is the JSON-lines transport;
:mod:`~life_agent.membrane.world` the answer-domain world (features, feasibility, menu,
and the ``said@1`` sentence built from ``core.decide``'s rows);
:mod:`~life_agent.membrane.session` one booted world driving decide and evidence ticks;
:mod:`~life_agent.membrane.boot` the decision ⋈ verdict join a boot replays.
"""
