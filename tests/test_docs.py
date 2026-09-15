"""The documentation has to stay true.

Docs rot quietly: a flag gets renamed, the page still promises it, and the first
person to find out is a stranger following the getting-started guide. These
check the claims that can be checked mechanically.
"""

from __future__ import annotations

import contextlib
import io
import re
from pathlib import Path

import pytest

from hook_atlas import cli, config

DOCS = Path(__file__).resolve().parent.parent / "docs"
COMMAND = re.compile(r"^\s*(?:\$ )?hook-atlas ([a-z-]+)(.*)$", re.M)


def documented_commands():
    """Every `hook-atlas ...` invocation shown anywhere in the docs."""
    for page in sorted(DOCS.glob("*.md")):
        for match in COMMAND.finditer(page.read_text()):
            yield page.name, match.group(1), match.group(2).strip()


def test_the_docs_show_some_commands():
    """Guard the guard: a regex that matched nothing would pass everything."""
    assert len(list(documented_commands())) > 5


@pytest.mark.parametrize(
    ("page", "subcommand", "rest"), list(documented_commands()), ids=lambda value: str(value)[:40]
)
def test_every_documented_command_exists(page, subcommand, rest):
    parser_commands = {"trace", "draw", "check", "config"}

    assert subcommand in parser_commands, f"{page} documents 'hook-atlas {subcommand}'"


@pytest.mark.parametrize(
    ("page", "subcommand", "rest"), list(documented_commands()), ids=lambda value: str(value)[:40]
)
def test_every_documented_flag_exists(page, subcommand, rest):
    """Flags shown in the docs must parse, or the guide sends people at nothing.

    Only what appears before `--` is ours. `tox r -e py312 -- --lf` passes `--lf`
    to tox, and asserting we accept it would be asserting the opposite of the
    behaviour the docs are describing.
    """
    ours = rest.split(" -- ", 1)[0]
    flags = [flag for flag in re.findall(r"(--[a-z-]+)", ours) if flag != "--"]
    if not flags:
        pytest.skip("no flags shown")

    help_text = _help_for(subcommand)
    missing = [flag for flag in flags if flag not in help_text]
    assert not missing, f"{page} shows {missing} for '{subcommand}', which does not accept them"


def _help_for(subcommand: str) -> str:
    """argparse lists every flag it accepts in its help output."""
    shown = io.StringIO()
    with contextlib.redirect_stdout(shown), contextlib.suppress(SystemExit):
        cli.main([subcommand, "--help"])
    return shown.getvalue()


def test_the_example_config_the_docs_point_at_exists():
    """`hook-atlas config --example pytest` is in getting-started and the
    configuring page; it has to produce something that loads."""
    parsed = config.load(config.example("pytest"))

    assert parsed.phases
    assert parsed.application == "pytest"


def test_the_configuring_page_documents_every_config_key():
    """A key nobody documents is a key nobody uses."""
    page = (DOCS / "configuring.md").read_text()
    keys = ["application", "internal", "bookkeeping", "[docs]", "[[phase]]", "fallback_anchors"]

    missing = [key for key in keys if key not in page]
    assert not missing, f"undocumented config keys: {missing}"
