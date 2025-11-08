"""
Tabletop Generate Quickstart Tool

Generates a quick-start guide for a specific game with setup instructions and first round walkthrough.
"""

from typing import List, Optional

from pydantic import Field

from ...core import Tool, ToolContext, register_tool
from ...core.pricing import PricingType, ToolPricing
from ...core.resources.registry import get_registry
from ...core.resources.base import ResourceCategory
from ...core.types.models import MCPModel


class TabletopGenerateQuickstartParams(MCPModel):
    """Parameters for generating a quickstart guide"""
    
    game_id: str = Field(description="Game identifier (resource name)")
    player_count: Optional[int] = Field(
        default=None,
        description="Number of players (for player-specific setup)",
        ge=1
    )
    experience_level: Optional[str] = Field(
        default="beginner",
        description="Experience level: 'beginner', 'intermediate', 'advanced'",
        pattern="^(beginner|intermediate|advanced)$"
    )


class SetupStep(MCPModel):
    """A single setup step"""
    
    step_number: int = Field(description="Step number")
    instruction: str = Field(description="Setup instruction")
    components: Optional[List[str]] = Field(
        default=None,
        description="Components needed for this step"
    )


class QuickstartGuide(MCPModel):
    """Quickstart guide content"""
    
    game_title: str = Field(description="Game title")
    game_id: str = Field(description="Game identifier")
    player_count: Optional[int] = Field(default=None, description="Recommended player count")
    components_checklist: List[str] = Field(description="List of components needed")
    setup_steps: List[SetupStep] = Field(description="Setup instructions")
    first_round_script: str = Field(description="First round walkthrough")
    tips: List[str] = Field(default_factory=list, description="Helpful tips")


class TabletopGenerateQuickstartResult(MCPModel):
    """Result from generating quickstart guide"""
    
    guide: QuickstartGuide = Field(description="Generated quickstart guide")
    game_found: bool = Field(description="Whether the game was found")


@register_tool
class TabletopGenerateQuickstartTool(Tool[TabletopGenerateQuickstartParams, TabletopGenerateQuickstartResult]):
    """Generate a quick-start guide for a tabletop game"""
    
    name = "tabletop_generate_quickstart"
    description = "Generate a quick-start guide for a tabletop game including components checklist, setup steps, and first round walkthrough."
    params_model = TabletopGenerateQuickstartParams
    result_model = TabletopGenerateQuickstartResult
    
    pricing = ToolPricing(type=PricingType.FREE)
    
    async def execute(
        self,
        ctx: ToolContext[TabletopGenerateQuickstartParams, TabletopGenerateQuickstartResult]
    ):
        """Execute the generate quickstart tool"""
        registry = get_registry()
        
        # Find the game resource
        resources = registry.list_resources(category=ResourceCategory.RULEBOOK)
        game_resource = None
        
        for resource in resources:
            if resource.name == ctx.params.game_id:
                game_resource = resource
                break
        
        if not game_resource:
            result = TabletopGenerateQuickstartResult(
                guide=QuickstartGuide(
                    game_title="",
                    game_id=ctx.params.game_id,
                    components_checklist=[],
                    setup_steps=[],
                    first_round_script=""
                ),
                game_found=False
            )
            yield ctx.structured(result)
            return
        
        content = game_resource.get_content()
        
        # Extract components
        components = content.get("components", [])
        
        # Extract setup steps
        setup_steps_raw = content.get("setup_steps", [])
        setup_steps = []
        for idx, step_text in enumerate(setup_steps_raw, 1):
            setup_steps.append(SetupStep(
                step_number=idx,
                instruction=step_text,
                components=None
            ))
        
        # Generate first round script
        phases = content.get("phases", [])
        first_round_script_parts = []
        
        if phases:
            first_round_script_parts.append("First Round Walkthrough:\n")
            for phase in sorted(phases, key=lambda p: p.get("order", 0)):
                phase_name = phase.get("name", "Unknown Phase")
                phase_desc = phase.get("description", "")
                first_round_script_parts.append(f"\n{phase_name}:")
                if phase_desc:
                    first_round_script_parts.append(f"  {phase_desc}")
        else:
            first_round_script_parts.append("Refer to the rulebook for first round instructions.")
        
        first_round_script = "\n".join(first_round_script_parts)
        
        # Generate tips based on experience level
        tips = []
        if ctx.params.experience_level == "beginner":
            tips.append("Take your time and don't worry about making mistakes.")
            tips.append("Focus on understanding the core mechanics first.")
        elif ctx.params.experience_level == "intermediate":
            tips.append("Try to optimize your strategy while learning.")
        else:
            tips.append("Explore advanced strategies and combinations.")
        
        guide = QuickstartGuide(
            game_title=content.get("title", game_resource.name),
            game_id=game_resource.name,
            player_count=ctx.params.player_count,
            components_checklist=components,
            setup_steps=setup_steps,
            first_round_script=first_round_script,
            tips=tips
        )
        
        result = TabletopGenerateQuickstartResult(
            guide=guide,
            game_found=True
        )
        
        yield ctx.structured(result)

