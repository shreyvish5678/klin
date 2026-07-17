# Contributing

## Development

```sh
cd products/dist-ui
npm ci
npm run dev
```

Before opening a pull request:

```sh
npm run validate
```

## Evidence rules

- Keep the surrounding agent, tools, prompts, fixtures, and evaluator fixed
  when comparing models.
- Label results as `sealed_measured`, `user_reported_unverified`, or
  `illustrative_target`.
- Never commit tokens, private messages, hidden labels, raw private traces, or
  wallet material.
- Do not convert a model filename, process startup, or user report into a
  measured claim.
- Proposed training or decoding methods must remain labeled `NOT RUN` until
  artifacts exist.

## Pull requests

Keep each pull request focused. Describe the evidence source, affected model
boundary, verification commands, screenshots for UI changes, and rollback
path.
