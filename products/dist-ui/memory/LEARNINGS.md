# Verified Learnings

- The product name shown to users is Work Distill.
- The primary interaction is chat on the left and a live research-loop
  visualizer with evidence output on the right.
- The source contract uses a fixed outer state machine and an adaptive inner
  graph with explicit promotion and validation gates.
- The neighboring `workdistill` workspace is product context and authoritative
  run state; this UI must not mutate it.
- A small Express server can supply the reference inventory, verify local Codex
  CLI availability, and stream the UI event contract over SSE without coupling
  the interface to the authoritative validation workspace.
- The mobile control surface should keep the research diagram horizontally
  scrollable while preventing document-level horizontal overflow.
- Overlay connector geometry must derive from rendered node positions; scaling
  a fixed SVG path set across variable-height graph states visibly detaches
  arrows from their nodes.
- For the consumer-facing surface, a numbered journey with technical details
  behind disclosure is easier to understand than an always-visible research
  topology, even when the underlying event contract remains unchanged.
- A comparison is not complete for a novice when checks merely stop running;
  completion must name the recommendation, explain why it won, distinguish it
  from other passing options, and provide one obvious next action.
- The sealed Discord run has no winning replacement: hosted scored 4/9,
  untouched Bonsai 1/9, and p42 0/9. The UI must render this as `NOT YET`;
  proposed optimization methods belong in a separately labeled technical view.
