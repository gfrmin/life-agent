"""life_agent.tasks — the action faculty: email → grounded GTD tasks (M2).

A thin **projection** of pkm's grounded extraction into the mutable GTD store:
``read.py`` queries cached ``action_items`` artifacts and traces each to its
email (Message-ID), and ``project.py`` files every not-yet-seen item once into
the in-tree jarvis inbox with a ``[src:email <Message-ID>]`` citation
(process-once via ``dedup.py``). No cache, no pkm changes — the grounded
extraction lives in pkm; only the immutable→mutable bridge lives here.
"""
