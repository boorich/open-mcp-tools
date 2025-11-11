"""
Calculator Tool - Safe mathematical expression evaluation

Provides a secure Python calculator that evaluates mathematical expressions
without consuming LLM tokens for basic arithmetic.
"""

import math
from typing import Dict, Optional
from pydantic import Field

from ...core import Tool, ToolContext, register_tool
from ...core.types.models import MCPModel


class CalculatorParams(MCPModel):
    """Parameters for calculator tool"""
    
    expression: str = Field(
        description="Mathematical expression to evaluate (e.g., '100 * 1.4' or '(ek - ek * discount) * 1.4')"
    )
    variables: Optional[Dict[str, float]] = Field(
        default=None,
        description="Optional variables to use in the expression (e.g., {'ek': 100, 'discount': 0.3})"
    )


class CalculatorResult(MCPModel):
    """Result from calculator"""
    
    expression: str = Field(description="The expression that was evaluated")
    result: float = Field(description="The calculated result")
    variables_used: Optional[Dict[str, float]] = Field(
        default=None,
        description="Variables that were provided"
    )
    formatted_result: str = Field(
        description="Human-readable result with context"
    )


@register_tool
class CalculatorTool(Tool):
    """
    Safe mathematical calculator tool
    
    Evaluates mathematical expressions without consuming LLM tokens.
    Supports standard math operations and common functions (sin, cos, sqrt, etc.).
    """
    
    name = "calculator"
    description = (
        "Evaluate mathematical expressions safely. "
        "Supports: +, -, *, /, **, (), and math functions (sqrt, sin, cos, log, etc.). "
        "Can use variables: calculator('ek * 1.4', {'ek': 100})"
    )
    params_model = CalculatorParams
    result_model = CalculatorResult
    
    # Safe namespace for eval - only math functions and builtins
    SAFE_NAMESPACE = {
        # Math module functions
        'abs': abs,
        'round': round,
        'min': min,
        'max': max,
        'sum': sum,
        'pow': pow,
        'sqrt': math.sqrt,
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'asin': math.asin,
        'acos': math.acos,
        'atan': math.atan,
        'log': math.log,
        'log10': math.log10,
        'exp': math.exp,
        'ceil': math.ceil,
        'floor': math.floor,
        'pi': math.pi,
        'e': math.e,
        # Safe builtins
        '__builtins__': {},
    }
    
    async def execute(
        self,
        ctx: ToolContext[CalculatorParams, CalculatorResult]
    ):
        """Execute calculator"""
        
        try:
            # Prepare namespace
            namespace = self.SAFE_NAMESPACE.copy()
            
            # Add user variables if provided
            if ctx.params.variables:
                # Validate variables are numeric
                for key, value in ctx.params.variables.items():
                    if not isinstance(value, (int, float)):
                        result = CalculatorResult(
                            expression=ctx.params.expression,
                            result=0.0,
                            variables_used=ctx.params.variables,
                            formatted_result=f"Error: Variable '{key}' must be a number, got {type(value).__name__}"
                        )
                        yield ctx.structured(result)
                        return
                    namespace[key] = float(value)
            
            # Evaluate expression
            try:
                result_value = eval(ctx.params.expression, namespace)
                
                # Ensure result is numeric
                if not isinstance(result_value, (int, float)):
                    result = CalculatorResult(
                        expression=ctx.params.expression,
                        result=0.0,
                        variables_used=ctx.params.variables,
                        formatted_result=f"Error: Expression must evaluate to a number, got {type(result_value).__name__}"
                    )
                    yield ctx.structured(result)
                    return
                
                result_value = float(result_value)
                
            except ZeroDivisionError:
                result = CalculatorResult(
                    expression=ctx.params.expression,
                    result=0.0,
                    variables_used=ctx.params.variables,
                    formatted_result="Error: Division by zero"
                )
                yield ctx.structured(result)
                return
            except NameError as e:
                result = CalculatorResult(
                    expression=ctx.params.expression,
                    result=0.0,
                    variables_used=ctx.params.variables,
                    formatted_result=f"Error: Unknown variable or function: {str(e)}"
                )
                yield ctx.structured(result)
                return
            except SyntaxError:
                result = CalculatorResult(
                    expression=ctx.params.expression,
                    result=0.0,
                    variables_used=ctx.params.variables,
                    formatted_result=f"Error: Invalid expression syntax"
                )
                yield ctx.structured(result)
                return
            except Exception as e:
                result = CalculatorResult(
                    expression=ctx.params.expression,
                    result=0.0,
                    variables_used=ctx.params.variables,
                    formatted_result=f"Error: {str(e)}"
                )
                yield ctx.structured(result)
                return
            
            # Format result nicely
            if ctx.params.variables:
                var_str = ", ".join(f"{k}={v}" for k, v in ctx.params.variables.items())
                formatted = f"{ctx.params.expression} (with {var_str}) = {result_value:,.2f}"
            else:
                formatted = f"{ctx.params.expression} = {result_value:,.2f}"
            
            result = CalculatorResult(
                expression=ctx.params.expression,
                result=result_value,
                variables_used=ctx.params.variables,
                formatted_result=formatted
            )
            
            yield ctx.structured(result)
            
        except Exception as e:
            result = CalculatorResult(
                expression=ctx.params.expression,
                result=0.0,
                variables_used=ctx.params.variables,
                formatted_result=f"Unexpected error: {str(e)}"
            )
            yield ctx.structured(result)

