"""
Delete Pricelist Tool

Delete a specific price list import from the database.
"""

import logging

from pydantic import Field

from ...core import Tool, ToolContext, register_tool
from ...core.pricing import PricingType, ToolPricing
from ...core.types.models import MCPModel
from .database import get_db_connection, init_database

logger = logging.getLogger(__name__)


class RagDeletePricelistParams(MCPModel):
    """Parameters for delete pricelist tool."""
    
    pricelist_id: int = Field(..., description="ID of the pricelist to delete")


class RagDeletePricelistResult(MCPModel):
    """Result of pricelist deletion."""
    
    success: bool
    pricelist_id: int
    deleted_prices: int
    message: str


@register_tool
class RagDeletePricelistTool(Tool[RagDeletePricelistParams, RagDeletePricelistResult]):
    """Tool to delete a price list."""
    
    name = "rag_delete_pricelist"
    description = "Delete a specific price list import. This removes all prices associated with that import but keeps the products."
    params_model = RagDeletePricelistParams
    result_model = RagDeletePricelistResult
    pricing = ToolPricing(type=PricingType.FREE)
    
    async def execute(
        self,
        ctx: ToolContext[RagDeletePricelistParams, RagDeletePricelistResult]
    ):
        """Execute pricelist deletion."""
        init_database()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Check if pricelist exists
            cursor.execute("""
                SELECT pl.id, s.name as supplier_name, pl.imported_at
                FROM pricelists pl
                JOIN suppliers s ON pl.supplier_id = s.id
                WHERE pl.id = ?
            """, (ctx.params.pricelist_id,))
            pricelist = cursor.fetchone()
            
            if not pricelist:
                yield ctx.structured(RagDeletePricelistResult(
                    success=False,
                    pricelist_id=ctx.params.pricelist_id,
                    deleted_prices=0,
                    message=f"Pricelist with ID {ctx.params.pricelist_id} not found"
                ))
                return
            
            # Count prices to be deleted
            cursor.execute("SELECT COUNT(*) as count FROM prices WHERE pricelist_id = ?", (ctx.params.pricelist_id,))
            price_count = cursor.fetchone()["count"]
            
            # Delete prices associated with this pricelist
            cursor.execute("DELETE FROM prices WHERE pricelist_id = ?", (ctx.params.pricelist_id,))
            
            # Delete the pricelist itself
            cursor.execute("DELETE FROM pricelists WHERE id = ?", (ctx.params.pricelist_id,))
            
            conn.commit()
            
            message = f"Deleted pricelist {ctx.params.pricelist_id} ({pricelist['supplier_name']}, imported {pricelist['imported_at']}) with {price_count} prices"
            logger.info(message)
            
            yield ctx.structured(RagDeletePricelistResult(
                success=True,
                pricelist_id=ctx.params.pricelist_id,
                deleted_prices=price_count,
                message=message
            ))
            
        except Exception as e:
            conn.rollback()
            error_msg = f"Failed to delete pricelist: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            yield ctx.structured(RagDeletePricelistResult(
                success=False,
                pricelist_id=ctx.params.pricelist_id,
                deleted_prices=0,
                message=error_msg
            ))
        
        finally:
            conn.close()

