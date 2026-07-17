# Prompt catalog

## Authoritative workflow prompt

[`prompts/workflowdistillprompt.md`](prompts/workflowdistillprompt.md) contains
the complete WorkflowDistill research-director specification: state machine,
adaptive research graph, events, gates, benchmark, model boundary, sponsor
roles, stopping conditions, evidence rules, and handoff.

## Product integration prompt

[`../products/dist-ui/docs/IMPLEMENTATION-PROMPT.md`](../products/dist-ui/docs/IMPLEMENTATION-PROMPT.md)
is the compact prompt for connecting a sanitized result bundle to the UI.

## Agent profiling prompt

> Inspect the selected agent's trigger, context construction, prompts, tools,
> permissions, model request, tool-result feedback, output contract, downstream
> actions, tests, and representative traces. Separate model responsibilities
> from deterministic responsibilities. Produce a sanitized workflow profile,
> failure taxonomy, compatibility requirements, and immutable replacement
> boundary. Do not modify the agent during profiling.

## Benchmark construction prompt

> Build visible development, frozen selection, and protected hidden splits for
> the profiled workflow. Cover no-tool, tool choice, arguments, ordering,
> multi-step completion, tool failure, ambiguity, authorization, bounded
> context, schema, repetition, and forbidden behavior. Prefer deterministic
> fields. Hash the benchmark before optimization and never train on selection
> or hidden labels.

## Candidate evaluation prompt

> Evaluate the candidate through the same agent, prompt, tools, fixtures, and
> evaluator as the hosted control. Record pass count, tool fidelity, schema,
> authorization, fabrication, repetition loops, latency, throughput, context,
> memory, and cost. Preserve negative results. Promote only after hidden
> evaluation, clean reproduction, and rollback verification.

## Result-import prompt

> Import this sanitized result with an explicit evidence classification.
> Verify its case count and hashes before presenting it as measured. If direct
> artifacts are missing, display the supplied metrics as user-reported and
> verification pending without rewriting historical sealed evidence.
