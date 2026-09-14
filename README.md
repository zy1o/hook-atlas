# hook-atlas

Trace and draw the hook execution flow of any [pluggy](https://pluggy.readthedocs.io/)-based
application — pytest, tox, devpi, datasette, or something nobody has written yet.

pluggy powers a lot of Python's plugin systems, and every one of them has the
same problem: the order hooks run in, what nests inside what, and which plugin
actually supplied each implementation are all facts about a *run*, not about the
documentation. This library captures them from a real run and draws the result.

## Status

Early. The library works; the `hook-atlas trace -- <command>` CLI is not built
yet. The first consumer is
[pytest-hook-atlas](https://github.com/zy1o/pytest-hook-atlas), which publishes
[an atlas of pytest's hooks](https://zy1o.github.io/pytest-hook-atlas/).

## What it does

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
