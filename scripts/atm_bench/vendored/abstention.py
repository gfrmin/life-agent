"""``ABSTENTION_PHRASES`` — copied verbatim from ``memqa/utils/evaluator/config.py`` at the pinned
sha (see SOURCE). ``config.py`` itself is NOT vendored: it imports ``memqa.global_config`` (the
project's OpenAI/vLLM settings) and names judge models. Upstream's typo-duplicate is kept.
"""

ABSTENTION_PHRASES = [
    "unknown",
    "abstention",
    "no information",
    "not available",
    "no evidence",
    "no evidnece",
    "insufficient information",
]
