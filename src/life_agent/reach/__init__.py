"""life_agent.reach — the agent's outward channels.

Transport + persona only. The GTD *truth* and *logic* live in ``life_agent.tasks`` (the
event ledger + the command layer); ``reach`` just carries messages and speaks in the
agent's voice. ``telegram`` is the dumb pipe (poll / send); ``jarvis`` is the loop + NLU +
persona that drives it; ``digest`` is the daily summary.
"""
