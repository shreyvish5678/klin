# Work Distill UI Instructions

## Scope

- This workspace owns only the Work Distill product interface and its local
  demo orchestrator.
- Treat `../workdistill/workdistillprompt.md` as product-domain context. Do not
  mutate the validation workspace while changing this UI.

## Product rules

- Preserve the fixed outer workflow, adaptive research loop, structured event
  language, explicit gates, and evidence-first output.
- Keep the interface dark, restrained, keyboard-friendly, and free of
  decorative emoji or unnecessary visual effects.
- Do not present placeholder data as evidence from a real validation run.
- Keep the surrounding agent immutable in replacement comparisons; represent
  changes at the model boundary.

## Verification

- Run `npm test` and `npm run build` after implementation changes.
- Verify the primary desktop layout and at least one narrow viewport.
