"""
Supplier Statistics Tool

Get overview statistics for all suppliers or a specific supplier.
"""

import logging
from typing import List

from pydantic import Field

from ...core import Tool, ToolContext, register_tool
from ...core.pricing import PricingType, ToolPricing
from ...core.types.models import MCPModel
from .database import get_db_connection, init_database

logger = logging.getLogger(__name__)


class RagSupplierStatsParams(MCPModel):
    """Parameters for supplier statistics tool."""
    
    supplier_name: str | None = Field(
        default=None,
        description="Optional: Get stats for specific supplier only"
    )


class SupplierStatEntry(MCPModel):
    """Statistics for a single supplier."""
    
    supplier_name: str
    total_products: int
    total_pricelists: int
    latest_import: str | None
    oldest_import: str | None
    avg_ek_price: float | None
    min_ek_price: float | None
    max_ek_price: float | None


class RagSupplierStatsResult(MCPModel):
    """Result of supplier statistics query."""
    
    suppliers: List[SupplierStatEntry]
    total_suppliers: int


@register_tool
class RagSupplierStatsTool(Tool[RagSupplierStatsParams, RagSupplierStatsResult]):
    """Tool to get supplier statistics."""
    
    name = "rag_supplier_stats"
    description = "Get overview statistics for all suppliers including product counts, price ranges, and import dates"
    params_model = RagSupplierStatsParams
    result_model = RagSupplierStatsResult
    pricing = ToolPricing(type=PricingType.FREE)
    
    async def execute(
        self,
        ctx: ToolContext[RagSupplierStatsParams, RagSupplierStatsResult]
    ):
        """Execute supplier stats query."""
        init_database()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get suppliers
        if ctx.params.supplier_name:
            cursor.execute("SELECT id, name FROM suppliers WHERE name = ?", (ctx.params.supplier_name,))
        else:
            cursor.execute("SELECT id, name FROM suppliers ORDER BY name")
        
        suppliers = cursor.fetchall()
        
        stats = []
        for supplier in suppliers:
            supplier_id = supplier["id"]
            supplier_name = supplier["name"]
            
            # Count products
            cursor.execute("""
                SELECT COUNT(DISTINCT pr.product_id) as count
                FROM prices pr
                JOIN pricelists pl ON pr.pricelist_id = pl.id
                WHERE pl.supplier_id = ?
            """, (supplier_id,))
            product_count = cursor.fetchone()["count"]
            
            # Count pricelists
            cursor.execute("SELECT COUNT(*) as count FROM pricelists WHERE supplier_id = ?", (supplier_id,))
            pricelist_count = cursor.fetchone()["count"]
            
            # Get import dates
            cursor.execute("""
                SELECT 
                    MIN(imported_at) as oldest,
                    MAX(imported_at) as latest
                FROM pricelists
                WHERE supplier_id = ?
            """, (supplier_id,))
            dates = cursor.fetchone()
            
            # Get price statistics
            cursor.execute("""
                SELECT 
                    AVG(pr.ek_price) as avg_price,
                    MIN(pr.ek_price) as min_price,
                    MAX(pr.ek_price) as max_price
                FROM prices pr
                JOIN pricelists pl ON pr.pricelist_id = pl.id
                WHERE pl.supplier_id = ?
            """, (supplier_id,))
            price_stats = cursor.fetchone()
            
            stats.append(SupplierStatEntry(
                supplier_name=supplier_name,
                total_products=product_count,
                total_pricelists=pricelist_count,
                latest_import=dates["latest"],
                oldest_import=dates["oldest"],
                avg_ek_price=round(price_stats["avg_price"], 2) if price_stats["avg_price"] else None,
                min_ek_price=round(price_stats["min_price"], 2) if price_stats["min_price"] else None,
                max_ek_price=round(price_stats["max_price"], 2) if price_stats["max_price"] else None
            ))
        
        conn.close()
        
        result = RagSupplierStatsResult(
            suppliers=stats,
            total_suppliers=len(stats)
        )
        
        yield ctx.structured(result)

