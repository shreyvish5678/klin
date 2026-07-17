# Session Handoff

## Objective

Maintain the Work Distill product UI and its local 10x replay of the sealed
WorkflowDistill Discord validation.

## Current state

- The authoritative demo UI lives in this `products/dist-ui` workspace.
- Local URL: `http://127.0.0.1:5173`
- React/Vite client and Express SSE orchestrator are running.
- The default Overview is plain-language and the separate Technical tab
  contains the model-boundary DAG, real benchmark metrics, proposed method
  queue, and harness pseudocode.
- The replay streams 22 sanitized events at 10x from sealed run
  `wd-discord-20260717T193605474Z-322363`.
- A newer user-reported result is displayed prominently: Bonsai 27B Q1 with
  supervised fine-tuning and LoRA, 9/9 selection passes, and 20 s p95 latency.
  Its classification is `user_reported_unverified` pending a result bundle,
  evaluator output, artifact hashes, and clean reproduction.
- Measured results remain GPT-5.6-sol 4/9, untouched Bonsai 1/9, and p42 0/9
  with 31 loops. The verdict is `NOT YET`.
- The historical sealed-run SFT, DPO, rank-sweep, and grammar-decoding queue is
  labeled `NOT RUN`; it is distinct from the newer user report.
- No private messages, identities, secrets, hidden labels, or raw traces are
  included.
- `npm test` passes all 6 tests, including the narrow browser interaction test.
- `npm run build` succeeds.

## Start locally

Run `npm run dev` and open `http://127.0.0.1:5173`.

## Safety and evidence boundary

- Treat `../workdistill/` as read-only product context from this workspace.
- Do not replace the sealed negative result with invented training evidence.
- Keep changes at the model boundary in any future comparison.
- Do not claim a replacement until fresh direct evidence passes every gate.
