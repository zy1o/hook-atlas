"""What an application nobody has described must still get.

These are the guarantees that let `hook-atlas` be pointed at something nobody
anticipated. Every one of them was a real failure first: the renderer raised
KeyError on a phase key it did not recognise, and a trace matching no anchor
produced a page with a hook table and no diagram at all.
"""

from __future__ import annotations

import re

from hook_atlas import analysis, flow
from hook_atlas.render import css, dot


def call(name, children=()):
    return {"name": name, "children": [dict(c) for c in children], "impls": []}


def trace(*names):
    return {
        "calls": [call(n) for n in names],
        "hookspecs": {},
        "stats": {},
        "environment": {},
        "desyncs": [],
    }


APP = trace("app_configure", "app_start", "app_work", "app_finish")


def test_an_application_with_no_phases_gets_one():
    assert [p.key for p in analysis.resolve_phases(APP, [])] == ["run"]


def test_phases_that_match_nothing_fall_back_to_the_whole_run():
    """The failure this exists to prevent is a page with no diagram on it."""
    irrelevant = [analysis.Phase("x", "X", ("never_called",), "")]

    assert [p.key for p in analysis.resolve_phases(APP, irrelevant)] == ["run"]


def test_the_whole_run_phase_holds_every_call():
    subtrees = analysis.phase_subtrees(APP, analysis.WHOLE_RUN)

    assert [node["name"] for node in subtrees] == [
        "app_configure",
        "app_start",
        "app_work",
        "app_finish",
    ]


def test_an_unconfigured_application_renders_a_real_diagram():
    phase = analysis.resolve_phases(APP, [])[0]
    nodes = flow.phase_variants(analysis.phase_subtrees(APP, phase))[0].flow

    svg = dot.render_inline_svg(nodes, {}, phase=phase.key)

    size = re.search(r'<svg width="(\d+)pt" height="(\d+)pt"', svg)
    assert size and int(size.group(2)) > 40, "a diagram, not an empty canvas"
    assert "app_work" in svg


def test_a_phase_key_nobody_declared_does_not_crash_the_renderer():
    """`PHASE_HUES[self.phase]` raised KeyError for anything but pytest's four."""
    builder = dot._Builder({}, dot.NO_LINKS, phase="something_new", theme="light")

    assert builder._colours(flow.FlowNode("x"))["fillcolor"]


def test_hooks_render_unlinked_when_no_documentation_is_configured():
    """A guessed URL is a dead anchor, which is the bug this project shipped."""
    svg = dot.render_inline_svg([flow.FlowNode("app_work")], {}, phase="run")

    assert "xlink:href" not in svg


def test_the_stylesheet_covers_whatever_phases_it_is_given():
    sheet = css.stylesheet(["configure", "execute"])

    assert ".ha-configure" in sheet and ".ha-execute" in sheet


def test_more_phases_than_the_palette_still_get_colours():
    keys = [f"phase{index}" for index in range(len(dot.PALETTE) + 3)]

    hues = dot.hues_for(keys)

    assert len(hues) == len(keys)
    assert all(hue.startswith("#") for hue in hues.values())
