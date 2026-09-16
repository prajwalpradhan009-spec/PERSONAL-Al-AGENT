"""
AI Agent Integration Layer
Dedicated tool/integration modules for external applications and services
(Spotify, Browser, File System, Windows Control, YouTube, GitHub, Google, Discord).

Design principle: every application exposes a granular capability API instead
of a single "openApplication" hammer. The capability registry in
`app.integrations.registry` maps (application, capability) -> tool function.
"""

from app.integrations.registry import (  # noqa: F401
    APPLICATIONS,
    list_applications,
    get_application,
    get_capabilities,
    has_capability,
    capability_summary_text,
)

__all__ = [
    "APPLICATIONS",
    "list_applications",
    "get_application",
    "get_capabilities",
    "has_capability",
    "capability_summary_text",
]