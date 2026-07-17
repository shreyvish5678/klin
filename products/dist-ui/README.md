# Work Distill UI

Work Distill is the local product surface for the completed Discord-to-Bonsai
validation. It replays the sealed run at 10x through the product's existing
React/Vite interface and local Express event orchestrator.

The default Overview stays plain-language. The separate Technical tab exposes
the immutable execution DAG, actual selection results, acceptance gates,
proposed next-method queue, and model-neutral harness pseudocode. Proposed
methods are explicitly labeled as not run.

## Run locally

```sh
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

Choose **Replay at 10×** to stream the 22-event sealed evidence cut.

## Measured result

- GPT-5.6-sol: 4/9, one genuine repetition loop
- Untouched Bonsai 27B Q1: 1/9, three loops
- Bonsai plus p42 LoRA: 0/9, 31 loops
- Replacement verdict: **NOT YET**
- Discord production writes: zero

The interface never presents the proposed SFT, DPO, rank-sweep, or grammar
methods as completed experiments.

## Validate

```sh
npm test
npm run build
```

The browser test verifies the 390 px mobile surface, 10x streamed branch
states, sealed verdict, technical disclosure, keyboard controls, and stopping
behavior.
