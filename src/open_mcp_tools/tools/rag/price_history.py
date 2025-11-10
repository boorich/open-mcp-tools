"""
Price History Tool

Show price development for a product over time across all imports.
"""

import logging
from typing import List

from pydantic import Field

from ...core import Tool, ToolContext, register_tool
from ...core.pricing import PricingType, ToolPricing
from ...core.types.models import MCPModel
from .database import get_db_connection, init_database

logger = logging.getLogger(__name__)


class RagPriceHistoryParams(MCPModel):
    """Parameters for price history tool."""
    
    ean: str = Field(..., description="EAN code to get price history for")
    supplier_filter: str | None = Field(
        default=None,
        description="Optional: Filter by specific supplier name"
    )


class PriceHistoryEntry(MCPModel):
    """Single price history entry."""
    
    supplier_name: str
    pricelist_id: int
    imported_at: str
    ek_price: float
    discount_percent: float
    gewerbepreis: float
    industriepreis: float
    topkundenpreis: float


class RagPriceHistoryResult(MCPModel):
    """Result of price history query."""
    
    ean: str
    found: bool
    product_name: str | None = None
    history: List[PriceHistoryEntry] = Field(default_factory=list)
    price_changes: dict | None = None


@register_tool
class RagPriceHistoryTool(Tool[RagPriceHistoryParams, RagPriceHistoryResult]):
    """Tool to show price history for a product."""
    
    name = "rag_price_history"
    description = "Show price development for a product over time across all price list imports"
    params_model = RagPriceHistoryParams
    result_model = RagPriceHistoryResult
    pricing = ToolPricing(type=PricingType.FREE)
    
    async def execute(
        self,
        ctx: ToolContext[RagPriceHistoryParams, RagPriceHistoryResult]
    ):
        """Execute price history lookup."""
        init_database()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get product
        cursor.execute("SELECT id, ean, name FROM products WHERE ean = ?", (ctx.params.ean,))
        product = cursor.fetchone()
        
        if not product:
            yield ctx.structured(RagPriceHistoryResult(
                ean=ctx.params.ean,
                found=False
            ))
            return
        
        # Get all prices ordered by import date
        query = """
            SELECT 
                s.name as supplier_name,
                pl.id as pricelist_id,
                pl.imported_at,
                pr.ek_price,
                pr.discount_percent,
                pr.gewerbepreis,
                pr.industriepreis,
                pr.topkundenpreis
            FROM prices pr
            JOIN pricelists pl ON pr.pricelist_id = pl.id
            JOIN suppliers s ON pl.supplier_id = s.id
            WHERE pr.product_id = ?
        """
        
        params = [product["id"]]
        
        if ctx.params.supplier_filter:
            query += " AND s.name = ?"
            params.append(ctx.params.supplier_filter)
        
        query += " ORDER BY pl.imported_at ASC, s.name ASC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        history = []
        for row in rows:
            history.append(PriceHistoryEntry(
                supplier_name=row["supplier_name"],
                pricelist_id=row["pricelist_id"],
                imported_at=row["imported_at"],
                ek_price=row["ek_price"],
                discount_percent=row["discount_percent"],
                gewerbepreis=row["gewerbepreis"],
                industriepreis=row["industriepreis"],
                topkundenpreis=row["topkundenpreis"]
            ))
        
        # Calculate price changes
        price_changes = None
        if len(history) > 1:
            first = history[0]
            last = history[-1]
            ek_change = ((last.ek_price - first.ek_price) / first.ek_price * 100) if first.ek_price > 0 else 0
            price_changes = {
                "first_import": first.imported_at,
                "last_import": last.imported_at,
                "first_ek_price": first.ek_price,
                "last_ek_price": last.ek_price,
                "ek_price_change_percent": round(ek_change, 2),
                "total_imports": len(history)
            }
        
        conn.close()
        
        result = RagPriceHistoryResult(
            ean=ctx.params.ean,
            found=True,
            product_name=product["name"],
            history=history,
            price_changes=price_changes
        )
        
        yield ctx.structured(result)

