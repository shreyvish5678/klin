# Work Distill

Work Distill is an evidence-first interface for deciding whether an agent's
hosted model can be replaced by a cheaper local model without changing the
agent around it.

The production demo is in [`products/dist-ui`](products/dist-ui). It contains
the responsive React product, local SSE orchestrator, sanitized sealed replay,
real-browser tests, architecture handoff, screenshots, and a YouTube-ready
screen recording.

![Work Distill completed replay](products/dist-ui/public/demo-results.png)

## Start the product

```sh
cd products/dist-ui
npm install
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173) and select
**Replay at 10×**.

## Validate

```sh
cd products/dist-ui
npm run validate
```

The validation gate runs six deterministic and browser-level tests, including
the 390 px responsive surface, then creates the production Vite build.

## Demo and documentation

- [12-second H.264 product demo](products/dist-ui/public/work-distill-demo.mp4)
- [Technical screenshot](products/dist-ui/public/demo-technical.png)
- [System design](products/dist-ui/docs/SYSTEM-DESIGN.md)
- [Implementation prompt](products/dist-ui/docs/IMPLEMENTATION-PROMPT.md)
- [Result import contract](products/dist-ui/docs/RESULT-IMPORT.schema.json)
- [Presenter script](products/dist-ui/docs/DEMO-SCRIPT.md)

The displayed result is a sanitized replay of sealed evidence. Proposed
optimization methods remain visibly marked `NOT RUN`, and no production
Discord write or secret is included.

`workflowdistill-replay-site` is the earlier presentation prototype;
`products/dist-ui` is the maintained product surface.
