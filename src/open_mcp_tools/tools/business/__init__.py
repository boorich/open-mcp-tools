"""Business Coaching Tools Module

Auto-discovery for business book tools.
"""

# Import tools to trigger registration
from .list_books import BusinessListBooksTool  # noqa: F401
from .lookup_framework import BusinessLookupFrameworkTool  # noqa: F401
from .lookup_chapter import BusinessLookupChapterTool  # noqa: F401
from .get_action_items import BusinessGetActionItemsTool  # noqa: F401
from .decide_task import BusinessDecideTaskTool  # noqa: F401
from .score_goal import BusinessScoreGoalTool  # noqa: F401

__all__ = [
    "BusinessListBooksTool",
    "BusinessLookupFrameworkTool",
    "BusinessLookupChapterTool",
    "BusinessGetActionItemsTool",
    "BusinessDecideTaskTool",
    "BusinessScoreGoalTool",
]

