# An atlas for your own project

A page like [pytest-hook-atlas](https://zy1o.github.io/pytest-hook-atlas/) for
*your* suite: the run split into phases, every hook listed with the plugins
behind it in call order, and a checkbox to hide the framework's own plugins so
only yours are left.

Two ways to get there. Start with the first; it takes a minute and you can
decide afterwards whether you want a site.

## One page, four commands

```bash
pip install hook-atlas            # plus Graphviz: apt/brew install graphviz

hook-atlas trace -- pytest -q tests/
hook-atlas config --example pytest > atlas.toml
hook-atlas draw --config atlas.toml

# open hook-flow.html
```

That is the whole thing. The page is self-contained — no server, no site, no
stylesheet to install — so you can mail it to someone or drop it in a ticket.

What you get:

- **A diagram per phase.** Startup, collection, the run-test protocol, session
  finish. Arrows mean *then*, not *called inside*; nesting is a box in a box.
- **Every hook observed**, sorted, with its call count, its semantics
  (`firstresult`, `historic`) and every implementation in pluggy's real call
  order — wrappers, then `tryfirst`, then plain, then `trylast`.
- **A checkbox** to hide pytest's own plugins. It only appears if you have
  something of your own on at least one hook; with a bare suite and no
  `conftest.py` there is nothing to reveal, so it stays out of the way.

!!! tip "Trace the command you actually run"

    Your flags, your plugins, your `conftest.py`. `hook-atlas trace -- pytest -q -k "not slow" -p no:randomly`
    is traced exactly as written, and your exit code comes back unchanged.

### Where `atlas.toml` comes in

Skip it and you still get a page — one flow of the whole run, hooks unlinked.
That is the honest default for an application nobody has described, and it is
also a wall of boxes for a suite of any size.

The config is what turns it into the page above: it names the phases, says
where pytest's hook documentation lives, and says which modules count as
pytest's own rather than yours. `--example pytest` gives you the real one,
[the same description](configuring.md) behind the published atlas.

Edit it and re-run `draw`; no re-tracing needed. Tracing is only for when the
suite changed.

## A site you can publish

When the page should live somewhere with a title, navigation and a URL:

```bash
pip install mkdocs mkdocs-material

cd your-project
hook-atlas init-site hook-flow --command "pytest -q tests/"

cd hook-flow
./build.sh
mkdocs serve        # http://127.0.0.1:8000
```

`init-site` writes a small project *inside* your repository:

```
hook-flow/
  atlas.toml      the description above, yours to edit
  mkdocs.yml      site name, theme, the extensions the hook table needs
  build.sh        trace -> draw -> assemble
  docs/           index.md is yours to write; flow.md is generated
```

`build.sh` runs your command from the project root rather than from the site
directory, so it finds your suite. Publish with `mkdocs gh-deploy`, or point
your existing CI at `./build.sh`.

!!! note "It keeps building when your tests fail"

    `hook-atlas` returns your command's exit code, which is usually what you
    want and would otherwise stop the build script dead. The generated script
    allows it through deliberately — a failing run is often exactly the one
    worth looking at.

## Describing something that is not pytest

Nothing above is pytest-specific except `atlas.toml`. For tox, datasette, or
your own pluggy application, write your own: phases, documentation URLs, and
which modules are the application's own. The format is small —
[Describing an application](configuring.md) covers it, and
`hook-atlas config --example pytest` is a worked example to crib from.

With no config at all, every one of these commands still works and produces one
flow of the whole run. That is the floor, and it is deliberately not an error.

## When it looks wrong

```bash
hook-atlas check trace.json
```

Reports a tracer that lost its place, a tree whose counts do not add up,
absolute paths baked into plugin names, and anything that fails to draw.

Two things that surprise people:

- **A very tall diagram.** Expected without a config, and expected with one for
  a few thousand tests. Phases are what make it readable; a thousand-test suite
  drawn flat is tens of thousands of pixels tall and nobody can read it.
- **`created no plugin manager, so there was nothing to trace`.** The command
  answered before building one — `pytest --version` does — or it is not built
  on pluggy. Trace the command you actually run.
