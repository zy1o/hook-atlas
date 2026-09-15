"""Point hook-atlas at real applications and check nothing goes belly up.

The unit tests use a plugin manager built for the purpose, which proves the
logic and nothing about the world. These run actual programs - tox, datasette,
pytest, devpi - in a subprocess and assert the three things that would make the
tool useless on something nobody anticipated:

* it records hooks at all,
* it draws a diagram without being told what the application's phases are,
* it leaves the program's own behaviour alone, exit code included.

Marked ``applications`` and skipped when the program is not installed, so the
default test run stays fast and offline.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from importlib.metadata import entry_points
from pathlib import Path

import pytest

from hook_atlas import analysis, flow, tracer
from hook_atlas.render import dot

pytestmark = pytest.mark.applications


def run_traced(command: list[str], cwd: Path, destination: Path) -> subprocess.CompletedProcess:
    """Run a command under the tracer, in its own process."""
    script = "import sys; from hook_atlas.cli import run; sys.exit(run(sys.argv[1:]))"
    return subprocess.run(
        [sys.executable, "-c", script, *command],
        cwd=cwd,
        env={**os.environ, tracer.ENV_TRACE_PATH: str(destination)},
        capture_output=True,
        text=True,
    )


def assert_usable_trace(destination: Path, application: str) -> dict:
    """Every guarantee this tool makes about an application it has never seen."""
    assert destination.exists(), "no trace was written"
    trace = json.loads(destination.read_text())

    assert trace["environment"]["application"] == application
    assert trace["environment"]["pluggy"], "pluggy version not recorded"
    assert trace["stats"]["unique_hooks"] > 0, "no hooks recorded at all"
    assert trace["desyncs"] == [], "before/after monitoring got out of step"

    # the hooks it saw must be described, or the diagram has nothing to say
    hooks = {node["name"] for node in analysis.walk(trace["calls"])}
    assert hooks, "no calls recorded"

    # and it must draw, with nobody having described this application
    phases = analysis.resolve_phases(trace, [])
    assert [phase.key for phase in phases] == ["run"]
    variants = flow.phase_variants(analysis.phase_subtrees(trace, phases[0]))
    svg = dot.render_inline_svg(
        flow.fold_repetitive(variants[0].flow), trace["hookspecs"], phase=phases[0].key
    )
    size = re.search(r'<svg width="(\d+)pt" height="(\d+)pt"', svg)
    assert size, "diagram has no dimensions"
    assert 20 < int(size.group(1)) < 20000 and 20 < int(size.group(2)) < 40000
    return trace


def requires(program: str) -> None:
    """Skip unless the program is importable *here*.

    shutil.which consults PATH, which does not necessarily contain the
    interpreter's own bin directory - the entry points do.
    """
    installed = {entry.name for entry in entry_points(group="console_scripts")}
    if program not in installed:
        pytest.skip(f"{program} is not installed in this environment")


def test_tox(tmp_path):
    requires("tox")
    (tmp_path / "tox.ini").write_text(
        "[tox]\nenvlist = py\nskipsdist = true\n\n[testenv]\ncommands = python -c 'pass'\n"
    )
    destination = tmp_path / "trace.json"

    result = run_traced(["tox", "list"], tmp_path, destination)

    assert result.returncode == 0, result.stderr
    trace = assert_usable_trace(destination, "tox")
    assert any(name.startswith("tox_") for name in trace["hookspecs"])


def test_pytest(tmp_path):
    (tmp_path / "test_x.py").write_text("def test_a():\n    assert True\n")
    destination = tmp_path / "trace.json"

    result = run_traced(
        ["pytest", "-q", "-p", "no:cacheprovider", str(tmp_path)], tmp_path, destination
    )

    assert result.returncode == 0, result.stderr
    trace = assert_usable_trace(destination, "pytest")
    # attaching at construction sees what a plugin entry point cannot
    hooks = {node["name"] for node in analysis.walk(trace["calls"])}
    assert "pytest_cmdline_parse" in hooks


def test_datasette(tmp_path):
    requires("datasette")
    destination = tmp_path / "trace.json"

    result = run_traced(["datasette", "--help"], tmp_path, destination)

    assert result.returncode == 0, result.stderr
    assert_usable_trace(destination, "datasette")


def test_devpi(tmp_path):
    requires("devpi")
    destination = tmp_path / "trace.json"

    result = run_traced(["devpi", "--version"], tmp_path, destination)

    assert result.returncode == 0, result.stderr
    assert_usable_trace(destination, "devpiclient")


def test_a_failing_program_still_fails(tmp_path):
    """A wrapper that turns a red build green is worse than no wrapper."""
    (tmp_path / "test_x.py").write_text("def test_a():\n    assert False\n")
    destination = tmp_path / "trace.json"

    result = run_traced(
        ["pytest", "-q", "-p", "no:cacheprovider", str(tmp_path)], tmp_path, destination
    )

    assert result.returncode != 0, "pytest failed but the wrapper reported success"
    assert_usable_trace(destination, "pytest")


def test_output_is_left_alone(tmp_path):
    """Whatever the program prints, it prints - the tracer is not in the way."""
    (tmp_path / "test_x.py").write_text("def test_a():\n    print('MARKER')\n")
    destination = tmp_path / "trace.json"

    result = run_traced(
        ["pytest", "-q", "-s", "-p", "no:cacheprovider", str(tmp_path)], tmp_path, destination
    )

    assert "MARKER" in result.stdout


def test_a_command_that_builds_no_plugin_manager_says_so(tmp_path):
    """`pytest --version` answers before building one. Nothing to trace is a
    result, not a malfunction, and the difference has to be visible."""
    destination = tmp_path / "trace.json"

    result = run_traced(["pytest", "--version"], tmp_path, destination)

    assert result.returncode == 0
    assert not destination.exists()
    assert "nothing to trace" in result.stderr
