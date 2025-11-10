"""
Database utilities for RAG pipeline price list storage.

Handles SQLite database connection, schema creation, and initialization.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Database location
DB_DIR = Path(__file__).parent.parent.parent.parent.parent / "resources" / "pricelists"
DB_PATH = DB_DIR / "pricelist.db"


def init_database() -> None:
    """Initialize the database and create tables if they don't exist."""
    # Ensure directory exists
    DB_DIR.mkdir(parents=True, exist_ok=True)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create suppliers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create pricelists table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pricelists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            version TEXT,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        )
    """)
    
    # Create products table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ean TEXT NOT NULL,
            name TEXT,
            description TEXT,
            UNIQUE(ean)
        )
    """)
    
    # Create prices table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            pricelist_id INTEGER NOT NULL,
            ek_price REAL NOT NULL,
            discount_percent REAL DEFAULT 0,
            gewerbepreis REAL,
            industriepreis REAL,
            topkundenpreis REAL,
            valid_from DATE,
            valid_to DATE,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (pricelist_id) REFERENCES pricelists(id),
            UNIQUE(product_id, pricelist_id)
        )
    """)
    
    # Create supplier column mappings table (for caching column mappings)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS supplier_column_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL,
            ean_column TEXT,
            price_column TEXT,
            discount_column TEXT,
            name_column TEXT,
            header_row INTEGER,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
            UNIQUE(supplier_id)
        )
    """)
    
    # Create indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_ean ON products(ean)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prices_product_id ON prices(product_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prices_pricelist_id ON prices(pricelist_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prices_ek_price ON prices(ek_price)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name)")
    
    conn.commit()
    logger.info(f"Database initialized at {DB_PATH}")


def get_db_connection() -> sqlite3.Connection:
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn


def get_or_create_supplier(conn: sqlite3.Connection, supplier_name: str) -> int:
    """Get supplier ID, creating supplier if it doesn't exist."""
    cursor = conn.cursor()
    
    # Try to get existing supplier
    cursor.execute("SELECT id FROM suppliers WHERE name = ?", (supplier_name,))
    row = cursor.fetchone()
    
    if row:
        return row["id"]
    
    # Create new supplier
    cursor.execute("INSERT INTO suppliers (name) VALUES (?)", (supplier_name,))
    conn.commit()
    return cursor.lastrowid


def get_supplier_column_mapping(conn: sqlite3.Connection, supplier_id: int) -> Optional[dict]:
    """Get cached column mapping for a supplier."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ean_column, price_column, discount_column, name_column, header_row
        FROM supplier_column_mappings
        WHERE supplier_id = ?
    """, (supplier_id,))
    
    row = cursor.fetchone()
    if row:
        return {
            "ean_column": row["ean_column"],
            "price_column": row["price_column"],
            "discount_column": row["discount_column"],
            "name_column": row["name_column"],
            "header_row": row["header_row"],
        }
    return None


def save_supplier_column_mapping(
    conn: sqlite3.Connection,
    supplier_id: int,
    ean_column: str,
    price_column: str,
    discount_column: Optional[str],
    name_column: Optional[str],
    header_row: int,
) -> None:
    """Save column mapping for a supplier."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO supplier_column_mappings
        (supplier_id, ean_column, price_column, discount_column, name_column, header_row)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (supplier_id, ean_column, price_column, discount_column, name_column, header_row))
    conn.commit()

