"""Shared fixtures.

The important one guards the tracer's module-level recorder. There is exactly
one, on purpose - interleaving two managers into a single tree would be
nonsense - which means a test that grabs it is not isolated from anything else
grabbing it, including a trace running *outside* the test session.

That is not hypothetical. CI traces pytest while it runs this suite, and a test
that reset the recorder in a `finally` destroyed the outer recording, then let
the tool report that there had been nothing to trace.
"""

from __future__ import annotations

import pytest

from hook_atlas import tracer


@pytest.fixture
def tracer_globals():
    """Borrow the tracer's global state, and give it back.

    Skips when something is already recording, because there is nothing useful
    to do in that case and clobbering it is actively harmful. Use this rather
    than setting `tracer._recorder` by hand: a hand-rolled `finally` cannot tell
    the difference between state it created and state it inherited.
    """
    if tracer._recorder is not None:
        pytest.skip("a trace is already running; this test would clobber it")

    try:
        yield tracer
    finally:
        # unwatch() restores the constructor only if we wrapped it, so this is
        # safe whether the test called watch() or only attach()
        tracer.unwatch()
        tracer._recorder = None
