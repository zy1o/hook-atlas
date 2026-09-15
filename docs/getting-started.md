# Getting started

```bash
pip install git+https://github.com/zy1o/hook-atlas
```

Not on PyPI yet.

## Trace, draw, open

Run whatever you normally run. Everything after `--` is yours, untouched — your
flags, your plugins, your `conftest.py`, your exit code.

```console
$ hook-atlas trace -- pytest -q tests/
........................                                       [100%]
24 passed in 0.31s
hook-atlas: wrote hook-atlas-trace.json
hook-atlas: draw it with  hook-atlas draw hook-atlas-trace.json

$ hook-atlas draw
hook-atlas: wrote hook-flow.html
```

`hook-flow.html` is standalone: the diagram is inline, there is no server and
nothing to install to look at it.

Other applications work the same way. A second `--` belongs to the program, not
to us, so this reaches tox whole:

```bash
hook-atlas trace -- tox r -e py312 -- --lf
hook-atlas trace -- datasette serve mydata.db    # ctrl-c: the trace is still written
```

## Options

```bash
hook-atlas trace -o run.json -- pytest -q    # name the trace
hook-atlas draw run.json -o flow.svg         # bare SVG rather than a page
hook-atlas check run.json                    # is this trace sound?
```

`check` is worth reaching for when something looks wrong. It reports a tracer
that lost its place, a tree whose counts do not add up, absolute paths baked
into plugin names, and anything that fails to draw.

## Reading the diagram

Steps run top to bottom; arrows mean *then*, not *called inside*. Nesting is
drawn as a box inside a box, so a hook drawn inside another was called during
it. A step marked `×8` is eight consecutive identical calls collapsed into one.

A dashed box is a **fold**: a long stretch that only shuffled a few hooks, drawn
as one cycle followed by a summary naming what it stands for. Distributed runs
produce hundreds of steps of results arriving in whatever order workers
finished, which is thousands of pixels saying "results came back". Nothing is
lost — the folded hooks are named on the box.

## Nothing got traced

```
hook-atlas: pytest created no plugin manager, so there was nothing to trace
```

The command answered before building one — `pytest --version` does — or the
program is not built on pluggy. Try the command you actually run rather than
`--help`.

## Two things worth knowing early

**Long runs make tall pictures.** With no configuration the whole run is one
flow, and a few hundred tests is a very tall image. That is the honest default;
[describing your application](configuring.md) is what slices it into phases.

**Tracing holds the whole call tree in memory** until the process exits. Fine
for a test suite; not yet suitable for a long-lived server.
