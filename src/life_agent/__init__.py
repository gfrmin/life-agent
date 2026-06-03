"""life_agent — the personal life-management agent (composition root).

Today this package holds the **memory faculty**: a retrieval + synthesis layer over the
pkm content-addressed catalogue. The brain (credence), the agent loop, and the
goals/utility model are future faculties — see ``ROADMAP.md``. Faculties integrate over
language-neutral seams (MCP / HTTP / CLI), so this Python package never assumes what the
eventual agent-loop spine is written in.
"""
