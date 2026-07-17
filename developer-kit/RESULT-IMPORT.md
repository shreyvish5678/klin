# Import a result

## Classify it

- `sealed_measured`: directly scored, hashed, and reproducible.
- `user_reported_unverified`: a result supplied without its complete evidence
  package.
- `illustrative_target`: a design or optimization goal, not an observation.

## Required verification

1. Validate the bundle against
   `products/dist-ui/docs/RESULT-IMPORT.schema.json`.
2. Confirm case count and split identities.
3. Verify manifest, evaluator, prompt, tool, fixture, model, and adapter hashes.
4. Confirm per-case scores aggregate to the displayed result.
5. Confirm the latency statistic and measurement window.
6. Confirm safety and loop hard gates.
7. Confirm hidden evaluation and clean reproduction.
8. Confirm no production write occurred without authorization.

The latest 9/9, 20-second Bonsai SFT + LoRA result remains
`user_reported_unverified` until this package is available.
