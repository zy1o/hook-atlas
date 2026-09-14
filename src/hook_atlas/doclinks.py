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
    """

    base_url: str = ""
    anchor_prefix: str = ""
    namespaces: frozenset[str] = field(default_factory=frozenset)

    def url_for(self, hook_name: str, declared_in: str | None = None) -> str | None:
        if not self.base_url:
            return None
        if declared_in is not None and declared_in not in self.namespaces:
            return None
        anchor = f"{self.anchor_prefix}.{hook_name}" if self.anchor_prefix else hook_name
        return f"{self.base_url}#{anchor}"


#: The default: every hook renders unlinked. What an application nobody has
#: described gets, and it is a correct answer rather than a degraded one.
NO_LINKS = DocLinks()
