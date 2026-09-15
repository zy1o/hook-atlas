"""The command line: trace a program, draw what it did, check the result.

    hook-atlas trace -- pytest -q tests/
    hook-atlas draw hook-atlas-trace.json -o flow.svg
    hook-atlas check hook-atlas-trace.json

``trace`` is the part that has to be careful. It runs inside somebody else's
program, so it changes nothing about it: the program keeps its own stdout and
its own exit code, and anything this tool has to say goes to stderr.
"""

from __future__ import annotations

import argparse
import os
import runpy
import sys
from importlib.metadata import entry_points
from pathlib import Path

from . import analysis, config, flow, tracer, validate
from .render import dot

DEFAULT_TRACE = Path(tracer.DEFAULT_TRACE_PATH)


def run(argv: list[str]) -> int:
    """Run ``argv`` under the tracer. Returns the command's own exit code."""
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


def _exit_code(returned: object) -> int:
    """What a program meant by what it returned or raised.

    Mirrors the interpreter: None is success, an int is itself, anything else is
    a message and a failure.
    """
    if returned is None:
        return 0
    if isinstance(returned, int):
        return returned
    return 1


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
        print(f"hook-atlas: draw it with  hook-atlas draw {written}", file=sys.stderr)


def draw(
    trace_path: Path,
    out_path: Path,
    described: config.AtlasConfig | None = None,
) -> Path:
    """Draw a trace, one diagram per phase the run actually reached.

    With nothing described, that is a single phase holding the whole run - an
    application nobody has configured still gets a picture, rather than an empty
    page or a crash.
    """
    described = described or config.AtlasConfig()
    trace = analysis.load_trace(trace_path)
    hookspecs = trace.get("hookspecs", {})

    drawings = []
    for phase in analysis.resolve_phases(trace, described.phases):
        variants = flow.phase_variants(analysis.phase_subtrees(trace, phase))
        nodes = flow.fold_repetitive(variants[0].flow) if variants else []
        drawings.append(
            (
                phase,
                dot.render_inline_svg(nodes, hookspecs, links=described.links, phase=phase.key),
            )
        )

    if out_path.suffix == ".html":
        out_path.write_text(_page(drawings, trace))
    else:
        # one file cannot hold several diagrams; the page format is for that
        out_path.write_text(drawings[0][1])
    return out_path


def _page(drawings: list, trace: dict) -> str:
    """Wrap the diagram so a browser shows something readable.

    Standalone rather than styled by a site: someone running this against their
    own project has no site, and telling them to go and build one before they
    can look at the picture would rather defeat the exercise.
    """
    environment = trace.get("environment", {})
    title = f"{environment.get('application', 'hook')} {environment.get('version', '')}".strip()
    stats = trace.get("stats", {})
    body = "\n".join(
        f"<h2>{phase.title}</h2>\n<p>{phase.description}</p>\n{svg}" if len(drawings) > 1 else svg
        for phase, svg in drawings
    )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>hook flow: {title}</title>
<style>
  body {{ font: 14px/1.5 system-ui, sans-serif; margin: 2rem; color: #222; }}
  h2 {{ margin-top: 2.5rem; }}
  p {{ color: #555; }}
  svg {{ max-width: 100%; height: auto; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #1b1b1b; color: #e3e3e3; }}
    p {{ color: #b4b4b4; }}
  }}
</style>
<h1>{title}</h1>
<p>{stats.get("unique_hooks", "?")} distinct hooks, {stats.get("total_calls", "?")} calls,
   recorded with pluggy {environment.get("pluggy", "?")}.</p>
{body}
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hook-atlas",
        description="Trace and draw the hook flow of any pluggy-based application.",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    traced = sub.add_parser("trace", help="run a command and record its hook calls")
    traced.add_argument("-o", "--output", type=Path, default=None, help="where to write the trace")
    # REMAINDER keeps the traced command's own flags intact, including a second
    # `--` that the command itself wants - `tox r -e py -- --lf` must arrive whole
    traced.add_argument("command", nargs=argparse.REMAINDER)

    drawn = sub.add_parser("draw", help="render a trace as SVG or a standalone page")
    drawn.add_argument("trace", type=Path, nargs="?", default=DEFAULT_TRACE)
    drawn.add_argument("-o", "--output", type=Path, default=Path("hook-flow.html"))
    drawn.add_argument(
        "--config", type=Path, default=None, help="describe the application (see docs)"
    )

    checked = sub.add_parser("check", help="report anything wrong with a trace")
    checked.add_argument("trace", type=Path, nargs="*", default=[DEFAULT_TRACE])

    shown = sub.add_parser("config", help="print a config to copy and edit")
    shown.add_argument("--example", default="pytest", help="which shipped example")

    args = parser.parse_args(argv)

    if args.subcommand == "trace":
        # only a leading `--` is ours; anything after the program name is its own
        command = _strip_leading_separator(args.command)
        if not command:
            traced.error("no command given, e.g. hook-atlas trace -- pytest -q")
        if args.output:
            os.environ[tracer.ENV_TRACE_PATH] = str(args.output)
        return run(command)

    if args.subcommand == "draw":
        described = config.load(args.config) if args.config else None
        written = draw(args.trace, args.output, described)
        print(f"hook-atlas: wrote {written}")
        return 0

    if args.subcommand == "config":
        print(config.example(args.example).read_text(), end="")
        return 0

    return validate.main([str(path) for path in args.trace])


def _strip_leading_separator(words: list[str]) -> list[str]:
    """Drop only the `--` that separates our flags from the command.

    A second one belongs to the command - `tox r -e py -- --lf` passes `--lf`
    through to what tox runs - and must survive untouched.
    """
    return words[1:] if words and words[0] == "--" else list(words)


if __name__ == "__main__":
    raise SystemExit(main())
