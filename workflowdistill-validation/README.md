# WorkflowDistill Discord Validation

Public, secret-free validation package produced for Klin.

Result: **NOT YET**. Hosted `gpt-5.6-sol` scored 4/9, untouched local
Bonsai-27B Q1 scored 1/9, and the existing p42 LoRA scored 0/9 with 31
repetition loops. No local candidate met the frozen hard gates.

This package includes the model-neutral harness, evaluator, visible synthetic
benchmark, normalized aggregate evidence, reproduction commands, and sponsor
integration results. It deliberately excludes Discord credentials and target
identities, private messages, raw private traces, protected hidden cases,
model weights, build sandboxes, local auth state, and confirmation receipts.

Start with:

- `results/FINAL-REPORT.md`
- `results/comparison.json`
- `results/REPRODUCE.md`
- `implementation/tools/model_harness.py`

Actual external spend was $0.02 through Zero. Discord sends were zero.
