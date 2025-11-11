"""
Business Task Decision Tool

Binary decision system for task delegation based on functional rules.
NO planning, NO reflection, PURE execution.
"""

import logging
from typing import List, Optional

from pydantic import Field

from ...core import Tool, ToolContext, register_tool
from ...core.pricing import PricingType, ToolPricing
from ...core.types.models import MCPModel

logger = logging.getLogger(__name__)


class BusinessDecideTaskParams(MCPModel):
    """Parameters for task decision"""
    
    task_name: str = Field(description="Name of the task")
    hourly_value: float = Field(
        description="Estimated value per hour this task generates (in your currency)"
    )
    hours_per_week: float = Field(
        description="How many hours per week this task takes"
    )
    energizes: bool = Field(
        default=False,
        description="Does this task energize you? (True/False)"
    )
    must_be_me: bool = Field(
        default=False,
        description="Can ONLY you do this? (True/False - be honest)"
    )
    buyback_rate: float = Field(
        default=50.0,
        description="Your buyback rate (yearly income / 2000). Default: 50"
    )


class TaskDecision(MCPModel):
    """Binary decision result"""
    
    task_name: str = Field(description="Task name")
    action: str = Field(description="DO | DELEGATE | DELETE")
    reasoning: str = Field(description="One sentence why")
    value_per_hour: float = Field(description="Calculated value per hour")
    weekly_cost: Optional[float] = Field(
        default=None,
        description="Cost to delegate per week (if applicable)"
    )
    roi: Optional[float] = Field(
        default=None,
        description="Return on investment for delegation (if applicable)"
    )
    time_saved_per_week: Optional[float] = Field(
        default=None,
        description="Hours saved per week (if delegated)"
    )


class BusinessDecideTaskResult(MCPModel):
    """Result of task decision"""
    
    decision: TaskDecision = Field(description="The binary decision")
    next_action: str = Field(description="Immediate next step")


@register_tool
class BusinessDecideTaskTool(Tool[BusinessDecideTaskParams, BusinessDecideTaskResult]):
    """Binary task decision tool based on functional rules"""
    
    name = "business_decide_task"
    description = (
        "Binary decision system for tasks. Input task details, get immediate action: "
        "DO (keep doing it yourself), DELEGATE (hire someone), or DELETE (eliminate). "
        "Based on functional programming principles - pure, composable, deterministic."
    )
    params_model = BusinessDecideTaskParams
    result_model = BusinessDecideTaskResult
    
    pricing = ToolPricing(type=PricingType.FREE)
    
    def _calculate_value_per_hour(self, params: BusinessDecideTaskParams) -> float:
        """Pure function: Calculate value per hour"""
        return params.hourly_value
    
    def _is_high_value(self, value_per_hour: float, buyback_rate: float) -> bool:
        """Pure function: Is this worth your time?"""
        return value_per_hour >= buyback_rate
    
    def _has_positive_roi(
        self,
        value_per_hour: float,
        buyback_rate: float,
        energizes: bool
    ) -> bool:
        """
        Pure function: Energy multiplier logic
        
        Energizing tasks: 50% discount OK (25€ threshold if rate is 50€)
        Draining tasks: 150% premium required (75€ threshold if rate is 50€)
        """
        threshold = buyback_rate * 0.5 if energizes else buyback_rate * 1.5
        return value_per_hour >= threshold
    
    def _calculate_delegation_cost(
        self,
        hours_per_week: float,
        market_rate: float = 25.0
    ) -> float:
        """Pure function: What it costs to delegate (assuming 25€/h VA rate)"""
        return hours_per_week * market_rate
    
    def _calculate_roi(
        self,
        hours_saved: float,
        your_rate: float,
        delegation_cost: float
    ) -> float:
        """Pure function: ROI of delegation"""
        value_reclaimed = hours_saved * your_rate
        return value_reclaimed / delegation_cost if delegation_cost > 0 else 0
    
    def _decide(self, params: BusinessDecideTaskParams) -> tuple[str, str]:
        """
        Pure decision function (functional composition)
        
        Returns: (ACTION, REASONING)
        """
        value_per_hour = self._calculate_value_per_hour(params)
        
        # RULE 1: Must be you? → DO IT
        if params.must_be_me:
            return ("DO", "Only you can do this (unique expertise required)")
        
        # RULE 2: Low value? → DELETE or DELEGATE
        if not self._is_high_value(value_per_hour, params.buyback_rate):
            delegation_cost = self._calculate_delegation_cost(params.hours_per_week)
            if delegation_cost < params.hours_per_week * params.buyback_rate * 0.5:
                return ("DELEGATE", f"Value ${value_per_hour:.0f}/h < your rate ${params.buyback_rate:.0f}/h")
            else:
                return ("DELETE", "Too low value to even delegate - eliminate entirely")
        
        # RULE 3: High value but check energy ROI
        if self._has_positive_roi(value_per_hour, params.buyback_rate, params.energizes):
            if params.energizes:
                return ("DO", f"High value ${value_per_hour:.0f}/h + energizes you = keep doing")
            else:
                # High value but draining - can we afford to delegate?
                delegation_cost = self._calculate_delegation_cost(params.hours_per_week)
                roi = self._calculate_roi(
                    params.hours_per_week,
                    params.buyback_rate,
                    delegation_cost
                )
                
                if roi >= 1.5:  # 150% ROI threshold
                    return ("DELEGATE", f"High value but drains energy - ROI {roi:.1f}x justifies delegation")
                else:
                    return ("DO", f"High value ${value_per_hour:.0f}/h - must do it yourself (low delegation ROI)")
        
        # RULE 4: Doesn't meet energy threshold
        return ("DELEGATE", f"Value ${value_per_hour:.0f}/h doesn't justify the energy drain")
    
    async def execute(
        self,
        ctx: ToolContext[BusinessDecideTaskParams, BusinessDecideTaskResult]
    ):
        # Apply decision function
        action, reasoning = self._decide(ctx.params)
        
        value_per_hour = self._calculate_value_per_hour(ctx.params)
        
        # Calculate delegation metrics if applicable
        weekly_cost = None
        roi = None
        time_saved = None
        
        if action == "DELEGATE":
            weekly_cost = self._calculate_delegation_cost(ctx.params.hours_per_week)
            time_saved = ctx.params.hours_per_week
            roi = self._calculate_roi(
                ctx.params.hours_per_week,
                ctx.params.buyback_rate,
                weekly_cost
            )
        
        # Build decision
        decision = TaskDecision(
            task_name=ctx.params.task_name,
            action=action,
            reasoning=reasoning,
            value_per_hour=value_per_hour,
            weekly_cost=weekly_cost,
            roi=roi,
            time_saved_per_week=time_saved
        )
        
        # Next action guidance
        if action == "DO":
            next_action = f"Keep doing '{ctx.params.task_name}' yourself. Block time for it."
        elif action == "DELEGATE" and weekly_cost is not None and roi is not None:
            next_action = f"Find VA/hire for '{ctx.params.task_name}'. Budget: ${weekly_cost:.0f}/week. ROI: {roi:.1f}x"
        elif action == "DELEGATE":
            next_action = f"Delegate '{ctx.params.task_name}' to VA/assistant. Saves {time_saved:.1f}h/week."
        else:  # DELETE
            next_action = f"Eliminate '{ctx.params.task_name}' entirely. Stop doing it now."
        
        result = BusinessDecideTaskResult(
            decision=decision,
            next_action=next_action
        )
        
        yield ctx.structured(result)

