"""Turn a hook name into a link to its documentation, when there is one.

Deliberately conservative. An application whose documentation we know nothing
about renders its hooks as plain boxes, because the alternative - guessing a URL
- produces dead anchors, and dead anchors are what this project shipped for
years before anyone noticed.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DocLinks:
    """Where an application's hook documentation lives.

    ``namespaces`` lists the hookspec modules this documentation actually
    covers. A hook declared anywhere else - a plugin's own hooks, a project's
    own - renders unlinked rather than pointing at a page where its anchor does
    not exist.

    ``documented`` narrows that further, to the hooks a *particular* page turns
    out to contain. Namespaces are a statement of intent; this is a fact about
    the page, and the two differ whenever a version's own documentation is
    unavailable and something more general is used instead. A hook removed
    between that version and this one is then in the right namespace and absent
    from the page, and linking it produces the dead anchor this module exists to
    prevent. Leave it ``None`` to link anything the namespaces allow.
    """

    base_url: str = ""
    anchor_prefix: str = ""
    namespaces: frozenset[str] = field(default_factory=frozenset)
    documented: frozenset[str] | None = None

    def url_for(self, hook_name: str, declared_in: str | None = None) -> str | None:
        if not self.base_url:
            return None
        if declared_in is not None and declared_in not in self.namespaces:
            return None
        if self.documented is not None and hook_name not in self.documented:
            return None
        anchor = f"{self.anchor_prefix}.{hook_name}" if self.anchor_prefix else hook_name
        return f"{self.base_url}#{anchor}"


#: The default: every hook renders unlinked. What an application nobody has
#: described gets, and it is a correct answer rather than a degraded one.
NO_LINKS = DocLinks()
