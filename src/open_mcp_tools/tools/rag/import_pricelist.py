"""
RAG Import Price List Tool

Imports Excel price lists into SQLite database with flexible column detection.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from pydantic import Field

from ...core import Tool, ToolContext, register_tool
from ...core.pricing import PricingType, ToolPricing
from ...core.types.models import MCPModel
from .database import (
    get_db_connection,
    get_or_create_supplier,
    get_supplier_column_mapping,
    init_database,
    save_supplier_column_mapping,
)
from .excel_parser import ExcelParser

logger = logging.getLogger(__name__)


class RagImportPricelistParams(MCPModel):
    """Parameters for importing a price list"""
    
    file_path: str = Field(description="Path to Excel file (.xlsx)")
    supplier_name: str = Field(description="Name of the supplier")
    header_row: Optional[int] = Field(
        default=None,
        description="Row number for headers (1-indexed). Auto-detect if not provided."
    )
    column_mapping: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Manual column mapping override (JSON dict with ean_column, price_column, etc.)",
        json_schema_extra={
            "type": "object",
            "properties": {
                "ean_column": {"type": "string"},
                "price_column": {"type": "string"},
                "discount_column": {"type": "string"},
                "name_column": {"type": "string"}
            }
        }
    )
    version: Optional[str] = Field(
        default=None,
        description="Version identifier for this price list"
    )


class ImportSummary(MCPModel):
    """Summary of import operation"""
    
    rows_processed: int = Field(description="Number of rows successfully processed")
    rows_skipped: int = Field(description="Number of rows skipped (invalid data)")
    products_added: int = Field(description="Number of new products added")
    products_updated: int = Field(description="Number of existing products updated")
    prices_added: int = Field(description="Number of new prices added")
    prices_updated: int = Field(description="Number of existing prices updated")
    errors: list[str] = Field(default_factory=list, description="List of error messages")


class RagImportPricelistResult(MCPModel):
    """Result from importing a price list"""
    
    success: bool = Field(description="Whether import was successful")
    supplier_id: int = Field(description="Supplier ID in database")
    pricelist_id: int = Field(description="Price list ID in database")
    summary: ImportSummary = Field(description="Import summary statistics")
    column_mapping_used: dict = Field(description="Column mapping that was used")


@register_tool
class RagImportPricelistTool(Tool[RagImportPricelistParams, RagImportPricelistResult]):
    """Import Excel price list into database"""
    
    name = "rag_import_pricelist"
    description = "Import an Excel price list file into the database. Automatically detects column structure and calculates price tiers (Gewerbepreis, Industriepreis, Topkundenpreis)."
    params_model = RagImportPricelistParams
    result_model = RagImportPricelistResult
    
    pricing = ToolPricing(type=PricingType.FREE)
    
    async def execute(
        self,
        ctx: ToolContext[RagImportPricelistParams, RagImportPricelistResult]
    ):
        """Execute the import price list tool"""
        # Initialize database if needed
        init_database()
        
        file_path = Path(ctx.params.file_path)
        if not file_path.is_absolute():
            # Try relative to project root
            project_root = Path(__file__).parent.parent.parent.parent.parent
            file_path = project_root / file_path
        
        if not file_path.exists():
            result = RagImportPricelistResult(
                success=False,
                supplier_id=0,
                pricelist_id=0,
                summary=ImportSummary(
                    rows_processed=0,
                    rows_skipped=0,
                    products_added=0,
                    products_updated=0,
                    prices_added=0,
                    prices_updated=0,
                    errors=[f"File not found: {file_path}"]
                ),
                column_mapping_used={}
            )
            yield ctx.structured(result)
            return
        
        conn = get_db_connection()
        parser = None
        
        try:
            # Get or create supplier
            supplier_id = get_or_create_supplier(conn, ctx.params.supplier_name)
            
            # Initialize parser
            parser = ExcelParser(file_path)
            # Ensure worksheet is loaded
            if parser.worksheet is None:
                parser._load_worksheet()
            
            # Detect or use provided column mapping
            if ctx.params.column_mapping:
                column_mapping = ctx.params.column_mapping
                # Ensure column numbers are integers
                column_mapping = {
                    "ean_column": int(column_mapping.get("ean_column", 0)),
                    "price_column": int(column_mapping.get("price_column", 0)),
                    "discount_column": int(column_mapping.get("discount_column")) if column_mapping.get("discount_column") else None,
                    "name_column": int(column_mapping.get("name_column")) if column_mapping.get("name_column") else None,
                }
                if ctx.params.header_row:
                    parser.header_row = ctx.params.header_row
                else:
                    parser.header_row = parser.detect_header_row()
            else:
                # Try to use cached mapping
                cached_mapping = get_supplier_column_mapping(conn, supplier_id)
                if cached_mapping:
                    column_mapping = {
                        "ean_column": int(cached_mapping["ean_column"]),
                        "price_column": int(cached_mapping["price_column"]),
                        "discount_column": int(cached_mapping["discount_column"]) if cached_mapping.get("discount_column") else None,
                        "name_column": int(cached_mapping["name_column"]) if cached_mapping.get("name_column") else None,
                    }
                    parser.header_row = int(cached_mapping["header_row"])
                else:
                    # Detect columns
                    if ctx.params.header_row:
                        parser.header_row = ctx.params.header_row
                    else:
                        parser.header_row = parser.detect_header_row()
                    column_mapping = parser.detect_columns(parser.header_row)
            
            # Parse rows in async chunks to allow cancellation
            logger.info("Starting to parse Excel file...")
            # ✅ Use optimized parser (much faster)
            rows = parser.parse_rows(column_mapping, start_row=parser.header_row + 1)
            logger.info(f"Parsed {len(rows)} rows from Excel file")
            
            # Check for cancellation before proceeding
            if ctx.request.is_cancelled():
                raise asyncio.CancelledError("Import cancelled by user")
            
            logger.info("Creating pricelist entry...")
            # Create pricelist entry
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO pricelists (supplier_id, file_path, version)
                VALUES (?, ?, ?)
            """, (supplier_id, str(file_path), ctx.params.version))
            pricelist_id = int(cursor.lastrowid)  # Ensure it's an integer
            logger.info(f"Created pricelist entry with ID: {pricelist_id}")
            
            # Save column mapping for future use
            logger.info("Saving column mapping...")
            save_supplier_column_mapping(
                conn,
                supplier_id,
                str(column_mapping["ean_column"]),
                str(column_mapping["price_column"]),
                str(column_mapping.get("discount_column")) if column_mapping.get("discount_column") else None,
                str(column_mapping.get("name_column")) if column_mapping.get("name_column") else None,
                parser.header_row
            )
            logger.info("Column mapping saved")
            
            # ✅ OPTIMIZED: Process all data in memory first
            logger.info(f"Processing {len(rows)} rows in memory...")
            summary = ImportSummary(
                rows_processed=0,
                rows_skipped=0,
                products_added=0,
                products_updated=0,
                prices_added=0,
                prices_updated=0,
                errors=[]
            )
            
            # Deduplicate and prepare data (last EAN wins)
            product_data = {}  # ean -> name
            price_data = {}    # ean -> (ek, discount, gewerbe, industrie, topkunden)
            
            for row_data in rows:
                try:
                    ean = row_data["ean"]
                    price = float(row_data["price"])
                    discount = float(row_data.get("discount", 0.0))
                    name = row_data.get("name")
                    
                    # Calculate price tiers
                    ek_price = price * (1 - discount / 100) if discount > 0 else price
                    gewerbepreis = ek_price * 1.4
                    industriepreis = ek_price * 1.3
                    topkundenpreis = ek_price * 1.2
                    
                    product_data[ean] = name
                    price_data[ean] = (ek_price, discount, gewerbepreis, industriepreis, topkundenpreis)
                    
                except Exception as e:
                    summary.rows_skipped += 1
                    summary.errors.append(f"Row {row_data.get('row_number', 'unknown')}: {str(e)}")
            
            logger.info(f"Prepared {len(product_data)} unique products, {len(price_data)} prices")
            await asyncio.sleep(0)
            
            # ✅ Get existing products in ONE query
            eans = list(product_data.keys())
            existing_eans = set()
            if eans:
                # Split into batches of 900 (SQLite limit is 999 params)
                for i in range(0, len(eans), 900):
                    batch = eans[i:i+900]
                    placeholders = ','.join(['?'] * len(batch))
                    cursor.execute(f"SELECT ean FROM products WHERE ean IN ({placeholders})", batch)
                    existing_eans.update(row["ean"] for row in cursor.fetchall())
                
                summary.products_updated = len(existing_eans)
                summary.products_added = len(eans) - len(existing_eans)
            
            # ✅ Batch insert NEW products only
            new_products = [(ean, name) for ean, name in product_data.items() if ean not in existing_eans]
            if new_products:
                logger.info(f"Inserting {len(new_products)} new products...")
                for i in range(0, len(new_products), 900):
                    batch = new_products[i:i+900]
                    cursor.executemany("INSERT INTO products (ean, name) VALUES (?, ?)", batch)
                await asyncio.sleep(0)
            
            # ✅ Update existing products with new names (if provided)
            updates = [(name, ean) for ean, name in product_data.items() 
                       if ean in existing_eans and name]
            if updates:
                logger.info(f"Updating {len(updates)} product names...")
                for i in range(0, len(updates), 900):
                    batch = updates[i:i+900]
                    cursor.executemany("UPDATE products SET name = ? WHERE ean = ? AND name IS NULL", batch)
                await asyncio.sleep(0)
            
            # ✅ Get ALL product IDs in ONE query
            ean_to_id = {}
            for i in range(0, len(eans), 900):
                batch = eans[i:i+900]
                placeholders = ','.join(['?'] * len(batch))
                cursor.execute(f"SELECT id, ean FROM products WHERE ean IN ({placeholders})", batch)
                ean_to_id.update({row["ean"]: row["id"] for row in cursor.fetchall()})
            await asyncio.sleep(0)
            
            # ✅ Prepare ALL price inserts
            prices_to_insert = []
            for ean, (ek, disc, gew, ind, top) in price_data.items():
                if ean in ean_to_id:
                    prices_to_insert.append((
                        ean_to_id[ean], pricelist_id, ek, disc, gew, ind, top
                    ))
                else:
                    summary.rows_skipped += 1
            
            summary.rows_processed = len(prices_to_insert)
            
            # ✅ Single batch insert for ALL prices
            if prices_to_insert:
                logger.info(f"Inserting {len(prices_to_insert)} prices...")
                for i in range(0, len(prices_to_insert), 900):
                    batch = prices_to_insert[i:i+900]
                    cursor.executemany("""
                        INSERT OR REPLACE INTO prices
                        (product_id, pricelist_id, ek_price, discount_percent,
                         gewerbepreis, industriepreis, topkundenpreis)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, batch)
                
                summary.prices_added = len(prices_to_insert)
                await asyncio.sleep(0)
            logger.info(f"Committing transaction...")
            conn.commit()
            logger.info(f"Transaction committed successfully")
            logger.info(f"Import completed: {summary.rows_processed} rows processed, {summary.products_added} products added, {summary.prices_added} prices added")
            
            result = RagImportPricelistResult(
                success=True,
                supplier_id=supplier_id,
                pricelist_id=pricelist_id,
                summary=summary,
                column_mapping_used=column_mapping
            )
            
            yield ctx.structured(result)
            
        except asyncio.CancelledError:
            conn.rollback()
            logger.info("Import cancelled by user")
            result = RagImportPricelistResult(
                success=False,
                supplier_id=supplier_id if 'supplier_id' in locals() else 0,
                pricelist_id=pricelist_id if 'pricelist_id' in locals() else 0,
                summary=ImportSummary(
                    rows_processed=summary.rows_processed if 'summary' in locals() else 0,
                    rows_skipped=summary.rows_skipped if 'summary' in locals() else 0,
                    products_added=summary.products_added if 'summary' in locals() else 0,
                    products_updated=summary.products_updated if 'summary' in locals() else 0,
                    prices_added=summary.prices_added if 'summary' in locals() else 0,
                    prices_updated=summary.prices_updated if 'summary' in locals() else 0,
                    errors=["Import cancelled by user"]
                ),
                column_mapping_used={}
            )
            yield ctx.structured(result)
            return
        except Exception as e:
            conn.rollback()
            error_msg = f"Import failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            result = RagImportPricelistResult(
                success=False,
                supplier_id=0,
                pricelist_id=0,
                summary=ImportSummary(
                    rows_processed=0,
                    rows_skipped=0,
                    products_added=0,
                    products_updated=0,
                    prices_added=0,
                    prices_updated=0,
                    errors=[error_msg]
                ),
                column_mapping_used={}
            )
            yield ctx.structured(result)
        
        finally:
            if parser:
                parser.close()
            conn.close()

