# Describing an application

Optional, and worth it. Without a config you get one flow and unlinked hooks.
With one you get named phases as columns, hooks linked to their documentation,
and a filter for the application's own plugins.

It is TOML, because it is data — describing a project you did not write should
not mean writing Python.

```bash
hook-atlas draw --config atlas.toml
```

## The format

```toml
application = "myapp"              # what pluggy calls the manager

[docs]
base_url = "https://myapp.example/hooks.html"
anchor_prefix = "myapp.hookspec"   # link is <base_url>#<anchor_prefix>.<hook>
namespaces = ["myapp.hookspecs"]   # only hooks declared here get links

[[phase]]
key = "startup"                    # becomes a CSS class and heading anchor
title = "Startup"
anchors = ["myapp_configure"]      # hooks that open this phase
description = "What happens here, in a sentence or two."
```

Every field is optional except a phase's `key` and `title`.

| Key | Means |
| --- | --- |
| `application` | Names the manager, labels releases, and derives which modules count as the application's own (`myapp.`, `_myapp.`). |
| `internal` | Override that derivation when the application's layout is unusual. |
| `bookkeeping` | Hooks kept out of the fingerprint deciding whether two releases produced the same flow. |
| `[docs]` | Where hook documentation lives. Omit it and hooks render unlinked, which beats a dead anchor. |
| `[[phase]]` | One diagram. Drawn in the order written, left to right, taking colours from that order. |
| `phase.anchors` | The hooks that open the phase. Everything called inside them belongs to it. |
| `phase.fallback_anchors` | Used *only* when `anchors` match nothing. |

## Phases, and what happens without them

A phase claims a hook and everything called inside it. A phase whose anchors
never fire is dropped; if that leaves nothing, the whole run is drawn as one
flow rather than an empty page. That fallback is the guarantee that makes this
safe to point at an application nobody has described.

`fallback_anchors` exists for one specific situation: processes of the same run
doing different jobs. Under pytest-xdist the controlling process never calls
`pytest_runtest_protocol` — only its workers do — so anchoring the run-test
phase there alone leaves the controller's entire scheduling loop outside every
phase, drawn nowhere at all.

## A worked example

pytest's config ships with the package. It is the one behind
[pytest-hook-atlas](https://zy1o.github.io/pytest-hook-atlas/), so it is a real
description of a large application rather than an illustration:

```bash
hook-atlas config --example pytest > atlas.toml
```

Two parts of it are worth stealing the reasoning from.

**`bookkeeping`.** pytest excludes `pytest_plugin_registered` and
`pytest_warning_recorded` from the fingerprint. Neither moves for reasons to do
with the flow — the first fires once per registered plugin, so its count tracks
how many plugins a release ships, and the second is replayed in a batch when a
wrapped phase ends, so its position marks a phase boundary rather than where a
warning arose. Left in, releases split into separate documents over a difference
of one call.

**`namespaces`.** pytest's config documents `_pytest.hookspec` and nothing
else. pytest-xdist contributes hooks that pytest's reference has never heard of;
without the restriction they would link to anchors that do not exist.

## Using a config in code

```python
from hook_atlas import analysis, config, flow
from hook_atlas.render import dot

described = config.load("atlas.toml")
trace = analysis.load_trace("hook-atlas-trace.json")

for phase in analysis.resolve_phases(trace, described.phases):
    variants = flow.phase_variants(analysis.phase_subtrees(trace, phase))
    svg = dot.render_inline_svg(
        flow.fold_repetitive(variants[0].flow),
        trace["hookspecs"],
        links=described.links,
        phase=phase.key,
    )
```

`resolve_phases` is the part worth keeping: it drops phases that did not fire
and falls back to the whole run rather than returning nothing.
