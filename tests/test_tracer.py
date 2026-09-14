"""The tracer, against a plugin manager built for the test.

Nothing here imports pytest as a subject - the point of this package is that it
does not know what application it is looking at.
"""

from __future__ import annotations

import pluggy

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


def test_attach_records_calls_in_order():
    pm = manager()
    recorder = tracer.attach(pm)
    try:
        pm.hook.demo_start(value=1)
        pm.hook.demo_pick()
        recorded = recorder.to_dict()
    finally:
        tracer._recorder = None

    assert [node["name"] for node in recorded["calls"]] == ["demo_start", "demo_pick"]


def test_the_trace_names_the_application_not_pytest():
    pm = manager()
    recorder = tracer.attach(pm)
    try:
        pm.hook.demo_start(value=1)
        environment = recorder.to_dict()["environment"]
    finally:
        tracer._recorder = None

    assert environment["application"] == "demo"
    assert "pytest" not in environment


def test_hookspec_semantics_are_read_from_the_live_manager():
    specs = tracer.hookspec_metadata(manager())

    assert specs["demo_pick"]["firstresult"] is True
    assert specs["demo_start"]["firstresult"] is False
    assert specs["demo_start"]["declared_in"].endswith("test_tracer")


def test_watch_traces_a_manager_it_did_not_create():
    """The whole point: reaching a manager somebody else constructed."""
    tracer.watch()
    try:
        pm = manager()
        pm.hook.demo_start(value=1)
        recorded = tracer._recorder.to_dict()
    finally:
        tracer.unwatch()
        tracer._recorder = None

    assert [node["name"] for node in recorded["calls"]] == ["demo_start"]


def test_unwatch_puts_the_constructor_back():
    before = pluggy.PluginManager.__init__
    tracer.watch()
    tracer.unwatch()
    tracer._recorder = None

    assert pluggy.PluginManager.__init__ is before


def test_watch_can_select_which_application_to_trace():
    tracer.watch(select=lambda name: name == "wanted")
    try:
        pluggy.PluginManager("unwanted")
        assert tracer._recorder is None
        pluggy.PluginManager("wanted")
        assert tracer._recorder is not None
    finally:
        tracer.unwatch()
        tracer._recorder = None


def test_declared_in_is_a_module_even_when_the_namespace_is_a_class():
    """pytest passes a module, where __name__ is the module path. Applications
    that pass a class got the class name, which resolves to no distribution and
    matches no documented namespace."""
    specs = tracer.hookspec_metadata(manager())

    assert specs["demo_start"]["declared_in"] == __name__
