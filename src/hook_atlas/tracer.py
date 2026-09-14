"""Structural capture of a pluggy application's hook call tree.

Installs pluggy's :meth:`~pluggy.PluginManager.add_hookcall_monitoring` and
records every hook call as it happens: the exact nesting, the order, and *which
plugin supplied each implementation*.

Two ways in. :func:`attach` takes a manager you already have, which is what an
application tracing itself wants. :func:`watch` patches
``PluginManager.__init__`` so every manager created afterwards is traced, which
is what tracing somebody else's program requires - there is otherwise no way to
reach a manager you did not construct. Both are supported by pluggy's own
public API once you hold a manager; only *reaching* it needs the patch.

This module is deliberately **standalone**: no imports from the rest of the
package, no syntax newer than Python 3.8, and nothing beyond pluggy. Tracing an
application pinned to an old Python means running there too, where the rest of
this package - which needs 3.11 and ``tomllib`` - cannot be installed. So
capture copies this one file next to the target and loads it on its own.
"""

from __future__ import annotations

import atexit
import inspect
import json
import os
import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pluggy

#: Bumped whenever the on-disk trace format changes incompatibly.
#: 3 replaced ``environment.pytest`` with ``application`` and ``version``, so a
#: trace says what it traced instead of assuming.
SCHEMA_VERSION = 3

#: Hooks whose *original* invocation happens before monitoring can be installed.
#:
#: ``pytest_addoption`` is the earliest hook handed the plugin manager, so it -
#: and the ``pytest_addhooks`` and ``pytest_cmdline_parse`` calls surrounding
#: it - are structurally uncapturable.
#:
#: Note the subtlety: ``pytest_addhooks`` and ``pytest_addoption`` are *historic*
#: hooks, so they replay for plugins registered later. If a conftest or plugin
#: that implements them is loaded after monitoring installs, they will appear in
#: the trace - as a replay, not as the original call. A trace therefore says
#: nothing about whether these ran before it started; they always did.
#:
#: Measured, not assumed: ``tests/test_tracer.py`` fails if this set changes.
#: Hooks an application may call before a tracer can attach. Empty here:
#: monitoring is installed from ``PluginManager.__init__``, so there is nothing
#: earlier to miss. Kept as a seam because a host that attaches later - pytest's
#: ``-p`` plugin entry point did, at ``pytest_addoption`` - has a real prologue
#: it should declare rather than silently omit.
PROLOGUE_HOOKS: frozenset[str] = frozenset()

ENV_TRACE_PATH = "HOOK_ATLAS_TRACE"
ENV_SCENARIO = "HOOK_ATLAS_SCENARIO"
ENV_PROCESS = "HOOK_ATLAS_PROCESS"

#: xdist names its workers gw0, gw1, ... and sets this in each of them. The
#: name is logical rather than a pid, so it stays meaningful in a committed
#: trace long after the process is gone.
#: xdist names its workers here. Generic: any application that forks and
#: wants its children traced separately can set HOOK_ATLAS_PROCESS instead.
ENV_XDIST_WORKER = "PYTEST_XDIST_WORKER"
DEFAULT_TRACE_PATH = "hook-atlas-trace.json"


@dataclass
class CallNode:
    """A single hook call, with the calls it made in turn."""

    name: str
    seq: int
    depth: int
    impls: list[dict[str, Any]]
    children: list[CallNode] = field(default_factory=list)
    raised: bool = False

    @property
    def application(self) -> str:
        """The name pluggy knows this manager by - ``pytest``, ``tox``, ``devpiclient``."""
        return getattr(self.pluginmanager, "project_name", "") or "unknown"

    @property
    def application_version(self) -> str:
        """Version of whatever is being traced, by the same route as hookspec
        sources: ``__version__`` if it exposes one, stdlib metadata otherwise."""
        module = sys.modules.get(self.application)
        version = getattr(module, "__version__", None) if module else None
        return str(version or _distribution_version(self.application) or "")

    def to_dict(self) -> dict[str, Any]:
        node: dict[str, Any] = {
            "name": self.name,
            "seq": self.seq,
            "depth": self.depth,
            "impls": self.impls,
        }
        if self.raised:
            node["raised"] = True
        if self.children:
            node["children"] = [child.to_dict() for child in self.children]
        return node


