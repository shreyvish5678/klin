# Final Report

## Direct answer

NOT YET

No local Bonsai candidate met the frozen non-inferiority and hard-gate
contract in this timed validation.

## Measured outcome

| Path | Selection success | Hard gates | Repetition loops | p95 latency |
|---|---:|---|---:|---:|
| Hosted gpt-5.6-sol | 4/9 | FAIL | 1 | 21.52s |
| Untouched Bonsai 27B Q1 | 1/9 | FAIL | 3 | 63.78s |
| Bonsai + p42 LoRA | 0/9 | FAIL | 31 | 144.72s |

The p42 mechanism was rejected: it worsened success from 1/9 to 0/9 and
increased repetition loops from 3 to 31. No finalist was locked, so hidden
evaluation, clean reproduction, and the authorized shadow send were correctly
not attempted. Discord sends: **0**.

## What worked

- The selected Discord facade was restored and passed 13 tests plus a masked,
  bounded live read-only Discord probe.
- The hosted Responses path completed model → MCP → Discord identity → model.
- The 15/9/6 benchmark was frozen after hosted observation.
- Pomerium allowed the candidate sandbox path (200) and denied hidden-label
  access (403).
- Zero made one paid $0.02 capability call; its stale catalog was rejected and
  that result reduced the hosted suite without inventing pricing.
- Untouched and p42 Bonsai paths ran locally at 16,384-token context.
- Hosted rollback remains available; the selected source content was not
  changed and no production cutover occurred.

## Incomplete mandatory gates

- No genuine Akash model experiment completed: no CLI, wallet/config, container
  runtime, deployment ID, or logs were available locally.
- The attested Brave key was not discoverable in the process, login shell, or
  launchd environment, so live Brave search was not claimed.
- No candidate qualified for hidden evaluation, clean reproduction, or shadow
  integration.
- Exact hosted dollar cost remains unavailable from the authenticated surface;
  exact token use is retained (295122 input,
  2193 output).

## Stop reason

Formal timed infeasibility: the visible contract failed for every Bonsai
candidate and mandatory downstream gates could not truthfully complete in the
remaining window. The correct product answer is **NOT YET**.
