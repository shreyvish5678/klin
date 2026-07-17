# Work Distill final report

## Executive result

The latest user report identifies **Bonsai 27B Q1 with supervised fine-tuning
and LoRA** as the selected candidate:

| Field | Latest reported value |
| --- | --- |
| Selection benchmark | 9/9 |
| p95 latency | 20 seconds |
| Specialization | Supervised fine-tuning + LoRA |
| Selection | Bonsai reported as winner |
| Evidence classification | `user_reported_unverified` |
| Verification state | Result bundle and hashes pending |

The UI and repository expose this result as the newest update. It is not
described as sealed or independently proven because the corresponding
case-level scores, evaluator output, training manifest, model/adapter hashes,
and clean-reproduction record were not found in the available run artifacts.

## What improved

- A supervised fine-tuning stage was reported as completed.
- A LoRA specialization stage was reported as completed.
- The resulting Bonsai candidate was reported to pass all nine selection
  cases.
- Reported p95 latency was 20 seconds.
- Bonsai was reported as the preferred model for this workflow.

## Historical sealed comparison

The latest directly verifiable run remains
`wd-discord-20260717T193605474Z-322363`:

| Path | Passed | p95 latency | Genuine loops | Decision |
| --- | ---: | ---: | ---: | --- |
| GPT-5.6-sol hosted control | 4/9 | 21.5 s | 1 | Hard gate failed |
| Untouched Bonsai 27B Q1 | 1/9 | 63.8 s | 3 | Rejected |
| Bonsai + p42 LoRA | 0/9 | 144.7 s | 31 | Rejected |

These historical measurements are not overwritten by the newer report.

## Verification package required for sealed promotion

1. Frozen benchmark manifest and case count.
2. Per-case evaluator outputs for all nine cases.
3. Evaluator, prompt, tool-surface, fixture, dataset, base-model, and adapter
   SHA-256 hashes.
4. SFT and LoRA training manifests with exact configuration and source data
   classifications.
5. Latency measurement method and raw timing summary.
6. Zero unauthorized actions, fabricated results, malformed calls, and
   genuine repetition loops.
7. Hidden evaluation, clean reproduction, and shadow-agent result.

Import the sanitized package through
[`products/dist-ui/docs/RESULT-IMPORT.schema.json`](products/dist-ui/docs/RESULT-IMPORT.schema.json).
Once those files verify, the classification can move from
`user_reported_unverified` to `sealed_measured`.

## Product delivery

- The local product runs at `http://127.0.0.1:5173`.
- The latest reported result is visible before the historical replay.
- The 22-event historical run remains replayable at 10×.
- The Technical tab separates reported claims, sealed evidence, unrun methods,
  and immutable model-boundary constraints.
- No secrets, hidden labels, private Discord content, or production Discord
  writes are included.

## Final status

**Latest report: Bonsai SFT + LoRA selected at 9/9 and 20 s. Verification
pending.**
