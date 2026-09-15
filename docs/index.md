# hook-atlas

**Trace and draw the hook execution flow of any [pluggy](https://pluggy.readthedocs.io/)-based
application** — pytest, tox, devpi, datasette, or something nobody has written yet.

pluggy tells you which hooks exist. It does not tell you what *your* run did:
the order they fired in, what nested inside what, and which plugin actually
supplied each implementation. Those are facts about a run, not about
documentation, and they change with your plugins, your config and your project
layout. This records them and draws the result.

```bash
hook-atlas trace -- pytest -q tests/
hook-atlas draw
# open hook-flow.html
```

## What you get

A diagram of what actually happened, in order, with nesting preserved. Every
implementation attributed to the plugin that supplied it, in pluggy's real call
order — wrappers, then `tryfirst`, then plain, then `trylast` — so the sequence
explains itself. Hookspec semantics read from the live plugin manager rather
than guessed, which is why hooks your plugins declare are described as fully as
the application's own.

And a JSON trace, which is the thing the diagram is drawn from. It is the more
useful half if you want to answer a question nobody built a view for.

## What it does not do

It does not know what your application is. With no configuration it draws the
whole run as a single flow and leaves hooks unlinked, because guessing a
documentation URL produces dead anchors and guessing phase boundaries produces
confident nonsense. [Describing an application](configuring.md) is a config
file, not a code change.

It does not change the program it watches. Your stdout, your exit code, your
behaviour — a wrapper that turned a failing build green would be worse than no
wrapper, and there is a test named after it.

## Where it came from

It is the engine behind
[pytest-hook-atlas](https://zy1o.github.io/pytest-hook-atlas/), which documents
pytest's hook flow across every release. Everything there that was not
specifically about pytest is here, which is most of it.
