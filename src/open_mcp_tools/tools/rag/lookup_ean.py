"""
RAG Lookup EAN Tool

Searches for EAN codes in the database and returns all available prices sorted by price.
"""

import logging
from typing import List, Optional

from pydantic import Field

from ...core import Tool, ToolContext, register_tool
from ...core.pricing import PricingType, ToolPricing
from ...core.types.models import MCPModel
from .database import get_db_connection, init_database

logger = logging.getLogger(__name__)


class PriceInfo(MCPModel):
    """Price information for a single supplier"""
    
    supplier_name: str = Field(description="Name of the supplier")
    ek_price: float = Field(description="Einkaufspreis (base price)")
    discount_percent: float = Field(description="Discount percentage")
    gewerbepreis: float = Field(description="Gewerbepreis (EK * 1.4)")
    industriepreis: float = Field(description="Industriepreis (EK * 1.3)")
    topkundenpreis: float = Field(description="Topkundenpreis (EK * 1.2)")
    pricelist_id: int = Field(description="Price list ID")
    imported_at: Optional[str] = Field(default=None, description="Import timestamp")


class RagLookupEanResult(MCPModel):
    """Result from EAN lookup"""
    
    ean: str = Field(description="EAN code that was searched")
    found: bool = Field(description="Whether EAN was found")
    product_name: Optional[str] = Field(default=None, description="Product name if available")
    prices: List[PriceInfo] = Field(
        default_factory=list,
        description="List of prices from different suppliers, sorted by EK price (ascending)"
    )
    total_suppliers: int = Field(description="Total number of suppliers offering this EAN")


class RagLookupEanParams(MCPModel):
    """Parameters for EAN lookup"""
    
    ean: str = Field(description="EAN code to search for")
    supplier_filter: Optional[str] = Field(
        default=None,
        description="Optional: Filter results by specific supplier name"
    )


@register_tool
class RagLookupEanTool(Tool[RagLookupEanParams, RagLookupEanResult]):
    """Lookup EAN code and return all available prices from different suppliers"""
    
    name = "rag_lookup_ean"
    description = "Search for an EAN code in the database and return all available prices from different suppliers, sorted by price. Includes all price tiers (Gewerbepreis, Industriepreis, Topkundenpreis)."
    params_model = RagLookupEanParams
    result_model = RagLookupEanResult
    
    pricing = ToolPricing(type=PricingType.FREE)
    
    async def execute(
        self,
        ctx: ToolContext[RagLookupEanParams, RagLookupEanResult]
    ):
        """Execute the EAN lookup tool"""
        # Initialize database if needed
        init_database()
        
        conn = get_db_connection()
        
        try:
            # Clean EAN (remove non-digits)
            ean = ''.join(c for c in ctx.params.ean if c.isdigit())
            
            if not ean:
                result = RagLookupEanResult(
                    ean=ctx.params.ean,
                    found=False,
                    product_name=None,
                    prices=[],
                    total_suppliers=0
                )
                yield ctx.structured(result)
                return
            
            # Query for product and prices
            cursor = conn.cursor()
            
            # Get product info
            cursor.execute("SELECT id, name FROM products WHERE ean = ?", (ean,))
            product_row = cursor.fetchone()
            
            if not product_row:
                result = RagLookupEanResult(
                    ean=ean,
                    found=False,
                    product_name=None,
                    prices=[],
                    total_suppliers=0
                )
                yield ctx.structured(result)
                return
            
            product_id = product_row["id"]
            product_name = product_row["name"]
            
            # Build query for prices
            query = """
                SELECT 
                    s.name AS supplier_name,
                    p.ek_price,
                    p.discount_percent,
                    p.gewerbepreis,
                    p.industriepreis,
                    p.topkundenpreis,
                    p.pricelist_id,
                    pl.imported_at
                FROM prices p
                JOIN pricelists pl ON p.pricelist_id = pl.id
                JOIN suppliers s ON pl.supplier_id = s.id
                WHERE p.product_id = ?
            """
            params = [product_id]
            
            if ctx.params.supplier_filter:
                query += " AND s.name = ?"
                params.append(ctx.params.supplier_filter)
            
            query += " ORDER BY p.ek_price ASC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            prices = []
            for row in rows:
                price_info = PriceInfo(
                    supplier_name=row["supplier_name"],
                    ek_price=float(row["ek_price"]),
                    discount_percent=float(row["discount_percent"] or 0.0),
                    gewerbepreis=float(row["gewerbepreis"]),
                    industriepreis=float(row["industriepreis"]),
                    topkundenpreis=float(row["topkundenpreis"]),
                    pricelist_id=row["pricelist_id"],
                    imported_at=row["imported_at"] if row["imported_at"] else None
                )
                prices.append(price_info)
            
            result = RagLookupEanResult(
                ean=ean,
                found=True,
                product_name=product_name,
                prices=prices,
                total_suppliers=len(prices)
            )
            
            yield ctx.structured(result)
            
        except Exception as e:
            logger.error(f"Error looking up EAN {ctx.params.ean}: {e}", exc_info=True)
            result = RagLookupEanResult(
                ean=ctx.params.ean,
                found=False,
                product_name=None,
                prices=[],
                total_suppliers=0
            )
            yield ctx.structured(result)
        
        finally:
            conn.close()