def _portable_argv() -> list[str]:
    """Command line with the project path made relative.

    Capture runs in a throwaway directory, so the absolute path changes every
    time. Recording it verbatim made every capture produce a diff even when
    nothing about the run had changed - noise in a file whose whole purpose is
    that a real change shows up as a reviewable diff.
    """
    working = os.getcwd()
    portable = []
    for argument in sys.argv[1:]:
        if argument == working:
            portable.append(".")
        elif argument.startswith(working + os.sep):
            portable.append(os.path.relpath(argument, working))
        else:
            portable.append(argument)
    return portable


def _raised(outcome: Any) -> bool:
    """Did the hook call raise?

    pluggy >= 1.3 exposes ``Result.exception``; 0.13 and 1.0 expose
    ``_Result.excinfo``. Both are supported so traces can be captured all the
    way back to pytest 6.0.
    """
    if getattr(outcome, "exception", None) is not None:
        return True
    return getattr(outcome, "excinfo", None) is not None


def _plugin_name(impl: Any) -> str | None:
    """Stable name for the plugin that supplied an implementation.

    pluggy falls back to ``str(id(plugin))`` for plugins registered without a
    name, so that field is a memory address that changes every run. Left alone
    it would make every capture produce a different trace, turning committed
    traces into noise and breaking any content-based comparison between them.
    """
    name = getattr(impl, "plugin_name", None)
    if name is None:
        return None
    name = str(name)
    if name.isdigit():
        return "<anonymous>"
    # A conftest is named by its absolute path, which during capture is a
    # throwaway directory. Relative is both stable across runs and more useful
    # to a reader: "conftest.py" rather than /tmp/hook-atlas-matrix-ubv1z_iu/...
    working = os.getcwd()
    if name.startswith(working + os.sep):
        return os.path.relpath(name, working)
    return name


def _impl_info(impl: Any) -> dict[str, Any]:
    """Summarise a pluggy ``HookImpl``.

    ``plugin_name`` is the provenance we care about: for a conftest it is the
    file path, which is what lets a scenario diagram show *where* a hook
    implementation came from.
    """
    function = getattr(impl, "function", None)
    return {
        "plugin": _plugin_name(impl),
        "module": getattr(function, "__module__", None),
        "function": getattr(function, "__qualname__", None),
        "wrapper": bool(getattr(impl, "wrapper", False)),
        "hookwrapper": bool(getattr(impl, "hookwrapper", False)),
        "tryfirst": bool(getattr(impl, "tryfirst", False)),
        "trylast": bool(getattr(impl, "trylast", False)),
    }


def hookspec_metadata(pluginmanager: Any) -> dict[str, dict[str, Any]]:
    """Static facts about every hook *this plugin manager knows about*.

    Read from the live plugin manager rather than by importing
    ``_pytest.hookspec``, so a project's own hooks are described too. pytest
    contributes 52; pytest-xdist adds 12 more, and any plugin or conftest that
    calls ``add_hookspecs`` contributes its own. Hardcoding pytest's module
    would have meant those rendering with no semantics at all - and it is the
    reason this can be pointed at an arbitrary project.

    Called as late as possible, because plugins register their hookspecs during
    ``pytest_addhooks``: read at ``pytest_addoption`` time, xdist's twelve are
    not there yet.
    """
    metadata: dict[str, dict[str, Any]] = {}
    relay = getattr(pluginmanager, "hook", None)
    for name, caller in sorted(vars(relay).items()) if relay else ():
        if name.startswith("_"):
            continue
        spec = getattr(caller, "spec", None)
        if spec is None:
            continue
        opts = getattr(spec, "opts", None) or {}
        function = getattr(spec, "function", None)
        doc = inspect.getdoc(function) if function else ""
        try:
            argnames = list(inspect.signature(function).parameters) if function else []
        except (TypeError, ValueError):
            argnames = []
        namespace = getattr(spec, "namespace", None)
        metadata[name] = {
            "historic": bool(opts.get("historic")),
            "firstresult": bool(opts.get("firstresult")),
            "argnames": argnames,
            "summary": (doc or "").split("\n\n")[0].replace("\n", " ").strip(),
            # which module declared it - the basis for deciding whose
            # documentation, if any, a hook should link to
            "declared_in": _declaring_module(namespace),
        }
    return metadata


