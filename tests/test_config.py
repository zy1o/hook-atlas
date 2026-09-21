"""Describing an application, and the example that proves the format carries.

The pytest example is not decoration. It is the config behind a published site,
so if it stops loading, or stops meaning what that site means, a real thing
broke. pytest-hook-atlas tests its own phases against this file.
"""

from __future__ import annotations

import pytest

from hook_atlas import config


def test_nothing_configured_is_a_valid_config():
    """The default has to be usable, because most runs will not have a config."""
    empty = config.parse({})

    assert empty.phases == ()
    assert empty.links.url_for("any_hook") is None
    assert empty.internal == ()


def test_phases_keep_the_order_they_are_written_in():
    """Order is meaning: it decides column order and therefore colour."""
    parsed = config.parse({"phase": [{"key": "b", "title": "B"}, {"key": "a", "title": "A"}]})

    assert [phase.key for phase in parsed.phases] == ["b", "a"]


def test_duplicate_phase_keys_are_refused():
    """Keys become CSS classes and heading anchors; duplicates collide silently."""
    with pytest.raises(config.ConfigError, match="duplicate phase keys"):
        config.parse({"phase": [{"key": "a", "title": "A"}, {"key": "a", "title": "Again"}]})


def test_a_phase_without_a_key_says_which_one():
    with pytest.raises(config.ConfigError, match="phase 2 has no key"):
        config.parse({"phase": [{"key": "a", "title": "A"}, {"title": "B"}]})


def test_internal_prefixes_are_derived_from_the_application_name():
    assert config.parse({"application": "tox"}).internal == ("tox.", "_tox.")


def test_internal_prefixes_can_be_given_explicitly():
    parsed = config.parse({"application": "tox", "internal": ["tox._internals."]})

    assert parsed.internal == ("tox._internals.",)


def test_documentation_covers_only_the_namespaces_it_names():
    parsed = config.parse(
        {
            "docs": {
                "base_url": "https://example/ref.html",
                "anchor_prefix": "app.hookspec",
                "namespaces": ["app.hookspecs"],
            }
        }
    )

    assert parsed.links.url_for("app_go", "app.hookspecs").endswith("#app.hookspec.app_go")
    assert parsed.links.url_for("plugin_go", "someplugin.hooks") is None


def test_a_broken_file_says_so_rather_than_raising_toml_internals(tmp_path):
    broken = tmp_path / "atlas.toml"
    broken.write_text("application = [unclosed\n")

    with pytest.raises(config.ConfigError, match="not valid TOML"):
        config.load(broken)


# --------------------------------------------------------------------------
# the shipped pytest example


def test_the_pytest_example_loads():
    parsed = config.load(config.example("pytest"))

    assert parsed.application == "pytest"
    assert [phase.key for phase in parsed.phases] == [
        "startup",
        "collection",
        "runtest",
        "finish",
    ]


def test_the_pytest_example_keeps_the_xdist_fallback():
    """Without it, a distributed run's controlling process is drawn empty: it
    never calls pytest_runtest_protocol, only its workers do."""
    parsed = config.load(config.example("pytest"))
    runtest = next(phase for phase in parsed.phases if phase.key == "runtest")

    assert runtest.fallback_anchors == ("pytest_runtestloop",)


def test_the_pytest_example_links_only_pytest_s_own_hooks():
    links = config.load(config.example("pytest")).links

    assert links.url_for("pytest_configure", "_pytest.hookspec")
    assert links.url_for("pytest_xdist_setupnodes", "xdist.newhooks") is None


def test_an_unknown_example_says_which_one():
    with pytest.raises(config.ConfigError, match="no example config"):
        config.example("nothing-like-this")


# --------------------------------------------------------------------------
# documentation that does not cover everything it might


def test_links_are_withheld_for_hooks_a_page_does_not_document():
    """Namespaces say what the documentation is *meant* to cover; `documented`
    says what a particular page turns out to hold. They differ when a version's
    own docs are gone and something newer stands in, and a hook removed since
    is then in the right namespace and missing from the page."""
    from hook_atlas.doclinks import DocLinks

    links = DocLinks(
        base_url="https://example/ref.html",
        anchor_prefix="app.hookspec",
        namespaces=frozenset({"app.hookspecs"}),
        documented=frozenset({"app_still_here"}),
    )

    assert links.url_for("app_still_here", "app.hookspecs")
    assert links.url_for("app_removed_since", "app.hookspecs") is None


def test_without_a_documented_set_everything_in_the_namespace_links():
    from hook_atlas.doclinks import DocLinks

    links = DocLinks(
        base_url="https://example/ref.html",
        anchor_prefix="app.hookspec",
        namespaces=frozenset({"app.hookspecs"}),
    )

    assert links.url_for("anything_at_all", "app.hookspecs")
