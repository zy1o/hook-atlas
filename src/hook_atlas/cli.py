"""A minimal front end: trace a command, write a trace, draw it.

Not the finished ``hook-atlas trace`` - that needs entry-point resolution for
``python -m`` and bare scripts, process naming, and streaming for programs that
never exit. This is the part that can be pointed at a real application today,
and it exists so that CI can do exactly that.
"""

from __future__ import annotations

import runpy
import sys
from importlib.metadata import entry_points
from pathlib import Path

from . import analysis, flow, tracer
from .render import dot


def run(argv: list[str]) -> int:
    """Run ``argv`` under the tracer. Returns the command's own exit code.

    The exit code is the command's, not ours. A wrapper that turned a failing
    program into a passing one would be worse than useless in anyone's CI.
    """
    tracer.watch()
    name, rest = argv[0], argv[1:]
    sys.argv = [name, *rest]

    console = {entry.name: entry for entry in entry_points(group="console_scripts")}
    try:
        if name in console:
            # A console script may *return* its exit code rather than raising
            # SystemExit - pytest's does. Discarding it turned a failing test
            # run into a passing wrapper, which is the one way this tool could
            # actively cause harm in somebody's CI.
            return _exit_code(console[name].load()())
        runpy.run_module(name, run_name="__main__", alter_sys=True)
    except SystemExit as exit_request:
        return _exit_code(exit_request.code)
    finally:
        _report(tracer.write_trace(), name)
    return 0


def _report(written: Path | None, name: str) -> None:
    """Say what happened, on stderr so it never pollutes the program's output.

    A command can finish without ever building a plugin manager - ``pytest
    --version`` answers before it builds one - and then there is genuinely
    nothing to record. Saying so is the difference between a tool that found
    nothing and a tool that looks broken.
    """
    if written is None:
        print(
            f"hook-atlas: {name} created no plugin manager, so there was nothing to trace",
            file=sys.stderr,
        )
    else:
        print(f"hook-atlas: wrote {written}", file=sys.stderr)


def _exit_code(returned: object) -> int:
    """What a program meant by what it returned or raised.

    Mirrors the interpreter: None is success, an int is itself, anything else
    is a message printed to stderr and a failure.
    """
    if returned is None:
        return 0
    if isinstance(returned, int):
        return returned
    return 1


def draw(trace_path: Path, out_path: Path) -> Path:
    """Draw a trace with no configuration at all - the unconfigured path."""
    trace = analysis.load_trace(trace_path)
    phase = analysis.resolve_phases(trace, [])[0]
    variants = flow.phase_variants(analysis.phase_subtrees(trace, phase))
    nodes = flow.fold_repetitive(variants[0].flow) if variants else []
    out_path.write_text(dot.render_inline_svg(nodes, trace["hookspecs"], phase=phase.key))
    return out_path


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: hook-atlas-trace <command> [args...]", file=sys.stderr)
        return 2
    return run(sys.argv[1:])
