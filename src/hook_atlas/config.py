"""Describing an application: its phases, its documentation, its own modules.

Everything here is optional. Without a config the whole run is drawn as one
flow, hooks render unlinked, and nothing is called internal - which is the
correct output for an application nobody has described, not a degraded one.

A config is what turns that into something shaped like the application. It is
TOML because it is data, and because someone describing a project they did not
write should not have to write Python to do it.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .analysis import Phase
from .doclinks import NO_LINKS, DocLinks
from .implementers import internal_prefixes


class ConfigError(ValueError):
    """A config that cannot be used, with a reason a human can act on."""


@dataclass(frozen=True)
class AtlasConfig:
    """Everything an application can tell this tool about itself."""

    #: What pluggy calls the manager. Used for labels, and to guess which
    #: modules are the application's own.
    application: str = ""
    phases: tuple[Phase, ...] = ()
    links: DocLinks = NO_LINKS
    #: Module prefixes counting as the application implementing a hook itself.
    #: Derived from the application name when not given.
    internal: tuple[str, ...] = ()
    #: Hooks kept out of the fingerprint that decides whether two releases
    #: produced the same flow. See `bookkeeping` in the TOML.
    bookkeeping: frozenset[str] = field(default_factory=frozenset)


def load(path: str | Path) -> AtlasConfig:
    """Read a config file. Raises :class:`ConfigError` with a usable message."""
    text = Path(path).read_text()
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path} is not valid TOML: {error}") from error
    return parse(raw, source=str(path))


def parse(raw: dict[str, Any], source: str = "<config>") -> AtlasConfig:
    """Turn parsed TOML into a config, complaining about anything unusable."""
    application = str(raw.get("application", "") or "")

    phases = tuple(_phase(entry, source, index) for index, entry in enumerate(raw.get("phase", [])))
    keys = [phase.key for phase in phases]
    duplicated = {key for key in keys if keys.count(key) > 1}
    if duplicated:
        # keys become CSS classes and heading anchors; duplicates would collide
        # silently and colour two different phases the same
        raise ConfigError(f"{source}: duplicate phase keys {sorted(duplicated)}")

    documentation = raw.get("docs", {})
    links = (
        DocLinks(
            base_url=str(documentation.get("base_url", "")),
            anchor_prefix=str(documentation.get("anchor_prefix", "")),
            namespaces=frozenset(documentation.get("namespaces", ())),
        )
        if documentation
        else NO_LINKS
    )

    internal = tuple(raw.get("internal", ())) or internal_prefixes(application)

    return AtlasConfig(
        application=application,
        phases=phases,
        links=links,
        internal=internal,
        bookkeeping=frozenset(raw.get("bookkeeping", ())),
    )


def _phase(entry: dict[str, Any], source: str, index: int) -> Phase:
    where = f"{source}: phase {index + 1}"
    for required in ("key", "title"):
        if not entry.get(required):
            raise ConfigError(f"{where} has no {required}")
    return Phase(
        key=str(entry["key"]),
        title=str(entry["title"]),
        anchors=tuple(entry.get("anchors", ())),
        description=str(entry.get("description", "")),
        fallback_anchors=tuple(entry.get("fallback_anchors", ())),
    )


def example(name: str = "pytest") -> Path:
    """Path to a config shipped with this package, for copying or testing."""
    path = Path(__file__).parent / "examples" / f"{name}.toml"
    if not path.exists():
        raise ConfigError(f"no example config called {name!r}")
    return path
