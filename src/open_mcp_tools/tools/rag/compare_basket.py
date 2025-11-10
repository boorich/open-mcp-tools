"""
Compare Basket Tool

Compare total cost of a basket of items across different suppliers.
"""

import logging
from typing import List

from pydantic import Field

from ...core import Tool, ToolContext, register_tool
from ...core.pricing import PricingType, ToolPricing
from ...core.types.models import MCPModel
from .database import get_db_connection, init_database

logger = logging.getLogger(__name__)


class BasketItem(MCPModel):
    """Single item in the basket."""
    
    ean: str = Field(..., description="EAN code of the product")
    quantity: int = Field(..., description="Quantity to order", ge=1)


class RagCompareBasketParams(MCPModel):
    """Parameters for basket comparison tool."""
    
    items: List[BasketItem] = Field(
        ...,
        description="List of items with EAN and quantity",
        min_items=1,
        max_items=500
    )
    price_tier: str = Field(
        default="gewerbepreis",
        description="Price tier to use: 'ek', 'gewerbepreis', 'industriepreis', or 'topkundenpreis'"
    )


class BasketItemPrice(MCPModel):
    """Price information for a basket item."""
    
    ean: str
    product_name: str | None = None
    quantity: int
    found: bool
    unit_price: float | None = None
    total_price: float | None = None


class SupplierBasketTotal(MCPModel):
    """Total cost for a supplier."""
    
    supplier_name: str
    items: List[BasketItemPrice]
    items_available: int
    items_missing: int
    total_cost: float
    missing_eans: List[str] = Field(default_factory=list)


class RagCompareBasketResult(MCPModel):
    """Result of basket comparison."""
    
    suppliers: List[SupplierBasketTotal]
    best_supplier: str | None = None
    best_total: float | None = None


@register_tool
class RagCompareBasketTool(Tool[RagCompareBasketParams, RagCompareBasketResult]):
    """Tool to compare basket costs across suppliers."""
    
    name = "rag_compare_basket"
    description = "Compare the total cost of a shopping basket across different suppliers to find the best deal"
    params_model = RagCompareBasketParams
    result_model = RagCompareBasketResult
    pricing = ToolPricing(type=PricingType.FREE)
    
    async def execute(
        self,
        ctx: ToolContext[RagCompareBasketParams, RagCompareBasketResult]
    ):
        """Execute basket comparison."""
        init_database()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Map price tier to column
        price_column_map = {
            "ek": "ek_price",
            "gewerbepreis": "gewerbepreis",
            "industriepreis": "industriepreis",
            "topkundenpreis": "topkundenpreis"
        }
        price_column = price_column_map.get(ctx.params.price_tier, "gewerbepreis")
        
        # Get all suppliers
        cursor.execute("SELECT id, name FROM suppliers ORDER BY name")
        suppliers = cursor.fetchall()
        
        supplier_results = []
        
        for supplier in suppliers:
            supplier_id = supplier["id"]
            supplier_name = supplier["name"]
            
            items_prices = []
            total_cost = 0
            items_available = 0
            items_missing = 0
            missing_eans = []
            
            for item in ctx.params.items:
                # First get product info
                cursor.execute("SELECT id, name FROM products WHERE ean = ?", (item.ean,))
                product = cursor.fetchone()
                
                if not product:
                    # Product doesn't exist at all
                    items_missing += 1
                    missing_eans.append(item.ean)
                    items_prices.append(BasketItemPrice(
                        ean=item.ean,
                        product_name=None,
                        quantity=item.quantity,
                        found=False
                    ))
                    continue
                
                # Get latest price from this supplier
                cursor.execute(f"""
                    SELECT pr.{price_column} as unit_price
                    FROM prices pr
                    JOIN pricelists pl ON pr.pricelist_id = pl.id
                    WHERE pr.product_id = ? AND pl.supplier_id = ?
                    ORDER BY pl.imported_at DESC
                    LIMIT 1
                """, (product["id"], supplier_id))
                
                price_row = cursor.fetchone()
                
                if price_row and price_row["unit_price"]:
                    unit_price = price_row["unit_price"]
                    total_price = unit_price * item.quantity
                    total_cost += total_price
                    items_available += 1
                    
                    items_prices.append(BasketItemPrice(
                        ean=item.ean,
                        product_name=product["name"],
                        quantity=item.quantity,
                        found=True,
                        unit_price=unit_price,
                        total_price=total_price
                    ))
                else:
                    # Product exists but supplier doesn't have it
                    items_missing += 1
                    missing_eans.append(item.ean)
                    items_prices.append(BasketItemPrice(
                        ean=item.ean,
                        product_name=product["name"],
                        quantity=item.quantity,
                        found=False
                    ))
            
            supplier_results.append(SupplierBasketTotal(
                supplier_name=supplier_name,
                items=items_prices,
                items_available=items_available,
                items_missing=items_missing,
                total_cost=round(total_cost, 2),
                missing_eans=missing_eans
            ))
        
        # Find best supplier (lowest total cost with most items available)
        valid_suppliers = [s for s in supplier_results if s.items_available > 0]
        best_supplier = None
        best_total = None
        
        if valid_suppliers:
            # Sort by: most items available, then lowest cost
            valid_suppliers.sort(key=lambda s: (-s.items_available, s.total_cost))
            best = valid_suppliers[0]
            best_supplier = best.supplier_name
            best_total = best.total_cost
        
        conn.close()
        
        result = RagCompareBasketResult(
            suppliers=supplier_results,
            best_supplier=best_supplier,
            best_total=best_total
        )
        
        yield ctx.structured(result)

