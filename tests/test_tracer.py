"""The tracer, against a plugin manager built for the test.

Nothing here imports pytest as a subject - the point of this package is that it
does not know what application it is looking at.
"""

from __future__ import annotations

import pluggy
import pytest

from hook_atlas import tracer

hookspec = pluggy.HookspecMarker("demo")
hookimpl = pluggy.HookimplMarker("demo")


class Spec:
    @hookspec
    def demo_start(self, value): ...

    @hookspec(firstresult=True)
    def demo_pick(self): ...


class Plugin:
    @hookimpl
    def demo_start(self, value):
        return value

    @hookimpl
    def demo_pick(self):
        return 1


def manager():
    pm = pluggy.PluginManager("demo")
    pm.add_hookspecs(Spec)
    pm.register(Plugin(), name="demo_plugin")
    return pm


def test_attach_records_calls_in_order(tracer_globals):
    pm = manager()
    recorder = tracer_globals.attach(pm)

    pm.hook.demo_start(value=1)
    pm.hook.demo_pick()
    recorded = recorder.to_dict()

    assert [node["name"] for node in recorded["calls"]] == ["demo_start", "demo_pick"]


def test_the_trace_names_the_application_not_pytest(tracer_globals):
    pm = manager()
    recorder = tracer_globals.attach(pm)

    pm.hook.demo_start(value=1)
    environment = recorder.to_dict()["environment"]

    assert environment["application"] == "demo"
    assert "pytest" not in environment


def test_hookspec_semantics_are_read_from_the_live_manager():
    specs = tracer.hookspec_metadata(manager())

    assert specs["demo_pick"]["firstresult"] is True
    assert specs["demo_start"]["firstresult"] is False
    assert specs["demo_start"]["declared_in"].endswith("test_tracer")


def test_watch_traces_a_manager_it_did_not_create(tracer_globals):
    """The whole point: reaching a manager somebody else constructed."""
    tracer_globals.watch()

    pm = manager()
    pm.hook.demo_start(value=1)
    recorded = tracer_globals._recorder.to_dict()

    assert [node["name"] for node in recorded["calls"]] == ["demo_start"]


def test_unwatch_puts_the_constructor_back(tracer_globals):
    before = pluggy.PluginManager.__init__
    tracer_globals.watch()
    tracer_globals.unwatch()

    assert pluggy.PluginManager.__init__ is before


def test_watch_can_select_which_application_to_trace(tracer_globals):
    tracer_globals.watch(select=lambda name: name == "wanted")

    pluggy.PluginManager("unwanted")
    assert tracer_globals._recorder is None
    pluggy.PluginManager("wanted")
    assert tracer_globals._recorder is not None


def test_declared_in_is_a_module_even_when_the_namespace_is_a_class():
    """pytest passes a module, where __name__ is the module path. Applications
    that pass a class got the class name, which resolves to no distribution and
    matches no documented namespace."""
    specs = tracer.hookspec_metadata(manager())

    assert specs["demo_start"]["declared_in"] == __name__


def test_a_deleted_working_directory_does_not_break_naming(tmp_path, monkeypatch):
    """Test suites chdir into temporary directories and delete them.

    os.getcwd() then raises, and a tracer that lets that escape has broken a
    program it was only supposed to watch. Found against datasette's suite.
    """
    doomed = tmp_path / "gone"
    doomed.mkdir()
    monkeypatch.chdir(doomed)
    doomed.rmdir()

    class Impl:
        plugin_name = "/somewhere/conftest.py"

    assert tracer._plugin_name(Impl()) == "/somewhere/conftest.py"


def test_a_manager_built_before_watch_is_never_seen(tracer_globals):
    """The one hard constraint the documentation warns about.

    watch() wraps the constructor, so anything already constructed came from
    the original and is invisible. Documented as a warning, and therefore worth
    a test - a reader following it deserves it to be true.
    """
    before = manager()
    tracer_globals.watch()
    after = manager()

    before.hook.demo_start(value=1)
    after.hook.demo_start(value=2)
    recorded = [node["name"] for node in tracer_globals._recorder.to_dict()["calls"]]

    assert recorded == ["demo_start"], "only the manager built after watch() is traced"


def test_the_guard_skips_rather_than_clobbering():
    """Guard the guard.

    The `tracer_globals` fixture is what stops a test stealing a recording that
    belongs to something outside the test session - CI traces pytest while it
    runs this suite. If it ever stops skipping, the failure is silent: a real
    trace quietly replaced by a shorter one. So the condition is checked
    directly rather than trusted.
    """
    from conftest import tracer_globals

    borrow = tracer_globals.__wrapped__  # the fixture body, undecorated

    tracer._recorder = object()
    try:
        with pytest.raises(BaseException, match="would clobber it"):
            next(borrow())
    finally:
        tracer._recorder = None
