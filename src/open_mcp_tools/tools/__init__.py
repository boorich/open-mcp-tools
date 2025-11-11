"""Open MCP Tools - Auto-discovery for tool registration"""

# Import tabletop tools to trigger registration
from . import tabletop  # noqa: F401

# Import RAG pipeline tools to trigger registration
from . import rag  # noqa: F401

# Import business coaching tools to trigger registration
from . import business  # noqa: F401

__all__ = []
