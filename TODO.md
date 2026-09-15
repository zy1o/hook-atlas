# What's next

Rough order of value, not a commitment.

## Wire up pytest-hook-atlas

It depends on `hook-atlas` already but installs it from a git branch in CI,
because there was nothing on PyPI. There is now, so those three TEMPORARY steps
come out and the version pin in `pyproject.toml` takes over.

Worth doing as the first real test of the release: it is a consumer that was
developed against an editable checkout, so it will notice anything the packaged
version does not carry.

## An example gallery

Traces are the interesting artifact and there are none to look at without
running something first. A handful captured from real applications, committed,
and drawn on the docs site would show what the output actually looks like -
which is currently only discoverable by installing the tool.

Capture them rather than sharing artifacts out of CI. The CI runs exist to catch
breakage, and making the docs depend on a build somewhere else turns a red run
in one place into a broken page in another.

Candidates, in order of how interesting the shape is:

- **datasette's own test suite under pytest** - already exercised in CI, brings
  pytest-asyncio, pytest-xdist and pytest-timeout with it, so several hookspec
  sources appear at once.
- **tox running something trivial** - small and flat, which is a useful
  counterweight to pytest. Not every pluggy application has a rich flow, and
  the gallery should not imply otherwise.
- **datasette serving** - a long-running process rather than a batch one. Needs
  the memory question below answered first.

## Streaming capture

The whole call tree is held in memory until the process exits, which is fine for
a test run and wrong for a server. Measured in an earlier prototype as a large
reduction in both memory and file size, losslessly, by writing nodes as they
close rather than accumulating them.

Blocks tracing anything long-lived, `datasette serve` included.

## Smaller things

- `hook-atlas draw` renders one phase per diagram. A single page showing phases
  side by side, as pytest-hook-atlas does, would suit a wide screen better.
- Config discovery: look for `atlas.toml` beside the trace, or in the working
  directory, so `--config` is not needed every time.
- An application that creates several plugin managers gets only the first
  traced. devpi-client creates two. Tracing both needs a trace per manager, the
  way processes already work.
