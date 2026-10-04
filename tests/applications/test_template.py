"""Does the thing the guide tells people to do actually work?

`docs/your-own-atlas.md` promises four commands and a page, then an mkdocs site
on top. This runs both, end to end, against a committed sample project whose
conftest implements hooks of its own - so the page can be checked for the thing
that distinguishes a useful atlas from a picture of a framework: *your* code,
attributed to you, told apart from the framework's.

Marked `template` and skipped by default: it needs mkdocs, mkdocs-material and
the Graphviz binary. CI runs it on every change and weekly, because what it
depends on - mkdocs, its theme, pytest itself - drifts underneath it.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.template

SAMPLE = Path(__file__).resolve().parent.parent / "sample-project"
SANITY = "sample-project conftest hook ran"


def run(command: list[str], cwd: Path, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, **kwargs)


@pytest.fixture(scope="module")
def project(tmp_path_factory) -> Path:
    """A copy of the sample project, so nothing is written into the repository."""
    directory = tmp_path_factory.mktemp("project")
    shutil.copytree(SAMPLE, directory / "app")
    return directory / "app"


@pytest.fixture(scope="module")
def page(project: Path) -> str:
    """The four commands from the guide, run exactly as written."""
    atlas = project / "atlas.toml"

    traced = run(
        [sys.executable, "-m", "hook_atlas.cli", "trace", "--", "pytest", "-q", "-s", "tests/"],
        project,
    )
    assert SANITY in traced.stdout, f"the project's own hook did not run\n{traced.stdout}"

    written = run(
        [sys.executable, "-m", "hook_atlas.cli", "config", "--example", "pytest"], project
    )
    atlas.write_text(written.stdout)

    drawn = run([sys.executable, "-m", "hook_atlas.cli", "draw", "--config", "atlas.toml"], project)
    assert drawn.returncode == 0, drawn.stderr

    html = (project / "hook-flow.html").read_text()
    # CI keeps the page as an artifact: the deliverable is something to look at,
    # and no number of passing assertions shows what it looks like.
    keep = os.environ.get("HOOK_ATLAS_TEMPLATE_OUT")
    if keep:
        destination = Path(keep)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(html)
    return html


def test_the_page_has_a_diagram_for_every_phase(page):
    headings = re.findall(r"<h2>([^<]+)</h2>", page)

    assert "Startup and configuration" in headings
    assert "The run-test protocol" in headings
    assert "Every hook observed" in headings
    assert page.count("<svg ") >= 4


def test_the_page_lists_the_hooks_that_ran(page):
    rows = re.findall(r"<tr><td>.*?</tr>", page, re.S)

    assert len(rows) > 20, "a pytest run touches more hooks than this"
    assert "pytest_runtest_protocol" in page
    assert "pytest_collection" in page


def test_the_project_s_own_hooks_are_attributed_to_it(page):
    """The sanity check. A conftest implementation has to be traced, attributed
    to the file, and told apart from pytest's own - none of which a page made
    only of framework internals would show.

    Other things may be external too, and should be: whatever pytest plugins
    happen to be installed are not pytest either. What is asserted is that
    *ours* is found, not that nothing else is.
    """
    rows = {
        re.search(r"<code>(pytest_\w+)</code>", row).group(1): row
        for row in re.findall(r"<tr><td>.*?</tr>", page, re.S)
        if "ha-external" in row
    }

    for hook in ("pytest_configure", "pytest_collection_modifyitems"):
        assert hook in rows, f"{hook} was not attributed to anything outside pytest"
        assert "conftest.py" in rows[hook], rows[hook]


def test_the_ordering_markers_survive(page):
    """`trylast` on our pytest_configure is why it runs where it does."""
    row = next(
        row
        for row in re.findall(r"<tr><td>.*?</tr>", page, re.S)
        if "pytest_configure" in row and "ha-external" in row
    )

    assert "trylast" in row


def test_the_filter_is_offered(page):
    assert "ha-hide-internal" in page
    assert "ha-filter" in page


def test_hooks_link_to_pytest_s_documentation(page):
    assert "docs.pytest.org" in page


def test_the_page_needs_nothing_else_to_view(page):
    assert page.startswith("<!doctype html>")
    assert "<link" not in page
    assert "src=" not in page


# --------------------------------------------------------------------------
# the site the guide offers on top


@pytest.fixture(scope="module")
def site(project: Path) -> Path:
    """`init-site`, then the build script it writes, then mkdocs."""
    if shutil.which("mkdocs") is None:
        pytest.skip("mkdocs is not installed")

    created = run(
        [
            sys.executable,
            "-m",
            "hook_atlas.cli",
            "init-site",
            "hook-flow",
            "--name",
            "Sample",
            "--command",
            "pytest -q tests/",
        ],
        project,
    )
    assert created.returncode == 0, created.stderr

    directory = project / "hook-flow"
    built = run(["./build.sh"], directory, env={**os.environ, "PATH": os.environ["PATH"]})
    assert built.returncode == 0, built.stderr

    rendered = run(["mkdocs", "build", "--strict"], directory)
    assert rendered.returncode == 0, rendered.stderr
    return directory


def test_init_site_writes_a_working_project(site: Path):
    for name in ("atlas.toml", "mkdocs.yml", "build.sh", "README.md"):
        assert (site / name).is_file(), name
    assert (site / "docs" / "index.md").is_file()


def test_the_published_site_carries_the_whole_page(site: Path):
    html = (site / "site" / "index.html").read_text()

    assert "Every hook observed" in html
    assert "<svg " in html
    assert "ha-hide-internal" in html
    assert "ha-impl ha-external" in html, "the project's own hooks reached the site"
    assert "md-header" in html, "mkdocs-material rendered it"
