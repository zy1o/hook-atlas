"""A project's own hooks, for the template check to find.

Deliberately does nothing but say so. The point is that an implementation
belonging to the *project* rather than to pytest exists at all: it has to be
traced, attributed to this file, classified as not-pytest's, rendered in the
hook table with its ordering marker, and revealed by the filter. A suite with
no conftest exercises none of that, and the page it produces looks the same
whether the attribution works or not.
"""

import pytest

SANITY = "sample-project conftest hook ran"


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    # printed so the trace is not the only evidence the hook really ran
    print(SANITY)


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    pass
