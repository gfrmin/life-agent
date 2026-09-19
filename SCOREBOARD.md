# Scoreboard

`python -m eval.score --write`. Counts over each set's rows; `right`/`wrong` include escalated answers, the esc- columns are their escalated share. `U/q` is priced at the folded gauge u_right 1, u_wrong -5.1310, u_declined 0, lambda_usd 1.33108/$. Rule 5: a change merges when no row's U falls against the committed board at today's gauge (`--gate`).

| set | arm | rows | right | wrong | esc-right | esc-wrong | declined | $/q | U/q | s/q |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| owner | typed | 104 | 61 (58.7%) | 2 (1.9%) | 0 | 0 | 41 (39.4%) | 0.0036 | +0.483 | — |
| owner | oracle | 104 | 96 (92.3%) | 5 (4.8%) | 0 | 0 | 3 (2.9%) | 0.3751 | +0.177 | — |
| owner | router | 104 | 97 (93.3%) | 5 (4.8%) | 36 | 3 | 2 (1.9%) | 0.1535 | +0.482 | — |

Not scored:

- `atm` — ATM-Bench email-only number-typed (198); scored from J3 (`make sets`)
- `live` — the live stream since the reset; scored from J4
- `sample` — synthetic sample KB (scripts/bootstrap-sample.sh); scored end to end from J3
