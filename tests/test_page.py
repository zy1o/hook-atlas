"""The self-contained page: what somebody gets from `hook-atlas draw`.

This is the output the documentation promises, so what is checked here is what
the guide claims: phases separated, every hook listed with the plugins behind
it in call order, and a filter for the application's own - appearing only when
there is something of yours to reveal.
"""

from __future__ import annotations

import re

from hook_atlas import config
from hook_atlas.render import page


def impl(plugin, module, hook, **flags):
    """One entry as the tracer records it: pluggy's registered name, plus where
    the implementation actually lives."""
    entry = {
        "plugin": plugin,
        "module": module,
        "function": hook,
        "wrapper": False,
        "hookwrapper": False,
        "tryfirst": False,
        "trylast": False,
    }
    entry.update(flags)
    return entry


def trace(*, extra_impls=()):
    """A small run: one hook pytest implements, one the project does."""
    calls = [
        {
            "name": "app_configure",
            "children": [],
            "impls": [impl("logging", "myapp.logging", "app_configure"), *extra_impls],
        },
        {
            "name": "app_run",
            "children": [],
            "impls": [impl("runner", "myapp.runner", "app_run")],
        },
    ]
    return {
        "schema_version": 3,
        "calls": calls,
        "hookspecs": {
            "app_configure": {"firstresult": False, "historic": True, "declared_in": "myapp.hooks"},
            "app_run": {"firstresult": True, "historic": False, "declared_in": "myapp.hooks"},
        },
        "stats": {"total_calls": 2, "unique_hooks": 2},
        "environment": {"application": "myapp", "version": "1.0", "pluggy": "1.6.0"},
        "scenario": {"id": "run", "argv": ["myapp", "--go"]},
        "desyncs": [],
    }


def described():
    return config.parse(
        {
            "application": "myapp",
            "phase": [
                {"key": "setup", "title": "Setup", "anchors": ["app_configure"]},
                {"key": "run", "title": "Running", "anchors": ["app_run"]},
            ],
            "docs": {
                "base_url": "https://example/hooks.html",
                "anchor_prefix": "myapp.hookspec",
                "namespaces": ["myapp.hooks"],
            },
        }
    )


def test_each_phase_gets_its_own_diagram():
    html = page.render(trace(), described())

    assert re.findall(r"<h2>([^<]+)</h2>", html)[:2] == ["Setup", "Running"]
    assert html.count("<svg ") == 2


def test_every_hook_is_listed_with_who_implements_it():
    html = page.render(trace(), described())

    assert "app_configure" in html and "app_run" in html
    assert "myapp.logging" in html and "myapp.runner" in html
    assert "historic" in html and "firstresult" in html


def test_hooks_link_to_the_documentation_when_there_is_some():
    html = page.render(trace(), described())

    assert "https://example/hooks.html#myapp.hookspec.app_run" in html


def test_the_filter_has_something_to_reveal_only_when_you_do():
    """An application implements most of itself as plugins; the point of the
    checkbox is the handful of entries that are not its own."""
    without = page.render(trace(), described())
    assert "ha-impl ha-external" not in without

    with_yours = page.render(
        trace(extra_impls=[impl("conftest.py", "conftest", "app_configure", tryfirst=True)]),
        described(),
    )
    assert "ha-impl ha-external" in with_yours
    assert "tryfirst" in with_yours


def test_the_page_stands_alone():
    """Somebody tracing their own project has no site and no server."""
    html = page.render(trace(), described())

    assert html.startswith("<!doctype html>")
    assert "<link" not in html, "no external stylesheet"
    assert "src=" not in html, "nothing fetched at view time"
    assert "<style>" in html and "<script>" in html


def test_an_application_nobody_described_still_gets_a_page():
    html = page.render(trace())

    assert "<svg " in html
    assert "app_configure" in html
    assert "example/hooks.html" not in html, "no documentation was configured"


def test_the_page_says_what_produced_it():
    html = page.render(trace(), described())

    assert "myapp --go" in html
    assert "1.6.0" in html
