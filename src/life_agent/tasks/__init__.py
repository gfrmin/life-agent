"""life_agent.tasks — the action faculty: email → grounded GTD tasks (M2).

Reads cached ``action_items`` artifacts from the pkm catalogue (Phase 1), applies
GTD policy (everything → inbox, never auto-schedule), dedups by the source email's
Message-ID via a process-once ledger, and files each into the in-tree jarvis GTD
store with a ``[src:email <Message-ID>]`` citation. No cache, no pkm changes — the
churn lives here, the grounded extraction lives in pkm.
"""
