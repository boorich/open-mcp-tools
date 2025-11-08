"""
Tabletop List Resources Tool

Lists available tabletop rulebook resources with filtering options.
"""

from typing import List, Optional

from pydantic import Field

from ...core import Tool, ToolContext, register_tool
from ...core.pricing import PricingType, ToolPricing
from ...core.resources.registry import get_registry
from ...core.resources.base import ResourceCategory
from ...core.types.models import MCPModel


class TabletopListResourcesParams(MCPModel):
    """Parameters for listing tabletop resources"""
    
    play_style: Optional[str] = Field(
        default=None,
        description="Filter by play style (e.g., 'cooperative', 'competitive', 'solo')"
    )
    complexity: Optional[str] = Field(
        default=None,
        description="Filter by complexity level: 'light', 'medium', 'heavy', 'very-heavy'"
    )
    min_players: Optional[int] = Field(
        default=None,
        description="Minimum player count",
        ge=1
    )
    max_players: Optional[int] = Field(
        default=None,
        description="Maximum player count",
        ge=1
    )
    max_playtime: Optional[int] = Field(
        default=None,
        description="Maximum playtime in minutes",
        ge=1
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Filter by tags (any match)"
    )


class GameInfo(MCPModel):
    """Information about a tabletop game"""
    
    name: str = Field(description="Game name/identifier")
    title: str = Field(description="Display title")
    version: str = Field(description="Resource version")
    uri: str = Field(description="Resource URI")
    description: Optional[str] = Field(default=None, description="Game description")
    player_count: Optional[dict] = Field(
        default=None,
        description="Player count range with min/max"
    )
    playtime: Optional[dict] = Field(
        default=None,
        description="Playtime range in minutes with min/max"
    )
    complexity: Optional[str] = Field(
        default=None,
        description="Complexity level"
    )
    language: Optional[str] = Field(default=None, description="Language code")
    tags: List[str] = Field(default_factory=list, description="Game tags")


class TabletopListResourcesResult(MCPModel):
    """Result from listing tabletop resources"""
    
    games: List[GameInfo] = Field(description="List of matching games")
    total: int = Field(description="Total number of games found")
    filters_applied: dict = Field(description="Filters that were applied")


@register_tool
class TabletopListResourcesTool(Tool[TabletopListResourcesParams, TabletopListResourcesResult]):
    """List available tabletop rulebook resources with optional filtering"""
    
    name = "tabletop_list_resources"
    description = "List available tabletop rulebook resources. Filter by play style, complexity, player count, playtime, or tags."
    params_model = TabletopListResourcesParams
    result_model = TabletopListResourcesResult
    
    pricing = ToolPricing(type=PricingType.FREE)
    
    async def execute(
        self,
        ctx: ToolContext[TabletopListResourcesParams, TabletopListResourcesResult]
    ):
        """Execute the list resources tool"""
        registry = get_registry()
        
        # Get all rulebook resources
        all_resources = registry.list_resources(category=ResourceCategory.RULEBOOK)
        
        # Apply filters
        filtered_resources = []
        filters_applied = {}
        
        for resource in all_resources:
            content = resource.get_content()
            
            # Filter by complexity
            if ctx.params.complexity:
                game_complexity = content.get("complexity")
                if game_complexity != ctx.params.complexity:
                    continue
                filters_applied["complexity"] = ctx.params.complexity
            
            # Filter by player count
            player_count = content.get("player_count")
            if ctx.params.min_players or ctx.params.max_players:
                if not player_count:
                    continue
                min_players = player_count.get("min", 1)
                max_players = player_count.get("max", 999)
                
                if ctx.params.min_players and max_players < ctx.params.min_players:
                    continue
                if ctx.params.max_players and min_players > ctx.params.max_players:
                    continue
                
                if ctx.params.min_players:
                    filters_applied["min_players"] = ctx.params.min_players
                if ctx.params.max_players:
                    filters_applied["max_players"] = ctx.params.max_players
            
            # Filter by playtime
            playtime = content.get("playtime")
            if ctx.params.max_playtime:
                if not playtime:
                    continue
                min_playtime = playtime.get("min", 0)
                if min_playtime > ctx.params.max_playtime:
                    continue
                filters_applied["max_playtime"] = ctx.params.max_playtime
            
            # Filter by tags
            if ctx.params.tags:
                resource_tags = resource.metadata.tags
                if not any(tag.lower() in [t.lower() for t in resource_tags] for tag in ctx.params.tags):
                    continue
                filters_applied["tags"] = ctx.params.tags
            
            # Filter by play style (check tags)
            if ctx.params.play_style:
                resource_tags = [t.lower() for t in resource.metadata.tags]
                if ctx.params.play_style.lower() not in resource_tags:
                    continue
                filters_applied["play_style"] = ctx.params.play_style
            
            filtered_resources.append(resource)
        
        # Convert to GameInfo objects
        games = []
        for resource in filtered_resources:
            content = resource.get_content()
            
            game_info = GameInfo(
                name=resource.name,
                title=content.get("title", resource.name),
                version=resource.metadata.version,
                uri=resource.uri,
                description=resource.metadata.description,
                player_count=content.get("player_count"),
                playtime=content.get("playtime"),
                complexity=content.get("complexity"),
                language=content.get("language"),
                tags=resource.metadata.tags
            )
            games.append(game_info)
        
        result = TabletopListResourcesResult(
            games=games,
            total=len(games),
            filters_applied=filters_applied
        )
        
        yield ctx.structured(result)

