# Work Distill system design

## Product boundary

Work Distill turns a sealed model-replacement run into an understandable
product surface. The browser never reads private traces, credentials, hidden
labels, or Discord identities. It receives sanitized structured events from a
local replay service.

## Architecture

```text
                  immutable validation boundary
 prompt ──> model ──> tool gate ──> Discord facade ──> normalized trace
              │             │                                │
              │             └── authorization + receipt      │
              │                                              ▼
              └── only swappable node                  deterministic evaluator
                                                               │
                                                               ▼
                   sanitized result bundle ──> replay API ──> React UI
                                               SSE / 10×       ├─ Overview
                                                              └─ Technical
```

## Runtime components

| Component | Responsibility |
| --- | --- |
| `server/workflow.mjs` | Sanitized event fixture and measured aggregate results |
| `server.mjs` | Health, workspace, run creation, and 10x SSE replay |
| `src/App.jsx` | Product state, overview journey, technical inspection, test matrix |
| `src/styles.css` | Responsive dark control surface |
| `tests/workflow.test.mjs` | Event ordering, provenance, cases, and branch lifecycle |
| `tests/ui-browser.test.mjs` | Real browser interaction and 390 px containment |

## Evidence contract

Every replay event carries:

- `schema_version`
- `run_id` and immutable `source_run_id`
- monotonically increasing `sequence`
- `event_type`, `phase`, and graph `node`
- human summary and sanitized detail
- explicit `evidence_mode`
- optional branch, test, artifact, and aggregate metric fields

The current bundle is bound to
`wd-discord-20260717T193605474Z-322363`. A future result may replace it only
when its summary, provenance, evaluator hash, case count, and hard gates pass
the import schema in `RESULT-IMPORT.schema.json`.

The product may also display a `user_reported_unverified` result in a separate
status layer. It must show the reported metrics and methods with a verification
warning and may not supersede a sealed result until the required hashes and
evaluator outputs are imported.

## Production implementation scaffold

1. Export a sanitized signed result bundle from the authoritative run.
2. Validate it against `docs/RESULT-IMPORT.schema.json`.
3. Verify the manifest and evaluator hashes before opening case-level data.
4. Map source events to the stable UI event contract.
5. Store only sanitized aggregates and visible-case facts.
6. Stream replay events from a durable queue or object store.
7. Gate public publication on an explicit evidence classification.
8. Keep the historical run immutable; publish a new version for every result.

## Security invariants

- Never ship provider tokens, Discord tokens, wallet material, private text, or
  hidden labels.
- Never infer a pass from a model filename or process startup.
- Never mix results from different prompt, tool, fixture, or evaluator hashes.
- Never present user-reported numbers as sealed evidence without provenance.
- No UI action performs a production Discord write.
