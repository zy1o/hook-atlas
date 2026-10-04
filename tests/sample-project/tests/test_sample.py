"""Enough shape to put something in each phase: a fixture, a parametrised test,
a skip. Not a test of hook-atlas - this suite exists to be traced."""

import pytest


@pytest.fixture
def database():
    return {"rows": 0}


@pytest.mark.parametrize("count", [0, 1])
def test_rows(database, count):
    assert database["rows"] <= count


def test_plain():
    assert True


@pytest.mark.skip(reason="skipped on purpose: the run-test protocol differs")
def test_skipped():
    raise AssertionError