def _declaring_module(namespace):
    """The module path a hookspec namespace belongs to.

    pytest hands ``add_hookspecs`` a module, where ``__name__`` is already the
    module path. Plenty of applications hand it a class or an instance instead,
    and there ``__name__`` is the class - ``Spec`` - which is not a module, so
    resolving its distribution or matching it against a documented namespace
    both fail. ``__module__`` is the module path in exactly those cases.
    """
    if inspect.ismodule(namespace):
        return namespace.__name__
    module = getattr(namespace, "__module__", None)
    if module:
        return module
    return getattr(type(namespace), "__module__", None) or _namespace_name(namespace)


def _distribution_version(package: str) -> str | None:
    """Version of the distribution providing ``package``, from stdlib metadata.

    Deliberately not the ``importlib-metadata`` backport, which would let us use
    ``packages_distributions`` on every Python: the tracer is copied into the
    virtualenv being measured, so any dependency of ours would have to be
    installed there too. Adding anything to the environment under observation is
    a bad habit even when the thing added is benign - it is too easy to overlook
    something that turns out not to be.

    ``importlib.metadata`` itself is stdlib from 3.8, so this costs nothing.
    Only the top-level-to-distribution map has to be built by hand, because
    ``packages_distributions`` arrived in 3.10.
    """
    try:
        import importlib.metadata as metadata
    except ImportError:  # pragma: no cover - importlib.metadata is stdlib from 3.8
        return None

    try:
        for distribution in metadata.distributions():
            top_level = distribution.read_text("top_level.txt") or ""
            names = top_level.split() or [(distribution.metadata["Name"] or "").replace("-", "_")]
            if package in names:
                return distribution.version
    except Exception:  # noqa: BLE001 - provenance is nice to have, never required
        return None
    return None


