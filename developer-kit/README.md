# Work Distill developer kit

This folder is the implementation handoff for teams adapting Work Distill to
their own agents.

## Start here

1. [Run the existing product](RUN.md)
2. [Build your own Work Distill implementation](BUILD-YOUR-OWN.md)
3. [Connect an existing agent](AGENT-INTEGRATION.md)
4. [Implement the event contract](EVENT-CONTRACT.md)
5. [Import and verify results](RESULT-IMPORT.md)
6. [Use the prompt catalog](PROMPTS.md)

## Ready-to-copy scaffolds

- [`examples/model-boundary-adapter.mjs`](examples/model-boundary-adapter.mjs)
- [`templates/agent-manifest.yaml`](templates/agent-manifest.yaml)
- [`templates/replacement-contract.yaml`](templates/replacement-contract.yaml)
- [`templates/result-bundle.example.yaml`](templates/result-bundle.example.yaml)

The core invariant is simple: keep the agent fixed and change only the model
boundary plus the minimum compatibility layer required by that model.
