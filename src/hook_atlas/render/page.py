"""One self-contained HTML page for one traced run.

Standalone on purpose. Somebody tracing their own project has no site, no
server and no stylesheet, and telling them to build one before they can look at
the picture would rather defeat the exercise. Everything - diagrams, styles,
the filter - is inlined, so the file works from a disk with no network.
"""

from __future__ import annotations

import html
import json
from typing import Any

from .. import analysis, flow, implementers
from ..config import AtlasConfig
from . import css, dot

SEMANTICS = {
    "plain": "",
    "historic": "historic",
    "firstresult": "firstresult",
    "both": "historic, firstresult",
}


def render(
    trace: dict[str, Any], described: AtlasConfig | None = None, standalone: bool = True
) -> str:
    """The whole page: what produced it, a diagram per phase, and every hook.

    ``standalone`` wraps it in a document. Without it you get the styles and the
    body only, for pasting into a site that supplies its own ``<html>`` - which
    is what the mkdocs scaffold does.
    """
    described = described or AtlasConfig()
    hookspecs = trace.get("hookspecs", {})
    environment = trace.get("environment", {})
    application = environment.get("application") or "this run"
    version = environment.get("version") or ""

    phases = analysis.resolve_phases(trace, described.phases)
    sections = []
    for phase in phases:
        variants = flow.phase_variants(analysis.phase_subtrees(trace, phase))
        nodes = flow.fold_repetitive(variants[0].flow) if variants else []
        svg = dot.render_inline_svg(nodes, hookspecs, links=described.links, phase=phase.key)
        heading = f"<h2>{html.escape(phase.title)}</h2>" if len(phases) > 1 else ""
        description = f"<p>{html.escape(phase.description)}</p>" if phase.description else ""
        sections.append(f"{heading}\n{description}\n{svg}")

    title = f"{application} {version}".strip()
    if not standalone:
        return _fragment(
            provenance=_provenance(trace),
            body="\n".join(sections),
            table=_hook_table(trace, described),
            phase_keys=[phase.key for phase in phases],
            owner=described.application or application,
        )
    return _document(
        title=title,
        provenance=_provenance(trace),
        body="\n".join(sections),
        table=_hook_table(trace, described),
        phase_keys=[phase.key for phase in phases],
        owner=described.application or application,
    )


def _provenance(trace: dict[str, Any]) -> str:
    """What produced this page, so a file found later can still explain itself."""
    environment = trace.get("environment", {})
    stats = trace.get("stats", {})
    argv = trace.get("scenario", {}).get("argv") or []
    command = " ".join(argv)
    parts = [
        f"{stats.get('unique_hooks', '?')} distinct hooks, {stats.get('total_calls', '?')} calls",
        f"pluggy {environment.get('pluggy', '?')}",
        f"Python {environment.get('python', '?')}",
    ]
    line = " &middot; ".join(parts)
    if command:
        line += f"<br><code>{html.escape(command)}</code>"
    return line


def _hook_table(trace: dict[str, Any], described: AtlasConfig) -> str:
    """Every hook observed, with the plugins behind it in pluggy's call order.

    An application implements most of itself as plugins, so this is mostly its
    own internals - which is the point, and why the filter exists.
    """
    graph = analysis.full_graph(trace)
    hookspecs = trace.get("hookspecs", {})
    implemented = implementers.for_trace(trace, described.internal)

    rows = []
    for name in sorted(graph.hooks):
        hook = graph.hooks[name]
        url = described.links.url_for(name, hookspecs.get(name, {}).get("declared_in"))
        label = (
            f'<a href="{html.escape(url)}" target="_blank"><code>{html.escape(name)}</code></a>'
            if url
            else f"<code>{html.escape(name)}</code>"
        )
        listed = (
            "<br>".join(
                f'<span class="ha-impl ha-{"internal" if item.internal else "external"}">'
                f"<code>{html.escape(item.label)}</code>"
                + (
                    f' <span class="ha-flags">{html.escape(item.annotation)}</span>'
                    if item.annotation
                    else ""
                )
                + "</span>"
                for item in implemented.get(name, ())
            )
            or "-"
        )
        rows.append(
            f"<tr><td>{label}</td><td>{hook.call_count}</td>"
            f"<td>{SEMANTICS[hook.semantics]}</td><td>{listed}</td></tr>"
        )

    return (
        '<div class="ha-hook-table">\n<table>\n'
        "<thead><tr><th>Hook</th><th>Calls</th><th>Semantics</th>"
        "<th>Implemented by, in call order</th></tr></thead>\n"
        f"<tbody>\n{chr(10).join(rows)}\n</tbody>\n</table>\n</div>"
    )


