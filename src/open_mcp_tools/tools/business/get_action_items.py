"""
Business Get Action Items Tool

Retrieves actionable items and exercises from a business book.
"""

import logging
from typing import List, Optional

from pydantic import Field

from ...core import Tool, ToolContext, register_tool
from ...core.pricing import PricingType, ToolPricing
from ...core.resources.registry import get_registry
from ...core.resources.base import ResourceCategory, BusinessBookResource
from ...core.types.models import MCPModel

logger = logging.getLogger(__name__)


class BusinessGetActionItemsParams(MCPModel):
    """Parameters for getting action items"""
    
    book_id: str = Field(description="Book identifier (resource name)")
    difficulty: Optional[str] = Field(
        default=None,
        description="Filter by difficulty: 'easy', 'medium', 'hard'"
    )
    chapter: Optional[int] = Field(
        default=None,
        description="Optional chapter number to filter by"
    )


class ActionItemDetail(MCPModel):
    """Detailed action item information"""
    
    action: str = Field(description="Action to take")
    description: str = Field(description="Details about the action")
    chapter: Optional[int] = Field(default=None, description="Related chapter")
    difficulty: Optional[str] = Field(default=None, description="Implementation difficulty")


class BusinessGetActionItemsResult(MCPModel):
    """Result from getting action items"""
    
    action_items: List[ActionItemDetail] = Field(description="Action items")
    book_found: bool = Field(description="Whether the book was found")
    total: int = Field(description="Total number of action items returned")
    filtered_by: dict = Field(description="Applied filters")


@register_tool
class BusinessGetActionItemsTool(Tool[BusinessGetActionItemsParams, BusinessGetActionItemsResult]):
    """Get actionable items and exercises from a business book"""
    
    name = "business_get_action_items"
    description = "Retrieve actionable items, exercises, and implementation steps from a business book. Can filter by difficulty (easy/medium/hard) or chapter number."
    params_model = BusinessGetActionItemsParams
    result_model = BusinessGetActionItemsResult
    
    pricing = ToolPricing(type=PricingType.FREE)
    
    async def execute(
        self,
        ctx: ToolContext[BusinessGetActionItemsParams, BusinessGetActionItemsResult]
    ):
        registry = get_registry()
        
        # Find the book
        book_resource = None
        for resource in registry.list_resources(category=ResourceCategory.BUSINESS_BOOK):
            if isinstance(resource, BusinessBookResource) and resource.name == ctx.params.book_id:
                book_resource = resource
                break
        
        if not book_resource:
            yield ctx.structured(BusinessGetActionItemsResult(
                action_items=[],
                book_found=False,
                total=0,
                filtered_by={}
            ))
            return
        
        content = book_resource.get_content()
        all_action_items = content.get("action_items", [])
        
        # Apply filters
        filtered_items = []
        
        for item in all_action_items:
            action = item.get("action", "")
            description = item.get("description", "")
            chapter = item.get("chapter")
            difficulty = item.get("difficulty")
            
            # Filter by difficulty
            if ctx.params.difficulty:
                if not difficulty or difficulty.lower() != ctx.params.difficulty.lower():
                    continue
            
            # Filter by chapter
            if ctx.params.chapter is not None:
                if chapter != ctx.params.chapter:
                    continue
            
            filtered_items.append(ActionItemDetail(
                action=action,
                description=description,
                chapter=chapter,
                difficulty=difficulty
            ))
        
        # Build filter summary
        filters_applied = {}
        if ctx.params.difficulty:
            filters_applied["difficulty"] = ctx.params.difficulty
        if ctx.params.chapter is not None:
            filters_applied["chapter"] = ctx.params.chapter
        
        result = BusinessGetActionItemsResult(
            action_items=filtered_items,
            book_found=True,
            total=len(filtered_items),
            filtered_by=filters_applied
        )
        
        yield ctx.structured(result)

