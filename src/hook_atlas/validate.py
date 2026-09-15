"""Check that a trace is well formed, and say what is wrong when it is not.

Separate from capture on purpose. Capture has to be forgiving - it runs inside
somebody else's program and must never be the reason that program fails - so the
checking happens afterwards, where being strict is free.

Run it over a trace from any application:

    python -m hook_atlas.validate hook-atlas-trace.json
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from . import analysis, flow
from .render import dot


def problems(trace: dict[str, Any]) -> list[str]:
    """Everything wrong with this trace, in the order it is worth reading."""
    found: list[str] = []
    found += _structure(trace)
    found += _provenance(trace)
    found += _drawing(trace)
    return found


def _structure(trace: dict[str, Any]) -> list[str]:
    found = []
    if trace.get("desyncs"):
        # the tracer pairs a `before` with an `after`; an unpaired one means the
        # recorded tree does not match the calls that actually happened
        found.append(f"monitoring desynchronised: {trace['desyncs']}")
    if not trace.get("calls"):
        found.append("no hook calls recorded")

    nodes = list(analysis.walk(trace.get("calls", [])))
    for node in nodes:
        if not node.get("name"):
            found.append("a recorded call has no hook name")
            break
    counted = trace.get("stats", {}).get("total_calls")
    if counted is not None and counted != len(nodes):
        found.append(f"stats claim {counted} calls, the tree holds {len(nodes)}")
    return found


def _provenance(trace: dict[str, Any]) -> list[str]:
    found = []
    environment = trace.get("environment", {})
    if not environment.get("application"):
        found.append("trace does not say which application it came from")
    if not environment.get("pluggy"):
        found.append("trace does not say which pluggy recorded it")

    # An absolute path leaking into a plugin name makes traces machine-specific,
    # which this project has shipped before and does not intend to again.
    for node in analysis.walk(trace.get("calls", [])):
        for impl in node.get("impls", []):
            plugin = str(impl.get("plugin") or "")
            if plugin.startswith("/") or (len(plugin) > 1 and plugin[1] == ":"):
                found.append(f"absolute path in a plugin name: {plugin}")
                return found
    return found


def _drawing(trace: dict[str, Any]) -> list[str]:
    """It must draw with nobody having described this application."""
    found = []
    phases = analysis.resolve_phases(trace, [])
    if not phases:
        found.append("no phase resolved, so nothing would be drawn")
        return found

    variants = flow.phase_variants(analysis.phase_subtrees(trace, phases[0]))
    if not variants:
        found.append("the resolved phase holds no steps")
        return found

    nodes = flow.fold_repetitive(variants[0].flow)
    try:
        svg = dot.render_inline_svg(nodes, trace.get("hookspecs", {}), phase=phases[0].key)
    except Exception as error:  # noqa: BLE001 - any failure here is the finding
        found.append(f"rendering raised {type(error).__name__}: {error}")
        return found
    if "<svg" not in svg:
        found.append("renderer produced no svg")
    return found


def main(argv: list[str] | None = None) -> int:
    paths = argv if argv is not None else sys.argv[1:]
    if not paths:
        print("usage: python -m hook_atlas.validate <trace.json>...", file=sys.stderr)
        return 2

    failed = False
    for name in paths:
        trace = analysis.load_trace(Path(name))
        found = problems(trace)
        environment = trace.get("environment", {})
        label = f"{environment.get('application', '?')} {environment.get('version', '')}".strip()
        if found:
            failed = True
            print(f"FAIL {name} ({label})")
            for problem in found:
                print(f"       {problem}")
        else:
            stats = trace.get("stats", {})
            print(
                f"ok   {name} ({label}): {stats.get('unique_hooks')} hooks, "
                f"{stats.get('total_calls')} calls"
            )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
