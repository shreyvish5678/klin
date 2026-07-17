# Implementation prompt

Use this prompt when connecting Work Distill to a new validated run:

> Integrate a sanitized WorkflowDistill result bundle into the existing
> `products/dist-ui` application. Preserve the surrounding agent, tool surface,
> fixtures, evaluator, and authorization rules. Change only the model boundary.
> Validate the bundle against `docs/RESULT-IMPORT.schema.json`; verify its
> manifest, evaluator, prompt, tools, and fixture hashes before rendering it as
> measured evidence. Keep facts, inference, proposed methods, and missing
> evidence visibly distinct. The Overview must explain the decision in plain
> language. The Technical tab must show the execution DAG, exact measured
> aggregates, hard gates, visible representative cases, provenance, and the
> next model-boundary experiment. Never expose secrets, private Discord data,
> confirmation receipts, hidden cases, or raw traces. Never convert a
> user-reported result into a sealed claim. Provide a 10x deterministic replay,
> responsive desktop/mobile layouts, keyboard controls, tests, production
> build, rollback notes, and reproduction instructions.

## Acceptance criteria

- Imported run ID and hashes are visible in technical provenance.
- Model paths use the same frozen case set and evaluator.
- Pass counts, latency, loop counts, safety gates, and spend come from the
  validated result bundle.
- Proposed SFT, DPO, LoRA, or decoding methods are labeled `NOT RUN` until
  direct artifacts exist.
- `npm test` and `npm run build` pass.
- The demo recording and screenshots are regenerated from the final source.
