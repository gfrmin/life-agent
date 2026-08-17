# `email_triage` transform (v1)

A small classifier (SPEC §18.8): an `email` artifact → one `category`
(`personal_work` | `transactional` | `automated_alert` | `newsletter_marketing` |
`status_report` | `other`) plus a short `reason`. No extraction, no grounding —
just *what kind* of email this is, grammar-constrained to the enum.

It composes with `action_items` (§18.7): both run over `email` artifacts
independently, and the action faculty (`life_agent`) files a task only when triage
says the email is one the owner must act on. **pkm classifies; the consumer
decides which categories are actionable** — that policy lives in `life_agent`, so
it is tunable without re-running the model.

Install into a live root by copying the three files under
`<root>/{transforms,prompts,schemas}/`, then:

    pkm --config <config> transform run email_triage --limit 50

Anthropic model (`claude-haiku-4-5-20251001` — local Ollama deprecated 2026-08-17),
metered `cost_usd` under the cost gate. Pin a dated model id (never an alias);
it is part of the cache key.