def hookspec_sources(metadata: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Version of whatever declared each set of hookspecs.

    pytest's own version is already recorded, but a plugin contributing hooks is
    otherwise anonymous: a trace could say a run used twelve xdist hooks without
    saying which xdist.

    ``__version__`` is tried first because it is free and usually right; stdlib
    metadata covers the packages that do not expose one, and resolves a
    top-level name to its distribution - ``xdist`` is shipped by ``pytest-xdist``.
    """
    sources: dict[str, str] = {}
    for spec in metadata.values():
        declared_in = spec.get("declared_in") or ""
        top = declared_in.split(".", 1)[0]
        if not top or declared_in in sources:
            continue
        module = sys.modules.get(top)
        version = getattr(module, "__version__", None) if module else None
        version = version or _distribution_version(top)
        if version:
            sources[declared_in] = str(version)
    return sources


def _namespace_name(namespace: Any) -> str:
    """A readable name for a hookspec namespace that is a class, not a module."""
    if namespace is None:
        return ""
    module = getattr(namespace, "__module__", "")
    qualname = getattr(namespace, "__qualname__", "")
    return ".".join(part for part in (module, qualname) if part) or str(namespace)


class HookRecorder:
    """Builds a call tree from pluggy's before/after monitoring callbacks."""

    def __init__(self, pluginmanager: Any = None) -> None:
        self.pluginmanager = pluginmanager
        self.roots: list[CallNode] = []
        self.desyncs: list[str] = []
        self._stack: list[CallNode] = []
        self._seq = 0

    def before(self, hook_name: str, hook_impls: Any, kwargs: Any) -> None:
        self._seq += 1
        node = CallNode(
            name=hook_name,
            seq=self._seq,
            depth=len(self._stack),
            impls=[_impl_info(impl) for impl in hook_impls],
        )
        if self._stack:
            self._stack[-1].children.append(node)
        else:
            self.roots.append(node)
        self._stack.append(node)

    def after(self, outcome: Any, hook_name: str, hook_impls: Any, kwargs: Any) -> None:
        if not self._stack:
            self.desyncs.append(f"after({hook_name}) with empty stack")
            return
        node = self._stack.pop()
        if node.name != hook_name:
            self.desyncs.append(f"expected after({node.name}), got after({hook_name})")
        if _raised(outcome):
            node.raised = True

    def total_calls(self) -> int:
        return self._seq

    @property
    def application(self) -> str:
        """The name pluggy knows this manager by - ``pytest``, ``tox``, ``devpiclient``."""
        return getattr(self.pluginmanager, "project_name", "") or "unknown"

    @property
    def application_version(self) -> str:
        """Version of whatever is being traced, by the same route as hookspec
        sources: ``__version__`` if it exposes one, stdlib metadata otherwise."""
        module = sys.modules.get(self.application)
        version = getattr(module, "__version__", None) if module else None
        return str(version or _distribution_version(self.application) or "")

    def to_dict(self) -> dict[str, Any]:
        hookspecs = hookspec_metadata(self.pluginmanager)
        return {
            "schema_version": SCHEMA_VERSION,
            "environment": {
                "application": self.application,
                "version": self.application_version,
                "pluggy": pluggy.__version__,
                "python": platform.python_version(),
                "platform": sys.platform,
                # which plugin contributed each set of hookspecs, and at what
                # version - otherwise a trace cannot say which xdist it used
                "hookspec_sources": hookspec_sources(hookspecs),
            },
            "scenario": {
                "id": os.environ.get(ENV_SCENARIO),
                "process": process_name() or "main",
                "argv": _portable_argv(),
            },
            "stats": {
                "total_calls": self._seq,
                "unique_hooks": len({n for n in _walk_names(self.roots)}),
            },
            "desyncs": self.desyncs,
            "hookspecs": hookspecs,
            "calls": [root.to_dict() for root in self.roots],
        }


def _walk_names(nodes: list[CallNode]):
    for node in nodes:
        yield node.name
        yield from _walk_names(node.children)


_recorder: HookRecorder | None = None


def process_name() -> str:
    """Which process this is, for scenarios that run more than one.

    Under xdist every worker writes its own trace, and so does the controller -
    they see genuinely different things, the controller never collecting or
    running a test at all. Empty for an ordinary single-process run, which
    keeps those traces named exactly as before.
    """
    worker = os.environ.get(ENV_XDIST_WORKER)
    if worker:
        return worker
    return os.environ.get(ENV_PROCESS, "")


def trace_path() -> Path:
    base = Path(os.environ.get(ENV_TRACE_PATH, DEFAULT_TRACE_PATH))
    name = process_name()
    return base.with_name(f"{base.stem}.{name}{base.suffix}") if name else base


def write_trace() -> Path | None:
    """Serialise the recorded tree. Returns the path written, if any."""
    if _recorder is None:
        return None
    destination = trace_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(_recorder.to_dict(), indent=2) + "\n")
    return destination


def attach(pluginmanager: Any) -> HookRecorder | None:
    """Record every hook call this manager makes from now on.

    Returns ``None`` if a manager is already being recorded. Tracing two at once
    would interleave their calls into one tree, and the applications that create
    several - devpi creates two - would come out as nonsense.
    """
    global _recorder
    if _recorder is not None:
        return None
    _recorder = HookRecorder(pluginmanager)
    pluginmanager.add_hookcall_monitoring(_recorder.before, _recorder.after)
    atexit.register(write_trace)
    return _recorder


def watch(select: Any = None) -> None:
    """Trace the next plugin manager the process creates.

    The only way to observe an application you are not modifying. pluggy
    supports the monitoring itself - what it has no API for is *reaching* a
    manager somebody else constructed, so the constructor is wrapped.

    Attaching here rather than at an application's own entry point is also
    strictly earlier: hooks a plugin-loaded tracer can never see, because they
    fire while plugins are still being loaded, are recorded from the first call.

    ``select`` is an optional predicate on the manager's project name, for a
    program that builds more than one.
    """
    original = pluggy.PluginManager.__init__

    def patched(self, project_name, *args, **kwargs):  # type: ignore[no-untyped-def]
        original(self, project_name, *args, **kwargs)
        if select is None or select(project_name):
            attach(self)

    patched.__wrapped__ = original  # type: ignore[attr-defined]
    pluggy.PluginManager.__init__ = patched  # type: ignore[method-assign]


def unwatch() -> None:
    """Undo :func:`watch`. Tests need the process back as they found it."""
    original = getattr(pluggy.PluginManager.__init__, "__wrapped__", None)
    if original is not None:
        pluggy.PluginManager.__init__ = original  # type: ignore[method-assign]
