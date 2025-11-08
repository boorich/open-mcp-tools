"""
Tabletop Player Role Cheatsheet Tool

Generates a player role or faction cheatsheet with abilities, reminders, and scoring conditions.
"""

from typing import List, Optional

from pydantic import Field

from ...core import Tool, ToolContext, register_tool
from ...core.pricing import PricingType, ToolPricing
from ...core.resources.registry import get_registry
from ...core.resources.base import ResourceCategory
from ...core.types.models import MCPModel


class TabletopPlayerRoleCheatsheetParams(MCPModel):
    """Parameters for generating a player role cheatsheet"""
    
    game_id: str = Field(description="Game identifier (resource name)")
    role: str = Field(description="Role or faction name")


class Ability(MCPModel):
    """A player ability or action"""
    
    name: str = Field(description="Ability name")
    description: str = Field(description="Ability description")
    cost: Optional[str] = Field(default=None, description="Cost or requirement")


class ScoringCondition(MCPModel):
    """A scoring condition"""
    
    condition: str = Field(description="Scoring condition description")
    points: Optional[int] = Field(default=None, description="Points awarded")


class PlayerRoleCheatsheet(MCPModel):
    """Player role cheatsheet content"""
    
    game_title: str = Field(description="Game title")
    role_name: str = Field(description="Role or faction name")
    description: Optional[str] = Field(default=None, description="Role description")
    abilities: List[Ability] = Field(default_factory=list, description="Role abilities")
    reminders: List[str] = Field(default_factory=list, description="Important reminders")
    scoring_conditions: List[ScoringCondition] = Field(
        default_factory=list,
        description="Key scoring conditions"
    )
    tips: List[str] = Field(default_factory=list, description="Strategy tips")


class TabletopPlayerRoleCheatsheetResult(MCPModel):
    """Result from generating player role cheatsheet"""
    
    cheatsheet: PlayerRoleCheatsheet = Field(description="Generated cheatsheet")
    game_found: bool = Field(description="Whether the game was found")
    role_found: bool = Field(description="Whether the role was found")


@register_tool
class TabletopPlayerRoleCheatsheetTool(Tool[TabletopPlayerRoleCheatsheetParams, TabletopPlayerRoleCheatsheetResult]):
    """Generate a player role or faction cheatsheet"""
    
    name = "tabletop_player_role_cheatsheet"
    description = "Generate a cheatsheet for a specific player role or faction including abilities, reminders, and scoring conditions."
    params_model = TabletopPlayerRoleCheatsheetParams
    result_model = TabletopPlayerRoleCheatsheetResult
    
    pricing = ToolPricing(type=PricingType.FREE)
    
    async def execute(
        self,
        ctx: ToolContext[TabletopPlayerRoleCheatsheetParams, TabletopPlayerRoleCheatsheetResult]
    ):
        """Execute the player role cheatsheet tool"""
        registry = get_registry()
        
        # Find the game resource
        resources = registry.list_resources(category=ResourceCategory.RULEBOOK)
        game_resource = None
        
        for resource in resources:
            if resource.name == ctx.params.game_id:
                game_resource = resource
                break
        
        if not game_resource:
            result = TabletopPlayerRoleCheatsheetResult(
                cheatsheet=PlayerRoleCheatsheet(
                    game_title="",
                    role_name=ctx.params.role
                ),
                game_found=False,
                role_found=False
            )
            yield ctx.structured(result)
            return
        
        content = game_resource.get_content()
        role_lower = ctx.params.role.lower()
        
        # Search for role information in content
        # This is a simplified implementation - in practice, you'd have structured role data
        role_found = False
        abilities = []
        reminders = []
        scoring_conditions = []
        tips = []
        
        # Check chapters for role-specific content
        chapters = content.get("chapters", [])
        for chapter in chapters:
            chapter_content = chapter.get("content", "")
            if role_lower in chapter_content.lower():
                role_found = True
                # Extract basic reminders from content
                reminders.append(f"Check {chapter.get('title', 'rules')} section for {ctx.params.role} details")
        
        # If no specific role data found, provide generic structure
        if not role_found:
            reminders.append(f"Refer to the rulebook for {ctx.params.role} specific rules")
            reminders.append("Check your faction/role card for unique abilities")
        
        cheatsheet = PlayerRoleCheatsheet(
            game_title=content.get("title", game_resource.name),
            role_name=ctx.params.role,
            description=None,
            abilities=abilities,
            reminders=reminders,
            scoring_conditions=scoring_conditions,
            tips=tips
        )
        
        result = TabletopPlayerRoleCheatsheetResult(
            cheatsheet=cheatsheet,
            game_found=True,
            role_found=role_found
        )
        
        yield ctx.structured(result)

