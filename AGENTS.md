# Working on this environment

The environment lives in `my_env/`. Run its development commands from that
directory. The animated run viewer lives in `my_env/viz/`; see
[`my_env/viz/README.md`](my_env/viz/README.md) for launch and verification commands.

## Keep Agent world in step with the environment

**When extending the environment, extend the visualizer in the same change.**
Agent world is part of the environment's user experience. A new capability is
not finished until people can follow it in both replay and live mode wherever
the recorded data supports it.

Before changing tools, evidence, task configuration, budgets, submissions,
grading, or run artifacts, check how the change affects the viewer:

- **New or changed tools:** update event normalization, station routing, the
  scene, and the inspector. Give a new action an understandable visual treatment
  and a keyboard-accessible station control. Preserve arguments, results, and
  errors in the details view; do not leave a supported tool as an unexplained
  generic event.
- **New documents or evidence types:** update the catalogue, cabinets or other
  appropriate storage, labels, backpack inventory, and retrieval animations.
  Derive counts and metadata from the run where possible. Do not assume there
  will always be five documents or only R01, R03, S01, S03, and S04.
- **Changed schemas or outcomes:** keep transcript and trace parsing, budgets,
  token accounting, finding status colors, submission/error behavior, completion
  copy, and grading flags consistent with the producer. A rejected submission
  must not produce accepted findings or success animations.
- **Changed paths or recording behavior:** update run discovery, artifact/grade
  lookup, live tailing, and matching of the finished replay. Keep launcher
  recipes and usage documentation accurate.

If a change has no visible or recorded effect, say why no visualizer change is
needed in the handoff or PR description. Do not make cosmetic changes solely to
touch the viewer.

## Where changes belong

`my_env/viz/agent_world.html` contains three inline scripts:

1. **Data adapter (`agent-world-data`):** `AgentWorldData` normalizes transcripts
   and live trace records into beats and reconstructs state for any timeline
   position.
2. **Canvas renderer (`agent-world-scene`):** `AgentWorldScene` owns stations,
   sprites, paths, and animations.
3. **Controller:** owns station controls, inventory, playback, live polling,
   inspector panels, and grading display.

Update all affected layers together. Station identifiers, document ID patterns,
and the five-document inventory baseline currently appear in multiple places;
changing only the canvas or only the data adapter is insufficient.
`my_env/viz/serve.py` owns the local HTTP endpoints.

## Preserve the experience and data truth

- Keep the cute pixel-art investigation world, expressive robot, and meaningful
  station interactions as the environment grows. Expand the room or navigation
  when needed so new content stays legible and reachable.
- Keep the viewer self-contained: vanilla JavaScript, inline canvas art, no
  external assets or frontend build step, and a standard-library Python server.
- Preserve older saved runs and imported transcripts. Unknown future events
  should remain inspectable without breaking playback.
- Keep backward seeking deterministic: inventory, budgets, tokens, findings,
  and completion must reflect the selected event, without leaking future state.
  Preserve the grouping of parallel calls.
- Use recorded data, not invented reasoning, results, or quality judgments.
  Live mode cannot show reasoning or tokens until those are actually available.
  Completion scores measure completion, not factual accuracy.
- Preserve play/pause, stepping, speed, timestamp pacing, file import, live
  follow, reduced motion, keyboard controls, and responsive layouts.
- Keep `/api/file` restricted to `out/`, including resolved symlinks. Render
  transcript content as text. Live tailing must tolerate missing files, partial
  lines, and trace resets without dropping or duplicating complete records.

## Verify changes that affect the viewer

Add or update meaningful regression coverage for the new behavior, including
replay and live normalization when relevant. Synthetic cases must run without
local `out/` artifacts; saved runs supplement that coverage.

From `my_env/`, run:

```sh
uv run --frozen --extra test pytest -q tests/test_visualiser.py
node --test tests/test_visualiser_data.cjs
uv run --frozen --extra dev just lint
```

Also run environment tests relevant to the change. For visible changes, inspect
the affected behavior in the browser, including backward scrubbing and error
states; check desktop and narrow layouts. For live changes, append trace
records and verify follow/replay handoff. Save screenshots under `.context/`.
Report any checks you could not run or unrelated pre-existing failures.
