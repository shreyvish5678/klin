# WorkflowDistill Validation Replay

An interactive, accelerated replay of the completed Discord-to-Bonsai matched
validation run. The default Story tab is judge-friendly; the separate Research
Console contains the 10x event stream, execution DAG, benchmark matrix, method
queue, and model-neutral harness pseudocode.

The site defaults to measured evidence and deliberately preserves the negative
result: the hosted control passed 4/9 selection cases, untouched Bonsai passed
1/9, and the p42 adapter passed 0/9. A separate, prominently labeled target
view describes the next model-boundary experiment without presenting it as a
measured result.

## Run locally

```bash
npm install
npm run dev
```

The default replay is a three-minute genuine-event cut shown at 10× speed, so it
completes in about 18 seconds. Playback speed, pause/replay, test-case
inspection, and evidence/target modes are interactive.

## Validate

```bash
npm test
```

This builds the Cloudflare-compatible vinext worker and verifies that the
rendered product contains the evidence labels, representative results, and no
starter preview content.
