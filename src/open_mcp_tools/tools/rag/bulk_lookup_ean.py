"""
Bulk EAN Lookup Tool

Lookup multiple EANs at once and get all prices from all suppliers.
"""

import logging
from typing import List

from pydantic import Field

from ...core import Tool, ToolContext, register_tool
from ...core.pricing import PricingType, ToolPricing
from ...core.types.models import MCPModel
from .database import get_db_connection, init_database

logger = logging.getLogger(__name__)


class RagBulkLookupEanParams(MCPModel):
    """Parameters for bulk EAN lookup tool."""
    
    eans: List[str] = Field(
        ...,
        description="List of EAN codes to search for",
        min_items=1,
        max_items=100
    )
    supplier_filter: str | None = Field(
        default=None,
        description="Optional: Filter results by specific supplier name"
    )


class EanPriceInfo(MCPModel):
    """Price information for a single EAN."""
    
    ean: str
    found: bool
    product_name: str | None = None
    prices: List[dict] = Field(default_factory=list)
    total_suppliers: int = 0


class RagBulkLookupEanResult(MCPModel):
    """Result of bulk EAN lookup."""
    
    results: List[EanPriceInfo]
    total_eans_searched: int
    total_found: int
    total_not_found: int


@register_tool
class RagBulkLookupEanTool(Tool[RagBulkLookupEanParams, RagBulkLookupEanResult]):
    """Tool to lookup multiple EAN codes at once."""
    
    name = "rag_bulk_lookup_ean"
    description = "Search for multiple EAN codes in the database and return all available prices from different suppliers, sorted by price"
    params_model = RagBulkLookupEanParams
    result_model = RagBulkLookupEanResult
    pricing = ToolPricing(type=PricingType.FREE)
    
    async def execute(
        self,
        ctx: ToolContext[RagBulkLookupEanParams, RagBulkLookupEanResult]
    ):
        """Execute bulk EAN lookup."""
        # Initialize database
        init_database()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        results = []
        found_count = 0
        not_found_count = 0
        
        for ean in ctx.params.eans:
            # Get product info
            cursor.execute("SELECT id, ean, name FROM products WHERE ean = ?", (ean,))
            product = cursor.fetchone()
            
            if not product:
                results.append(EanPriceInfo(
                    ean=ean,
                    found=False,
                    total_suppliers=0
                ))
                not_found_count += 1
                continue
            
            # Get all prices for this product
            query = """
                SELECT 
                    s.name as supplier_name,
                    pr.ek_price,
                    pr.discount_percent,
                    pr.gewerbepreis,
                    pr.industriepreis,
                    pr.topkundenpreis,
                    pl.id as pricelist_id,
                    pl.imported_at
                FROM prices pr
                JOIN pricelists pl ON pr.pricelist_id = pl.id
                JOIN suppliers s ON pl.supplier_id = s.id
                WHERE pr.product_id = ?
            """
            
            params = [product["id"]]
            
            if ctx.params.supplier_filter:
                query += " AND s.name = ?"
                params.append(ctx.params.supplier_filter)
            
            query += " ORDER BY pr.ek_price ASC"
            
            cursor.execute(query, params)
            price_rows = cursor.fetchall()
            
            prices = []
            for row in price_rows:
                prices.append({
                    "supplierName": row["supplier_name"],
                    "ekPrice": row["ek_price"],
                    "discountPercent": row["discount_percent"],
                    "gewerbepreis": row["gewerbepreis"],
                    "industriepreis": row["industriepreis"],
                    "topkundenpreis": row["topkundenpreis"],
                    "pricelistId": row["pricelist_id"],
                    "importedAt": row["imported_at"]
                })
            
            results.append(EanPriceInfo(
                ean=ean,
                found=True,
                product_name=product["name"],
                prices=prices,
                total_suppliers=len(prices)
            ))
            found_count += 1
        
        conn.close()
        
        result = RagBulkLookupEanResult(
            results=results,
            total_eans_searched=len(ctx.params.eans),
            total_found=found_count,
            total_not_found=not_found_count
        )
        
        yield ctx.structured(result)

