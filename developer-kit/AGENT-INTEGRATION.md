# Integrate your own agent

## Required inventory

Copy `templates/agent-manifest.yaml` and fill in:

- trigger and entrypoint
- hosted model and provider
- model request and response envelopes
- prompts and context builders
- tool schemas and permissions
- deterministic business logic
- output consumers and write authority
- representative traces and tests
- rollback command

## Boundary pattern

```text
agent event
  → fixed context builder
  → model-boundary adapter
  → selected model endpoint
  → fixed tool gate
  → fixed tool implementation
  → fixed output path
```

Use `examples/model-boundary-adapter.mjs` as the adapter seam. The control and
candidate must receive the same normalized request and tool definitions.

## Integration sequence

1. Launch the existing agent in a sandbox or shadow environment.
2. Prove the hosted path with direct-response, single-tool, and
   authorization-sensitive cases.
3. Freeze prompt, tool, fixture, evaluator, and benchmark hashes.
4. Point only the adapter at the candidate endpoint.
5. Run selection evaluation and preserve normalized traces.
6. Lock the candidate before hidden evaluation.
7. Reproduce from a clean checkout.
8. Run shadow integration with production writes disabled.
9. Keep the hosted endpoint available for rollback.

## Secret handling

Load credentials through the agent's existing secret mechanism. Never place
tokens in result bundles, events, screenshots, prompts, commits, or model
training data.
