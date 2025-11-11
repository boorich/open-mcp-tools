"""List Business Books Tool"""

import logging
from typing import List, Optional

from pydantic import Field

from ...core import Tool, ToolContext, register_tool
from ...core.pricing import PricingType, ToolPricing
from ...core.resources.registry import get_registry
from ...core.resources.base import ResourceCategory, BusinessBookResource
from ...core.types.models import MCPModel

logger = logging.getLogger(__name__)


class BusinessListBooksParams(MCPModel):
    """Parameters for listing business books"""
    
    category: Optional[str] = Field(
        default=None,
        description="Filter by category (e.g., 'entrepreneurship', 'leadership', 'productivity')"
    )
    tag: Optional[str] = Field(
        default=None,
        description="Filter by tag"
    )
    author: Optional[str] = Field(
        default=None,
        description="Filter by author name"
    )


class BookSummary(MCPModel):
    """Summary of a business book"""
    
    name: str
    title: str
    author: str
    category: str
    description: str
    tags: List[str]
    uri: str
    chapter_count: int
    framework_count: int
    action_item_count: int


class BusinessListBooksResult(MCPModel):
    """Result of listing business books"""
    
    books: List[BookSummary]
    total: int


@register_tool
class BusinessListBooksTool(Tool[BusinessListBooksParams, BusinessListBooksResult]):
    name = "business_list_books"
    description = (
        "List available business and self-help books with filtering options. "
        "Returns book summaries with metadata, framework counts, and action items."
    )
    params_model = BusinessListBooksParams
    result_model = BusinessListBooksResult
    pricing = ToolPricing(type=PricingType.FREE)
    
    async def execute(
        self,
        ctx: ToolContext[BusinessListBooksParams, BusinessListBooksResult]
    ):
        registry = get_registry()
        
        # Get all business book resources
        all_resources = registry.list_resources(category=ResourceCategory.BUSINESS_BOOK)
        
        # Filter resources
        filtered = []
        for resource in all_resources:
            if not isinstance(resource, BusinessBookResource):
                continue
            
            content = resource.get_content()
            
            # Apply filters
            if ctx.params.category:
                book_category = content.get('category', '').lower()
                if ctx.params.category.lower() not in book_category:
                    continue
            
            if ctx.params.tag:
                tags = [t.lower() for t in content.get('tags', [])]
                if ctx.params.tag.lower() not in tags:
                    continue
            
            if ctx.params.author:
                author = content.get('author', '').lower()
                if ctx.params.author.lower() not in author:
                    continue
            
            filtered.append(resource)
        
        # Build summaries
        books = []
        for resource in filtered:
            content = resource.get_content()
            
            summary = BookSummary(
                name=resource.name,
                title=content.get('title', resource.name),
                author=content.get('author', 'Unknown'),
                category=content.get('category', 'business'),
                description=content.get('description', 'No description available'),
                tags=content.get('tags', []),
                uri=resource.uri,
                chapter_count=len(content.get('chapters', [])),
                framework_count=len(content.get('frameworks', [])),
                action_item_count=len(content.get('action_items', []))
            )
            books.append(summary)
        
        result = BusinessListBooksResult(
            books=books,
            total=len(books)
        )
        
        yield ctx.structured(result)

