"""Tabletop Tools Module

Auto-discovery for tabletop rulebook tools.
"""

# Import tools to trigger registration
from .generate_quickstart import TabletopGenerateQuickstartTool  # noqa: F401
from .list_resources import TabletopListResourcesTool  # noqa: F401
from .lookup_rule import TabletopLookupRuleTool  # noqa: F401
from .player_role_cheatsheet import TabletopPlayerRoleCheatsheetTool  # noqa: F401

__all__ = [
    "TabletopListResourcesTool",
    "TabletopGenerateQuickstartTool",
    "TabletopLookupRuleTool",
    "TabletopPlayerRoleCheatsheetTool",
]

