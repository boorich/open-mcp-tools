"""
Product Search Tool

Search for products by name/description across all suppliers.
"""

import logging
from typing import List

from pydantic import Field

from ...core import Tool, ToolContext, register_tool
from ...core.pricing import PricingType, ToolPricing
from ...core.types.models import MCPModel
from .database import get_db_connection, init_database

logger = logging.getLogger(__name__)


class RagSearchProductsParams(MCPModel):
    """Parameters for product search tool."""
    
    search_term: str = Field(..., description="Search term to find in product names")
    limit: int = Field(
        default=50,
        description="Maximum number of results to return",
        ge=1,
        le=500
    )
    supplier_filter: str | None = Field(
        default=None,
        description="Optional: Filter by specific supplier name"
    )


class ProductSearchResult(MCPModel):
    """Single product search result."""
    
    ean: str
    name: str | None
    suppliers: List[str]
    cheapest_ek_price: float
    cheapest_supplier: str


class RagSearchProductsResult(MCPModel):
    """Result of product search."""
    
    search_term: str
    total_found: int
    results: List[ProductSearchResult]


@register_tool
class RagSearchProductsTool(Tool[RagSearchProductsParams, RagSearchProductsResult]):
    """Tool to search for products by name."""
    
    name = "rag_search_products"
    description = "Search for products by name or description. Returns matching products with their cheapest prices."
    params_model = RagSearchProductsParams
    result_model = RagSearchProductsResult
    pricing = ToolPricing(type=PricingType.FREE)
    
    async def execute(
        self,
        ctx: ToolContext[RagSearchProductsParams, RagSearchProductsResult]
    ):
        """Execute product search."""
        init_database()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Search products by name (case-insensitive)
        search_pattern = f"%{ctx.params.search_term}%"
        
        query = """
            SELECT DISTINCT
                p.ean,
                p.name
            FROM products p
            WHERE p.name LIKE ? COLLATE NOCASE
            LIMIT ?
        """
        
        cursor.execute(query, (search_pattern, ctx.params.limit))
        products = cursor.fetchall()
        
        results = []
        for product in products:
            # Get all prices for this product
            price_query = """
                SELECT 
                    s.name as supplier_name,
                    pr.ek_price
                FROM prices pr
                JOIN pricelists pl ON pr.pricelist_id = pl.id
                JOIN suppliers s ON pl.supplier_id = s.id
                WHERE pr.product_id = (SELECT id FROM products WHERE ean = ?)
            """
            
            price_params = [product["ean"]]
            
            if ctx.params.supplier_filter:
                price_query += " AND s.name = ?"
                price_params.append(ctx.params.supplier_filter)
            
            price_query += " ORDER BY pr.ek_price ASC"
            
            cursor.execute(price_query, price_params)
            prices = cursor.fetchall()
            
            if prices:
                cheapest = prices[0]
                suppliers = list(set(p["supplier_name"] for p in prices))
                
                results.append(ProductSearchResult(
                    ean=product["ean"],
                    name=product["name"],
                    suppliers=suppliers,
                    cheapest_ek_price=cheapest["ek_price"],
                    cheapest_supplier=cheapest["supplier_name"]
                ))
        
        conn.close()
        
        result = RagSearchProductsResult(
            search_term=ctx.params.search_term,
            total_found=len(results),
            results=results
        )
        
        yield ctx.structured(result)

