"""
List Pricelists Tool

Show all imported price lists with metadata.
"""

import logging
from typing import List

from pydantic import Field

from ...core import Tool, ToolContext, register_tool
from ...core.pricing import PricingType, ToolPricing
from ...core.types.models import MCPModel
from .database import get_db_connection, init_database

logger = logging.getLogger(__name__)


class RagListPricelistsParams(MCPModel):
    """Parameters for list pricelists tool."""
    
    supplier_filter: str | None = Field(
        default=None,
        description="Optional: Filter by specific supplier name"
    )


class PricelistEntry(MCPModel):
    """Single pricelist entry."""
    
    pricelist_id: int
    supplier_name: str
    file_path: str
    imported_at: str
    version: str | None = None
    product_count: int
    price_count: int


class RagListPricelistsResult(MCPModel):
    """Result of list pricelists query."""
    
    pricelists: List[PricelistEntry]
    total_pricelists: int


@register_tool
class RagListPricelistsTool(Tool[RagListPricelistsParams, RagListPricelistsResult]):
    """Tool to list all imported price lists."""
    
    name = "rag_list_pricelists"
    description = "List all imported price lists with details about supplier, import date, and product counts"
    params_model = RagListPricelistsParams
    result_model = RagListPricelistsResult
    pricing = ToolPricing(type=PricingType.FREE)
    
    async def execute(
        self,
        ctx: ToolContext[RagListPricelistsParams, RagListPricelistsResult]
    ):
        """Execute list pricelists query."""
        init_database()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get pricelists
        query = """
            SELECT 
                pl.id,
                s.name as supplier_name,
                pl.file_path,
                pl.imported_at,
                pl.version
            FROM pricelists pl
            JOIN suppliers s ON pl.supplier_id = s.id
        """
        
        params = []
        if ctx.params.supplier_filter:
            query += " WHERE s.name = ?"
            params.append(ctx.params.supplier_filter)
        
        query += " ORDER BY pl.imported_at DESC"
        
        cursor.execute(query, params)
        pricelists = cursor.fetchall()
        
        results = []
        for pl in pricelists:
            # Count unique products in this pricelist
            cursor.execute("""
                SELECT COUNT(DISTINCT product_id) as count
                FROM prices
                WHERE pricelist_id = ?
            """, (pl["id"],))
            product_count = cursor.fetchone()["count"]
            
            # Count prices in this pricelist
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM prices
                WHERE pricelist_id = ?
            """, (pl["id"],))
            price_count = cursor.fetchone()["count"]
            
            results.append(PricelistEntry(
                pricelist_id=pl["id"],
                supplier_name=pl["supplier_name"],
                file_path=pl["file_path"],
                imported_at=pl["imported_at"],
                version=pl["version"],
                product_count=product_count,
                price_count=price_count
            ))
        
        conn.close()
        
        result = RagListPricelistsResult(
            pricelists=results,
            total_pricelists=len(results)
        )
        
        yield ctx.structured(result)

