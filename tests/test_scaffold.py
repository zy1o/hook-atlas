"""The mkdocs project `init-site` writes.

What is checked is what the guide promises: the files exist, the build script
survives a failing test suite, and the config it starts from is the real one.
"""

from __future__ import annotations

import os
import stat

from hook_atlas import config, scaffold


def test_it_writes_a_project(tmp_path):
    written = scaffold.init_site(tmp_path / "site", name="demo", command="pytest -q")

    names = {path.name for path in written}
    assert names == {"atlas.toml", "mkdocs.yml", "build.sh", "README.md", ".gitignore"}
    assert (tmp_path / "site" / "docs").is_dir()


def test_the_build_script_is_executable(tmp_path):
    scaffold.init_site(tmp_path / "site", name="demo", command="pytest -q")

    mode = (tmp_path / "site" / "build.sh").stat().st_mode
    assert mode & stat.S_IXUSR


def test_a_failing_suite_still_produces_a_page(tmp_path):
    """hook-atlas returns the traced command's exit code, and `set -e` would
    stop the build there - on exactly the run somebody most wants to look at."""
    scaffold.init_site(tmp_path / "site", name="demo", command="pytest -q")
    script = (tmp_path / "site" / "build.sh").read_text()

    traced = next(line for line in script.splitlines() if "hook-atlas trace" in line)
    assert traced.rstrip().endswith("|| true"), traced


def test_the_command_lands_in_the_script(tmp_path):
    scaffold.init_site(tmp_path / "site", name="demo", command="pytest -q -k smoke")

    assert "pytest -q -k smoke" in (tmp_path / "site" / "build.sh").read_text()


def test_the_suite_is_traced_from_the_project_not_the_site(tmp_path):
    """The site directory lives inside the repository it documents; running the
    command there would find no tests."""
    scaffold.init_site(tmp_path / "site", name="demo", command="pytest -q")
    script = (tmp_path / "site" / "build.sh").read_text()

    assert "PROJECT_ROOT" in script
    assert 'cd "$PROJECT_ROOT"' in script


def test_it_starts_from_a_real_config(tmp_path):
    """Not a stub: the shipped pytest description, which is known to work."""
    scaffold.init_site(tmp_path / "site", name="demo", command="pytest -q")

    written = (tmp_path / "site" / "atlas.toml").read_text()
    assert written == config.example("pytest").read_text()
    assert config.parse(__import__("tomllib").loads(written)).phases


def test_generated_files_are_not_accidentally_empty(tmp_path):
    for path in scaffold.init_site(tmp_path / "site", name="demo", command="pytest -q"):
        assert path.stat().st_size > 0, path.name


def test_the_name_reaches_the_site_title(tmp_path):
    scaffold.init_site(tmp_path / "site", name="Payments API", command="pytest -q")

    assert "Payments API hook flow" in (tmp_path / "site" / "mkdocs.yml").read_text()
    assert os.path.exists(tmp_path / "site" / "mkdocs.yml")
