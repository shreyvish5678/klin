# Event contract

Every meaningful state transition should emit one append-only event:

```json
{
  "schema_version": "1.0",
  "run_id": "run-id",
  "sequence": 1,
  "timestamp": "2026-07-17T00:00:00Z",
  "event_type": "RUN_CREATED",
  "phase": "BOOTSTRAP",
  "status": "running",
  "lane": null,
  "branch_id": null,
  "candidate_id": null,
  "summary": "Sanitized human-readable update",
  "structured_reason": "Evidence, observed signal, decision, uncertainty, and next action",
  "metrics": {},
  "cost": {
    "estimated": null,
    "actual": null,
    "currency": "USD"
  },
  "evidence_paths": [],
  "artifact_paths": [],
  "requires_user_action": false
}
```

## Rules

- `sequence` is monotonic within a run.
- Events are append-only and sufficient to reconstruct visible state.
- Facts, inference, proposed work, and missing evidence remain distinct.
- Events contain no chain-of-thought, credentials, private messages, or hidden
  labels.
- State is atomically updated after every authoritative event.
- Branches terminate before a comparison joins them.
