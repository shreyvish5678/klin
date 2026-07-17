# Build your own Work Distill

## 1. Define the immutable agent

Document the agent trigger, context sources, prompts, tools, permissions,
output contract, downstream actions, current model, and rollback path. Model
comparison is invalid if these differ between control and candidate.

## 2. Implement the fixed outer workflow

```text
discover → select → freeze contract → restore baseline → profile workflow
→ freeze benchmark → measure hosted → measure candidate → research
→ lock finalist → hidden evaluation → clean reproduction → shadow integration
```

The research phase may branch adaptively, but the outer gates remain fixed.

## 3. Build the benchmark

Create development, selection, and hidden splits. Cover no-tool behavior,
tool selection, arguments, ordering, failures, ambiguity, authorization,
bounded context, repeated calls, schema compliance, and post-tool completion.
Hash the benchmark before candidate optimization.

## 4. Normalize the model boundary

Use one request/response contract for every model. A compatibility adapter may
translate provider envelopes, chat templates, tool schemas, stop sequences,
streaming chunks, and errors. It must not choose tools, fill semantic
arguments, access hidden answers, or silently call the control model.

## 5. Emit sanitized events

Implement the contract in [EVENT-CONTRACT.md](EVENT-CONTRACT.md). Persist
authoritative state outside the UI and stream only sanitized events.

## 6. Evaluate and promote

Use deterministic scoring where possible. Enforce authorization, fabrication,
loop, malformed-call, hidden-leakage, reproduction, rollback, and economic
gates. Stop at the first candidate that passes the frozen contract.

## 7. Package the result

Produce a sanitized bundle, verify every hash, classify the evidence, and
import it through the product schema. Keep negative results and uncertainty.
