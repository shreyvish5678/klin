# Rollback

## Current rollback boundary

- WorkflowDistill bootstrap commit:
  `eefdba74b6536314b6a3ba34e07ecce5d89b2363`.
- No discovered agent, hosted model, Bonsai model, adapter, launcher, service,
  deployment, or credential was modified by this run.
- `discord-agent` is selected, but selection and contract drafting did not
  modify its source or installed credentials.
- No production Discord message was sent.
- No Zero capability, Akash deployment, or Pomerium request was executed.

## Existing repository state to preserve

- `discord-agent` has an unborn `main` branch and no commit, so it cannot
  provide a conventional Git worktree base. It also contains pre-existing
  untracked files. After selection, use a full isolated copy and never delete
  or rewrite the source directory.
- `discord-manager` baseline revision is
  `c40d02bdd015802fa8dc84327f11e59b175ba03d` with pre-existing dirty work.
- `discord-cli` baseline revision is
  `78213756cecfde269215902243bef70717ea8390` with pre-existing dirty work.
- `bonsai-reasearch` baseline revision is
  `d98377f45118fdf981e9d41a7e48a88e0036218c` with pre-existing dirty work.
- `bonsai-heretic` baseline revision is
  `a2addc765bfb463d560b5c217ffaf08c29008edc` with pre-existing dirty work.

These revisions are identity evidence, not permission to discard uncommitted
user work. Never use a destructive reset. The hosted model remains intact
through every later candidate test and is the rollback endpoint.
