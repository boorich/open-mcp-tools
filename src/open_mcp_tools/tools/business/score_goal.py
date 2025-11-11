"""
Business Goal Scoring Tool

Strategic decision system using ICE methodology (Impact, Confidence, Ease).
Determines which goals/initiatives are worth pursuing.
"""

import logging
from typing import Optional

from pydantic import Field

from ...core import Tool, ToolContext, register_tool
from ...core.pricing import PricingType, ToolPricing
from ...core.types.models import MCPModel

logger = logging.getLogger(__name__)


class BusinessScoreGoalParams(MCPModel):
    """Parameters for goal scoring"""
    
    goal_name: str = Field(description="Name of the goal/initiative")
    impact: int = Field(
        description="Impact score (1-10): How much value does this create? Revenue, growth, strategic importance",
        ge=1,
        le=10
    )
    confidence: int = Field(
        description="Confidence score (1-10): How confident are you this will succeed? Do you have proven process?",
        ge=1,
        le=10
    )
    ease: int = Field(
        description="Ease score (1-10): How easy is this to execute? Time, resources, complexity",
        ge=1,
        le=10
    )
    threshold: float = Field(
        default=7.0,
        description="ICE threshold for pursuing (default: 7.0)",
        ge=1.0,
        le=10.0
    )


class GoalScore(MCPModel):
    """Goal scoring result"""
    
    goal_name: str = Field(description="Goal name")
    ice_score: float = Field(description="ICE score (average of Impact, Confidence, Ease)")
    decision: str = Field(description="PURSUE | DEFER | DELETE")
    reasoning: str = Field(description="Why this decision was made")
    bottleneck: Optional[str] = Field(
        default=None,
        description="The lowest-scoring dimension (what's holding you back)"
    )
    improvement_suggestion: Optional[str] = Field(
        default=None,
        description="How to improve the score"
    )
    breakdown: dict = Field(description="Score breakdown by dimension")


class BusinessScoreGoalResult(MCPModel):
    """Result of goal scoring"""
    
    score: GoalScore = Field(description="The goal score and decision")
    next_action: str = Field(description="Immediate next step")


@register_tool
class BusinessScoreGoalTool(Tool[BusinessScoreGoalParams, BusinessScoreGoalResult]):
    """Strategic goal scoring using ICE methodology"""
    
    name = "business_score_goal"
    description = (
        "Score goals/initiatives using ICE methodology (Impact, Confidence, Ease). "
        "Returns binary decision: PURSUE (score >= 7.0), DEFER (5.0-7.0), or DELETE (< 5.0). "
        "Use this for strategic decisions (what to work on), not tactical (who does the work)."
    )
    params_model = BusinessScoreGoalParams
    result_model = BusinessScoreGoalResult
    
    pricing = ToolPricing(type=PricingType.FREE)
    
    def _calculate_ice_score(
        self,
        impact: int,
        confidence: int,
        ease: int
    ) -> float:
        """Pure function: Calculate ICE score (average)"""
        return (impact + confidence + ease) / 3.0
    
    def _identify_bottleneck(
        self,
        impact: int,
        confidence: int,
        ease: int
    ) -> str:
        """Pure function: Find the lowest-scoring dimension"""
        scores = {
            "Impact": impact,
            "Confidence": confidence,
            "Ease": ease
        }
        bottleneck = min(scores, key=scores.get)
        return bottleneck
    
    def _decide(
        self,
        ice_score: float,
        threshold: float
    ) -> tuple[str, str]:
        """
        Pure decision function
        
        Returns: (DECISION, REASONING)
        """
        if ice_score >= threshold:
            return ("PURSUE", f"ICE score {ice_score:.1f} >= {threshold:.1f} - strong strategic fit")
        elif ice_score >= 5.0:
            return ("DEFER", f"ICE score {ice_score:.1f} below threshold - improve before pursuing")
        else:
            return ("DELETE", f"ICE score {ice_score:.1f} too low - not worth pursuing")
    
    def _suggest_improvement(
        self,
        bottleneck: str,
        impact: int,
        confidence: int,
        ease: int
    ) -> str:
        """Generate improvement suggestion based on bottleneck"""
        
        suggestions = {
            "Impact": (
                f"Impact is only {impact}/10. Ask: Does this directly drive revenue/growth? "
                "Consider focusing on higher-impact goals first."
            ),
            "Confidence": (
                f"Confidence is only {confidence}/10. You lack proven process. "
                "Run a small test first (30 days) to validate the approach before full commitment."
            ),
            "Ease": (
                f"Ease is only {ease}/10. This is too complex/time-consuming. "
                "Break it down into smaller phases or delegate more aggressively."
            )
        }
        
        return suggestions.get(bottleneck, "")
    
    async def execute(
        self,
        ctx: ToolContext[BusinessScoreGoalParams, BusinessScoreGoalResult]
    ):
        # Calculate ICE score
        ice_score = self._calculate_ice_score(
            ctx.params.impact,
            ctx.params.confidence,
            ctx.params.ease
        )
        
        # Identify bottleneck
        bottleneck = self._identify_bottleneck(
            ctx.params.impact,
            ctx.params.confidence,
            ctx.params.ease
        )
        
        # Make decision
        decision, reasoning = self._decide(ice_score, ctx.params.threshold)
        
        # Generate improvement suggestion
        improvement = None
        if decision != "PURSUE":
            improvement = self._suggest_improvement(
                bottleneck,
                ctx.params.impact,
                ctx.params.confidence,
                ctx.params.ease
            )
        
        # Build score result
        score = GoalScore(
            goal_name=ctx.params.goal_name,
            ice_score=round(ice_score, 2),
            decision=decision,
            reasoning=reasoning,
            bottleneck=bottleneck if decision != "PURSUE" else None,
            improvement_suggestion=improvement,
            breakdown={
                "impact": ctx.params.impact,
                "confidence": ctx.params.confidence,
                "ease": ctx.params.ease
            }
        )
        
        # Next action guidance
        if decision == "PURSUE":
            next_action = (
                f"✅ PURSUE '{ctx.params.goal_name}'. "
                f"Break it into tasks and use business_decide_task for each."
            )
        elif decision == "DEFER":
            next_action = (
                f"⏸️ DEFER '{ctx.params.goal_name}'. "
                f"Focus on improving {bottleneck} first. {improvement}"
            )
        else:  # DELETE
            next_action = (
                f"❌ DELETE '{ctx.params.goal_name}'. "
                f"Score too low - invest time in higher-ICE goals instead."
            )
        
        result = BusinessScoreGoalResult(
            score=score,
            next_action=next_action
        )
        
        yield ctx.structured(result)

