"""life_agent.membrane — the decider: the proplang engine, driven over JSON-lines stdio.

:mod:`~life_agent.membrane.client` is the transport; :mod:`~life_agent.membrane.world` the
answer-domain world (features, feasibility, menu, utility); :mod:`~life_agent.membrane.session`
one booted world driving decide and evidence ticks; :mod:`~life_agent.membrane.boot` the
decision ⋈ verdict join a boot replays; :mod:`~life_agent.membrane.coarse` the enactment of
the engine's act; and :mod:`~life_agent.membrane.decider` the synchronous decider the bridge
serves at ``POST /decide``.
"""
