"""The validator has to catch things, not just pass everything.

Each of these is a real failure mode: the tracer losing its place, a trace that
cannot say what produced it, a machine-specific path baked into a committed
file, and an application whose hooks do not resolve to any phase.
"""

from __future__ import annotations

from hook_atlas import validate


def good_trace():
    return {
        "schema_version": 3,
        "calls": [{"name": "app_start", "children": [], "impls": [{"plugin": "app.core"}]}],
        "hookspecs": {},
        "stats": {"total_calls": 1, "unique_hooks": 1},
        "environment": {"application": "app", "version": "1.0", "pluggy": "1.6.0"},
        "desyncs": [],
    }


def test_a_good_trace_has_no_problems():
    assert validate.problems(good_trace()) == []


def test_desyncs_are_reported():
    trace = good_trace()
    trace["desyncs"] = [{"expected": "a", "got": "b"}]

    assert any("desynchronised" in problem for problem in validate.problems(trace))


def test_an_empty_trace_is_reported():
    trace = good_trace()
    trace["calls"] = []

    assert any("no hook calls" in problem for problem in validate.problems(trace))


def test_a_miscounted_trace_is_reported():
    trace = good_trace()
    trace["stats"]["total_calls"] = 99

    assert any("stats claim 99" in problem for problem in validate.problems(trace))


def test_an_unattributed_trace_is_reported():
    trace = good_trace()
    trace["environment"]["application"] = ""

    assert any("which application" in problem for problem in validate.problems(trace))


def test_an_absolute_path_in_a_plugin_name_is_reported():
    """Committed traces have to be reproducible on somebody else's machine."""
    trace = good_trace()
    trace["calls"][0]["impls"] = [{"plugin": "/home/someone/project/conftest.py"}]

    assert any("absolute path" in problem for problem in validate.problems(trace))


def test_an_application_nobody_described_still_draws():
    """The flat default is what stops an unknown application producing nothing."""
    trace = good_trace()
    trace["calls"] = [{"name": f"app_{index}", "children": [], "impls": []} for index in range(5)]
    trace["stats"]["total_calls"] = 5

    assert validate.problems(trace) == []


def test_main_reports_failure_with_an_exit_code(tmp_path, capsys):
    import json

    bad = tmp_path / "bad.json"
    trace = good_trace()
    trace["desyncs"] = [{"expected": "a"}]
    bad.write_text(json.dumps(trace))

    assert validate.main([str(bad)]) == 1
    assert "FAIL" in capsys.readouterr().out


# --------------------------------------------------------------------------
# the command line, which is how anyone actually reaches any of this


def test_the_trace_subcommand_keeps_the_program_s_own_separator():
    """`hook-atlas trace -- tox r -e py -- --lf` must deliver the second `--`.

    Only the first belongs to us; the rest is the command's business.
    """
    from hook_atlas import cli

    assert cli._strip_leading_separator(["--", "tox", "r", "--", "--lf"]) == [
        "tox",
        "r",
        "--",
        "--lf",
    ]
    assert cli._strip_leading_separator(["pytest", "-q"]) == ["pytest", "-q"]


def test_draw_writes_a_page_someone_can_open(tmp_path):
    """The point of the tool is the picture, so `draw` has to produce something
    a browser shows without a site around it."""
    import json

    from hook_atlas import cli

    trace = tmp_path / "t.json"
    trace.write_text(
        json.dumps(
            {
                "calls": [{"name": "app_start", "children": [], "impls": []}],
                "hookspecs": {},
                "stats": {"total_calls": 1, "unique_hooks": 1},
                "environment": {"application": "app", "version": "2.0", "pluggy": "1.6.0"},
                "desyncs": [],
            }
        )
    )

    page = cli.draw(trace, tmp_path / "flow.html")
    text = page.read_text()

    assert text.startswith("<!doctype html>")
    assert "app 2.0" in text
    assert "<svg" in text and "app_start" in text


def test_draw_writes_bare_svg_when_asked_for_one(tmp_path):
    import json

    from hook_atlas import cli

    trace = tmp_path / "t.json"
    trace.write_text(
        json.dumps(
            {
                "calls": [{"name": "app_start", "children": [], "impls": []}],
                "hookspecs": {},
                "stats": {},
                "environment": {},
                "desyncs": [],
            }
        )
    )

    text = cli.draw(trace, tmp_path / "flow.svg").read_text()

    assert text.lstrip().startswith("<svg")
