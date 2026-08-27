# packaging

`systemd --user` units for the surfaces this repo deploys. Each one runs a wrapper in
[`../bin/`](../bin) rather than a Python entry point directly, so the unit stays free of
paths, ports and ids, and the wrapper does the environment resolution.

| unit | wrapper | what it is |
|---|---|---|
| `jarvis.service` | `bin/jarvis` | the Telegram reach channel |
| `gtd-web.service` | `bin/gtd-web` | the GTD board (`:8797`) |
| `trips-web.service` | `bin/trips-web` | the trips timeline, read-only (`:8800`) |
| `life-agent-bridge.service` | `bin/answer-bridge` | the answer-brain read path (`:8798`) |
| `daily-digest.{service,timer}` | `bin/daily-digest` | the scheduled briefing |

## Install: symlink, never copy

```bash
cd "$(git rev-parse --show-toplevel)"                            # from anywhere in the repo
ln -s "$PWD"/packaging/jarvis.service ~/.config/systemd/user/    # PII-OK: standard XDG + repo-relative paths
systemctl --user daemon-reload && systemctl --user enable --now jarvis.service
```

A `cp`-installed unit is a second copy free to drift, and this directory stops being the
source. That is not hypothetical here: `gtd-web.service` and `trips-web.service` ran as
real files on one host for a month, with a different `ExecStart` and the owner's Telegram
id inlined, while these tracked copies said otherwise. Nothing detected it, because
nothing can — two copies with no link between them have no mechanism to disagree loudly.

## THIS REPO IS PUBLIC — nothing owner-specific goes in a unit

No ids, addresses, absolute `/home/<user>` paths or ports-with-meaning. Use `%h`, systemd's
specifier for the user's home. Everything else resolves at runtime from the **gitignored
`.env`**, which each `bin/` wrapper sources before exec:

```
LIFE_AGENT_KB=...       PKM_CONFIG=...       JARVIS_USER_ID=...
```

### The trap that caused the drift, written down so it stops recurring

Under `loginctl enable-linger`, a `systemd --user` service starts with a **locked
gnome-keyring**. Anything resolving a secret through `secret-tool` therefore fails at boot
with no obvious cause — for the owner id, `tasks.store.owner_user_id()` exits with
`set JARVIS_USER_ID (env or keyring)`.

So "it resolves from the keyring" is true interactively and false under a linger-started
service. Put the value in `.env`. A deployment that hits this and works around it by
editing its own copy of the unit is how a public repo's PII-free unit and a live host's
unit come to disagree — which is exactly what happened, and why the wrappers exist.

If you need the keyring itself unlocked for a scheduled job, `unlock-keyring` in the ops
repo (under its per-host `bin/`) is the escape hatch.
