# Brain design — pi-mono + credence-pi

How the agent's runtime and "brain" work, and how `life-agent` composes them. Verified by reading
both repos on 2026-05-23.

## pi-mono (`~/git/pi-mono`) — the runtime (TypeScript, pnpm, Node ≥20)
A framework you build agents *on* (the public `pi-coding-agent` is one such app). Packages:
- `packages/ai` (`@mariozechner/pi-ai`) — multi-provider LLM (Anthropic/OpenAI/Google) unified streaming.
- `packages/agent` (`pi-agent-core`) — the agent loop: tool-calling, event stream, steering/follow-up queues.
  Tool type `AgentTool` in `packages/agent/src/types.ts`.
- `packages/coding-agent` — TUI app + **extension system**. Extensions register tools via
  `ctx.tools.registerTool(def)`; `ToolDefinition` (name, label, description, TypeBox `parameters`,
  `execute(...)`) in `src/core/extensions/types.ts`; built-ins in `src/core/tools/index.ts`; `loader.ts`.
- `packages/tui`, `packages/web-ui`.
- **No native MCP, by design.** Tools are TS functions. To use MCP servers you **write an extension
  that is an MCP client and wraps each remote MCP tool as a `ToolDefinition`** — our **MCP-bridge**.

Execution: `agentLoop` → LLM emits toolCall → `beforeToolCall` hook (can block) → `tool.execute()` →
`afterToolCall` hook → result appended → next turn. The `beforeToolCall` hook is the seam credence-pi uses.

## credence-pi (`~/git/credence/apps/credence-pi`) — the brain (TS body + Julia daemon)
A **Bayesian governor over tool calls**, *not* a task executor. Body/brain split over an HTTP wire:
- **Body** = a pi extension (`extension/src/index.ts`): hooks the `tool_call` event, extracts features
  (tool name, working dir, repetition…), `POST /sensor`, awaits an effector signal, dispatches it.
- **Brain** = a Julia daemon (`daemon/server.jl`): loads BDSL (`bdsl/{capabilities,features,prior,
  kernel,decide}.bdsl`), holds a posterior `Measure`, runs `decide-action` → **ask / proceed / block**
  (value-of-information driven, no magic thresholds), returns it via `SSE /signals`. Pass-1 works
  end-to-end with full tests; an observation log replays on startup.
- Design rule: ***"the brain does not invent tentacles; it selects from those the body declares."***
  ⇒ keep the brain pure; **declare/register capabilities body-side**.

## How `life-agent` composes them
`life-agent` is a pi app that loads two extensions:
1. **credence-pi governor** (existing) — gates every tool call.
2. **MCP-bridge** (new, in this repo) — an MCP *client* that registers `pkm-memory`, Jarvis, email,
   and calendar MCP tools into pi's registry as `ToolDefinition`s.

So a turn looks like: model wants `pkm_search` → bridge tool → `beforeToolCall` → credence-pi decides
(read-only search ⇒ auto-**proceed**; an email send ⇒ **ask**) → execute via MCP → result. The exact
same MCP servers are usable from Claude Code, keeping capabilities interface-agnostic.

**Governing new capabilities:** declare them in `bdsl/capabilities.bdsl` and let `decide.bdsl` weigh
risk/VOI (e.g. effects that send/modify default to *ask* until the posterior says otherwise).

## Not yet wired (future)
- `credence-proxy` (`~/git/credence/apps/python/credence_router`, OpenAI-compatible router) could back
  pi-ai so the brain also routes *models*. `credence_agents` (`…/python/credence_agents`, the Bayesian
  agent library) could inform policy. Both are separate today; integrate in Phase 2+ if useful.

## "credence-pi" naming
The owner's term: the **pi harness/agent** at `~/git/credence/apps/credence-pi` used with
`~/git/pi-mono`. Not a Raspberry Pi. The always-on runtime is just this app run as a `systemd --user`
service (where Phase 2's "daemon" lives).
