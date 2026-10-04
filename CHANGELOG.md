# Changelog

Newest first, following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [semantic versioning](https://semver.org/).

## [Unreleased]

## [0.3.0] - 2026-10-04

### Added

- CI runs the guide end to end, on every change and weekly, against a committed
  sample project whose conftest implements hooks of its own - so the check is
  that somebody else's code is found, named and told apart from pytest's, not
  merely that a page appeared. The page it produces is kept as an artifact.

- `draw` produces the whole page, not just diagrams: every hook observed, with
  the plugins behind it in pluggy's call order, and a checkbox to hide the
  application's own - which appears only when something of yours is there to
  reveal. Still one self-contained file, no site and no server.
- `hook-atlas init-site` writes a small mkdocs project around a trace, for when
  the page should have a title and a URL. Same renderer underneath, so there is
  one implementation rather than two.
- `draw -o page.md` emits a fragment for a site that supplies its own page
  furniture; `.html` still gives the standalone document.
- `implementers.for_trace`, the single-run answer to who implements what.
- Documentation examples assume no plugins. Every command runs against a bare
  pytest; where one needs a plugin it is named, and a test enforces it.
- A step-by-step guide: [An atlas for your own
  project](https://zy1o.github.io/hook-atlas/your-own-atlas/).

## [0.2.0] - 2026-09-21

### Added

- `DocLinks.documented` narrows linking to the hooks a page actually contains,
  not just the ones its namespaces allow. The two differ when a version's own
  documentation is unavailable and something newer stands in for it.

### Fixed

- Tests that borrow the tracer's module-level recorder now refuse to run when a
  trace is already live, instead of taking it. One of them destroyed the
  recording CI was making of the suite it was running in, which then reported
  that there had been nothing to trace.

### Changed

- The "how it works" sections say when `watch()` has to be called, which is the
  part that decides whether tracing works at all: before the application builds
  its manager, and therefore before it is imported. Previously the ordering was
  implied by an example rather than stated.

### Added

- The flow model, the renderers and the stylesheet are tested here, against
  this package's own palette, rather than in pytest-hook-atlas. They were left
  behind by the extraction, which meant the engine shipped its folding and
  contrast logic with almost no coverage of its own while a downstream project
  tested it. The contrast checks now cover every hue the palette can hand out,
  not only the four pytest happens to use.

## [0.1.0] - 2026-09-15

First release. The engine extracted from
[pytest-hook-atlas](https://github.com/zy1o/pytest-hook-atlas), with pytest
taken out of it.

### Added

- **Tracing any pluggy application.** `watch()` wraps `PluginManager.__init__`,
  which is the only way to reach a manager in a program you are not modifying;
  `attach(pm)` for an application tracing itself. Verified against tox,
  datasette, devpi-client and pytest.
- **`hook-atlas trace | draw | check`.** `draw` writes a standalone HTML page
  with the diagram inline, so seeing the result needs no site and no server.
- **Describing an application** in TOML - phases, documentation links, which
  modules are its own, which hooks stay out of the fingerprint. pytest's config
  ships as a worked example: `hook-atlas config --example pytest`.
- **A useful default for applications nobody has described.** The whole run as
  one flow, hooks unlinked, no phases invented. A trace matching no phase
  anchor falls back to that rather than drawing nothing.
- A readable message when Graphviz is missing. `pip install hook-atlas` does
  not install the renderer, only the bindings to it.
- **`hook-atlas check`**, which reports desynchronised monitoring, trees whose
  counts do not add up, traces that cannot say what produced them, absolute
  paths baked into plugin names, and anything that fails to draw.
- **CI against real applications**, including tracing pytest while it runs
  datasette's own test suite. Synthetic fixtures only exercise what we thought
  to put in them.

### Fixed

Carried over from the extraction, all found by pointing the tool at something
real:

- A console script that *returns* its exit code rather than raising
  `SystemExit` - pytest's does - made a failing run look successful.
- `os.getcwd()` raised inside the tracer when the traced program deleted the
  directory it was working in, which test suites do routinely.
- Phase colours were keyed by pytest's four phase names, so any other phase
  raised `KeyError` when themed and rendered grey otherwise.
- `declared_in` reported a class name rather than a module when a hookspec
  namespace was a class, which resolves to no distribution and matches no
  documented namespace.

[Unreleased]: https://github.com/zy1o/hook-atlas/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/zy1o/hook-atlas/releases/tag/v0.3.0
[0.2.0]: https://github.com/zy1o/hook-atlas/releases/tag/v0.2.0
[0.1.0]: https://github.com/zy1o/hook-atlas/releases/tag/v0.1.0
