# Register — OpenClaw governor seam (queued; landing site: governor integration design doc)

> **Status: owner-signed (S11, 2026-08-18) — queued for the governor integration tranche.**

**R-GOV-1 (2026-08-18, verified against docs.openclaw.ai).** The
`before_agent_finalize` seam **fails open**: handlers have a 15 s default budget, and
on timeout OpenClaw logs the failure and continues with the original final answer. A
governor whose EU computation overruns the budget silently becomes a no-op on exactly
the complex cases it exists for. Consequences, binding on the governor design:
(i) the finalize hook is advisory-grade — revise-nudges and shadow-mode logging only,
never enforcement; (ii) enforcement belongs at `before_tool_call`, whose blocking
semantics are fail-safe: `{block:true}` is terminal and stops lower-priority handlers,
`{block:false}` is a no-op that does not clear a prior block; (iii) the governor's
per-decision latency budget must sit well inside the hook budget, and the timeout path
is treated as a logged failure, not a pass; (iv) install prerequisite:
`plugins.entries.<id>.hooks.allowConversationAccess: true` is required for raw
conversation access from the typed hooks — its absence must degrade loudly.
`BeforeAgentFinalizeRetry {instruction, idempotencyKey?, maxAttempts?}` supports
bounded, replay-safe revise retries; Codex-native Stop hooks relay into this seam.
