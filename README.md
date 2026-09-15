# hook-atlas

Trace and draw the hook execution flow of any [pluggy](https://pluggy.readthedocs.io/)-based
application — pytest, tox, devpi, datasette, or something nobody has written yet.

pluggy powers a lot of Python's plugin systems, and every one of them has the
same problem: the order hooks run in, what nests inside what, and which plugin
actually supplied each implementation are all facts about a *run*, not about the
documentation. This library captures them from a real run and draws the result.

## Status

Early, and **not published to PyPI yet** - until it is, install it from source:

```bash
pip install git+https://github.com/zy1o/hook-atlas
```

The library and its `trace`/`draw`/`check` commands work. CI runs them against
tox, datasette, devpi-client and pytest on every change - including tracing
pytest while it runs datasette's own test suite - so "it works on things nobody
described to it" is checked rather than hoped for. The first consumer is
[pytest-hook-atlas](https://github.com/zy1o/pytest-hook-atlas), which publishes
[an atlas of pytest's hooks](https://zy1o.github.io/pytest-hook-atlas/).

## See your own project's hook flow

Three commands. Nothing to configure, and nothing to set up first.

```bash
pip install hook-atlas            # not on PyPI yet - see Status below

# 1. run whatever you normally run, with the tracer watching
hook-atlas trace -- pytest -q tests/

# 2. draw it
hook-atlas draw

# 3. open hook-flow.html
```

That is the whole thing. Step 1 writes `hook-atlas-trace.json` beside you and
prints where; step 2 turns it into a standalone `hook-flow.html` you can open in
a browser, with the diagram inline and no site, server or stylesheet needed.

Everything after the `--` is your command, untouched. Your flags, your plugins,
your `conftest.py`, your exit code:

```bash
hook-atlas trace -- pytest -q -k "not slow" --maxfail=2
hook-atlas trace -- tox r -e py312
hook-atlas trace -- datasette serve mydata.db     # ctrl-c: the trace is still written
```

A second `--` belongs to your command, not to us, so `tox r -e py -- --lf`
arrives at tox whole.

### Options worth knowing

```bash
hook-atlas trace -o run.json -- pytest -q   # name the trace
hook-atlas draw run.json -o flow.svg        # bare SVG instead of a page
hook-atlas check run.json                   # is the trace sound?
```

`check` is worth running if something looks wrong: it reports a tracer that lost
its place, a tree whose counts do not add up, absolute paths baked into plugin
names, and anything that fails to draw.

### What you get, and what you do not

The diagram is **one flow of the whole run**, because this tool has not been
told what your application's phases are. Every hook it saw, in the order it was
called, with nesting - and for a large test suite that is a very tall picture.
That is the honest default rather than a guess.

Hooks render unlinked unless the application's documentation is described to the
tool, because a guessed URL is a dead link.

If you want the run sliced into named phases with hooks linked to their
documentation, that is what a wrapper supplies -
[pytest-hook-atlas](https://github.com/zy1o/pytest-hook-atlas) does it for
pytest, in about a hundred lines of configuration.

### If nothing gets traced

```
hook-atlas: pytest created no plugin manager, so there was nothing to trace
```

means the command answered before building one - `pytest --version` does - or
that the program is not built on pluggy at all. Try the command you actually
run, rather than `--help` or `--version`.

## How it works

```python
import pluggy
from hook_atlas import tracer

tracer.watch()          # trace the next plugin manager this process creates
...                     # run the application
tracer.write_trace()    # a JSON record of every call, in order, with provenance
```

`watch()` wraps `PluginManager.__init__`, which is the only way to reach a
manager in a program you are not modifying. `attach(pm)` is the polite version
for an application tracing itself.

The program being traced is left alone. It keeps its own stdout and its own
exit code - a wrapper that turned a failing build green would be worse than no
wrapper at all, so that is a test.

From a trace you get the call tree with nesting and ordering preserved, the
plugin behind every implementation in pluggy's real call order, hookspec
semantics (`firstresult`, `historic`) read from the live manager rather than
guessed, and Graphviz diagrams.

## Configuring it for an application

Nothing is required. With no configuration an application's whole run is drawn
as a single flow, hooks render unlinked, and phases are not mentioned — which is
the honest output for an application nobody has described.

Describing one means supplying `Phase` objects to slice the run into diagrams,
and a `DocLinks` saying where its hook documentation lives. pytest's four phases
— startup, collection, the run-test protocol, session finish — live in
`pytest-hook-atlas`, not here.

## Licence

MIT.