#: Plain DOM rather than a framework hook. A site may swap pages without
#: reloading and need something cleverer; a file opened from disk does not.
#: Progressive enhancement: with scripting off every implementation is shown,
#: which is the correct default rather than a degraded one.
FILTER_SCRIPT = """
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.ha-hook-table').forEach(function (container) {
    const rows = Array.from(container.querySelectorAll('tbody tr'));
    // nothing outside the application itself means nothing worth filtering
    if (!rows.some((row) => row.querySelector('.ha-external'))) return;

    const box = document.createElement('input');
    box.type = 'checkbox';
    box.id = 'ha-hide-internal';

    const label = document.createElement('label');
    label.className = 'ha-filter';
    label.htmlFor = box.id;
    label.appendChild(box);
    label.appendChild(document.createTextNode(' \\u00a0Hide ' + OWNER + '\\u2019s own plugins'));

    box.addEventListener('change', function () {
      container.classList.toggle('ha-hide-internal', box.checked);
      rows.forEach(function (row) {
        // a row with nothing left to show is noise, not information
        row.hidden = box.checked && !row.querySelector('.ha-external');
      });
    });

    container.insertBefore(label, container.firstChild);
  });
});
"""

#: Enough to read the page on its own. The diagram colours come from the
#: generated stylesheet; this is only what surrounds them.
PAGE_STYLE = """
body { font: 15px/1.6 system-ui, -apple-system, sans-serif; margin: 2rem auto;
       max-width: 72rem; padding: 0 1rem; color: #1b1b1b; background: #fff; }
h1 { margin-bottom: .2rem; }
.ha-provenance { color: #5a5a5a; margin-top: 0; }
h2 { margin-top: 2.5rem; border-bottom: 1px solid #e2e2e2; padding-bottom: .3rem; }
svg { max-width: 100%; height: auto; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { text-align: left; padding: .4rem .6rem; border-bottom: 1px solid #ececec;
         vertical-align: top; }
th { border-bottom: 2px solid #d8d8d8; }
td:nth-child(2) { text-align: right; }
code { font-size: .92em; word-break: break-word; }
@media (prefers-color-scheme: dark) {
  body { background: #1b1b1b; color: #e3e3e3; }
  .ha-provenance { color: #b4b4b4; }
  h2 { border-color: #3a3a3a; }
  th, td { border-color: #333; }
  th { border-bottom-color: #4a4a4a; }
}
"""


def _fragment(
    provenance: str, body: str, table: str, phase_keys: list[str], owner: str = ""
) -> str:
    """Everything but the document shell, for embedding in a site."""
    script = f"const OWNER = {json.dumps(owner or 'the application')};{FILTER_SCRIPT}"
    return f"""<style>{css.stylesheet(phase_keys)}</style>

<p class="ha-provenance">{provenance}</p>

{body}

## Every hook observed

{table}

<script>{script}</script>
"""


def _document(
    title: str, provenance: str, body: str, table: str, phase_keys: list[str], owner: str = ""
) -> str:
    diagram_css = css.stylesheet(phase_keys)
    # the checkbox says whose plugins it hides, which is only knowable here
    script = f"const OWNER = {json.dumps(owner or 'the application')};{FILTER_SCRIPT}"
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>hook flow: {html.escape(title)}</title>
<style>{PAGE_STYLE}{diagram_css}</style>

<h1>{html.escape(title)}</h1>
<p class="ha-provenance">{provenance}</p>

{body}

<h2>Every hook observed</h2>
{table}

<script>{script}</script>
</html>
"""
