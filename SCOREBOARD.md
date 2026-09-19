# Scoreboard

`python -m eval.score --write`. Counts over each set's rows; `right`/`wrong` include escalated answers, the esc- columns are their escalated share. Rule 5: `wrong` may not rise more than 0.2 pp on any row without the owner.

| set | arm | rows | right | wrong | esc-right | esc-wrong | declined | $/q | s/q |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| owner | typed | 104 | 61 (58.7%) | 2 (1.9%) | 0 | 0 | 41 (39.4%) | 0.0036 | — |
| owner | oracle | 104 | 95 (91.3%) | 6 (5.8%) | 0 | 0 | 3 (2.9%) | 0.3751 | — |
| owner | router | 104 | 97 (93.3%) | 5 (4.8%) | 36 | 3 | 2 (1.9%) | 0.1535 | — |

Not scored:

- `atm` — ATM-Bench email-only number-typed (198); scored from J3 (`make sets`)
- `live` — the live stream since the reset; scored from J4
- `sample` — synthetic sample KB (scripts/bootstrap-sample.sh); scored end to end from J3
