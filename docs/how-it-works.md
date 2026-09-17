# How it works

Short version: pluggy is asked to report every hook call, the calls are recorded
as a tree, and the tree is drawn. The interesting part is how you get pluggy to
report calls in a program you are not modifying.

## Getting in

pluggy has supported hook monitoring for years —
`PluginManager.add_hookcall_monitoring(before, after)` is public API, and once
you hold a manager, recording its calls is a supported thing to do.

The problem is holding one. There is no registry of live managers and no
notification when one is built, so a tool that did not construct the manager has
no way to find it.

### If you own the manager

`attach(pm)` and you are done. No patching, nothing clever:

```python
tracer.attach(pm)
```

### If you do not

`watch()` wraps `PluginManager.__init__`, so every manager built afterwards is
recorded:

```python
tracer.watch()          # from here on, any manager pluggy builds is traced
```

The wrapping is process-local and reversible — the same technique coverage tools
and debuggers use — but it buys one hard constraint, and it is the only thing
about this worth memorising:

!!! warning "Order matters, and there is no second chance"

    `watch()` must run **before the application builds its manager**, which in
    practice means before the application is imported. A manager that already
    exists was built by the original constructor and will never be seen.

`hook-atlas trace` is that ordering, made safe: patch first, then resolve the
command's entry point, then import and run it. Doing it by hand means doing it
in that order too.

### Why the constructor, and not a plugin

The obvious alternative is to load as a plugin and take the manager the
application hands you. It works — it is how pytest-hook-atlas still captures —
and it is strictly later.

pytest is the worked example. A plugin first receives the manager at
`pytest_addoption` — by which point `pytest_cmdline_parse`, `pytest_addhooks`
and `pytest_addoption` itself have already been called, and a plugin-based
tracer can never record them. `pytest_cmdline_parse` was written down as
structurally unobservable on the strength of that, and stayed that way until
the constructor approach recorded it.

That is the whole argument for the monkeypatch: not elegance, but three hooks
that no politer method can reach.

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
