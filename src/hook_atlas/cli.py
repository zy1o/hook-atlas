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

import graphviz

from . import analysis, config, flow, scaffold, tracer, validate
from .render import dot, page

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
    """Draw a trace as a self-contained page, or as a bare SVG.

    An `.html` destination gets the whole thing: a diagram per phase the run
    reached, every hook with the plugins behind it, and a filter for the
    application's own. Anything else gets one SVG, because a single image
    cannot hold a table.

    With nothing described, the phases collapse to one holding the whole run -
    an application nobody has configured still gets a picture, rather than an
    empty page or a crash.
    """
    described = described or config.AtlasConfig()
    trace = analysis.load_trace(trace_path)

    if out_path.suffix in (".html", ".md"):
        # markdown for a site that supplies its own page furniture, html for a
        # file somebody opens. Same renderer either way.
        out_path.write_text(page.render(trace, described, standalone=out_path.suffix == ".html"))
        return out_path

    phase = analysis.resolve_phases(trace, described.phases)[0]
    variants = flow.phase_variants(analysis.phase_subtrees(trace, phase))
    nodes = flow.fold_repetitive(variants[0].flow) if variants else []
    out_path.write_text(
        dot.render_inline_svg(
            nodes, trace.get("hookspecs", {}), links=described.links, phase=phase.key
        )
    )
    return out_path


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

    site = sub.add_parser("init-site", help="write an mkdocs project around a trace")
    site.add_argument("directory", type=Path)
    site.add_argument("--name", default=None, help="what to call it; defaults to the directory")
    site.add_argument(
        "--command",
        default="pytest -q",
        help="the command to trace, written into build.sh",
    )
    site.add_argument("--example", default="pytest", help="which shipped config to start from")

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
        try:
            written = draw(args.trace, args.output, described)
        except graphviz.ExecutableNotFound:
            # The `graphviz` package is bindings; the renderer is a separate
            # binary. Without it the traceback comes from graphviz internals,
            # several frames deep, on the first command a new user runs.
            print(
                "hook-atlas: Graphviz is not installed, or `dot` is not on your PATH.\n"
                "            The graphviz Python package is only bindings - the renderer\n"
                "            is a separate program. Try `apt install graphviz`,\n"
                "            `brew install graphviz`, or your platform's equivalent.\n"
                "            The trace itself is fine; only drawing needs this.",
                file=sys.stderr,
            )
            return 1
        print(f"hook-atlas: wrote {written}")
        return 0

    if args.subcommand == "config":
        print(config.example(args.example).read_text(), end="")
        return 0

    if args.subcommand == "init-site":
        written = scaffold.init_site(
            args.directory,
            name=args.name or args.directory.name,
            command=args.command,
            example=args.example,
        )
        for path in written:
            print(f"  {path}")
        print(f"\nnext: cd {args.directory} && ./build.sh && mkdocs serve")
        print("needs mkdocs and mkdocs-material: pip install mkdocs mkdocs-material")
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
