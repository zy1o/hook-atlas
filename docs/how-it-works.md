# How it works

Short version: pluggy is asked to report every hook call, the calls are recorded
as a tree, and the tree is drawn. The interesting part is how you get pluggy to
report calls in a program you are not modifying.

## Getting in

pluggy has supported hook monitoring for years —
`PluginManager.add_hookcall_monitoring(before, after)` is public API. What it has
no API for is *reaching a manager somebody else constructed*. There is no
registry of live managers and no creation hook.

So `watch()` wraps `PluginManager.__init__`:

```python
def patched(self, project_name, *args, **kwargs):
    original(self, project_name, *args, **kwargs)
    attach(self)
```

Process-local, reversible, and applied before the target is imported. It is the
same technique coverage tools and debuggers use. If the application is tracing
itself, `attach(pm)` is the polite version and no patching happens.

This turns out to be *earlier* than a plugin entry point can manage. pytest
hands plugins a manager at `pytest_addoption`, by which time several hooks have
already fired — including `pytest_cmdline_parse`, which pytest-hook-atlas
documented for a year as structurally unobservable. Attaching at construction
records it.

## Staying invisible

The tracer runs inside someone else's process, so it must not change what that
process does.

Its exit code is its own. A console script may *return* its exit code rather
than raising `SystemExit` — pytest's does — and discarding that turned a failing
test run into a passing wrapper. A tool that turns a red build green is worse
than no tool, so that is a named test.

Its stdout is its own; anything we have to say goes to stderr. And an error
inside the tracer must not escape into the program: capture is deliberately
forgiving, and the strictness lives in `hook-atlas check`, which runs afterwards
where failing is free. That is not theoretical — datasette's tests chdir into
temporary directories and delete them, `os.getcwd()` raised inside the tracer,
and a traceback landed in the middle of somebody's test output.

## Order, not just containment

An earlier version of this code drew only containment — an arrow meant "called
inside", never "then". A hook fanned out into a set of unordered boxes, and the
thing people actually get wrong stayed invisible: under pytest, setup, call and
teardown are each followed by their own `makereport` and `logreport`. Three
reports per test, not one.

Arrows now mean *what happened next*. Nesting is a box inside a box.

## Repetition

Consecutive identical siblings collapse into one step with a count, so a run of
eight tests reads as one step marked `×8`.

That handles repetition but not *shuffled* repetition. A distributed run's
controlling process spends hundreds of steps receiving results from workers in
whatever order they finish; consecutive steps are rarely identical, so nothing
collapses, and it renders as thousands of pixels saying "results came back". So
a long stretch drawing on only a handful of hooks is folded: one turn of the
loop drawn in full, the rest summarised in a dashed box naming the hooks it
stands for, and whatever *ends* the loop left drawn.

Folding happens when drawing, never when fingerprinting. It changes how a flow
looks, and must not change which runs are judged the same.

## The trace is the artifact

Diagrams are a view. The JSON trace holds the call tree, every implementation
with the plugin that supplied it in pluggy's real call order, and hookspec
semantics read from the live plugin manager rather than from a module we decided
to import. That last choice is why hooks *your* plugins declare are described as
fully as the application's own — and it is what makes the tool pointable at
something it has never seen.

Renderers are thin functions over that structure. If you want to answer a
question nobody built a view for, read the JSON.

## Nothing is invented

An application nobody has described gets one flow of the whole run and unlinked
hooks. Not four guessed phases, not a URL pattern that might be right.

The same principle runs through the rest: a hook whose declaring module is not
in the configured documentation namespaces renders plain rather than pointing at
an anchor that does not exist; a version is left blank when neither
`__version__` nor package metadata knows it; nothing is "internal" until an
application says which modules are its own.
