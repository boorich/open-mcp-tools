"""
Excel parser for price lists with flexible column detection.

Handles varying Excel structures from different suppliers.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

logger = logging.getLogger(__name__)


class ExcelParser:
    """Parser for Excel price list files with flexible column detection."""
    
    # Common column name variations
    EAN_VARIANTS = ["ean", "ean-nummer", "ean code", "ean_code", "ean-nr", "ean nr"]
    PRICE_VARIANTS = ["grundpreis", "preis", "ek", "einkaufspreis", "ek-preis", "ek preis", "listpreis"]
    DISCOUNT_VARIANTS = ["rabatt1", "rabatt2", "rabatt", "rabatt %", "rabatt%", "discount", "nachlass"]
    NAME_VARIANTS = ["bezeichnung", "name", "artikel", "produkt", "beschreibung", "artikelname"]
    
    def __init__(self, file_path: Path):
        """Initialize parser with Excel file path."""
        if not HAS_OPENPYXL:
            raise ImportError("openpyxl is required for Excel parsing. Install with: pip install openpyxl")
        
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"Excel file not found: {file_path}")
        
        self.workbook = None
        self.worksheet = None
        self.header_row = None
        self.column_mapping = {}
    
    def detect_header_row(self, max_rows_to_check: int = 10) -> int:
        """
        Detect the header row by looking for common column names.
        
        Returns row number (1-indexed) or raises ValueError if not found.
        """
        if self.worksheet is None:
            self._load_worksheet()
        
        for row_num in range(1, min(max_rows_to_check + 1, self.worksheet.max_row + 1)):
            row_values = [str(cell.value).lower().strip() if cell.value else "" 
                         for cell in self.worksheet[row_num]]
            
            # Check if this row contains EAN-related column
            has_ean = any(any(variant in val for variant in self.EAN_VARIANTS) for val in row_values)
            # Check if this row contains price-related column
            has_price = any(any(variant in val for variant in self.PRICE_VARIANTS) for val in row_values)
            
            if has_ean and has_price:
                logger.info(f"Detected header row at row {row_num}")
                return row_num
        
        raise ValueError("Could not detect header row. No row found with both EAN and price columns.")
    
    def detect_columns(self, header_row: Optional[int] = None) -> Dict[str, Optional[str]]:
        """
        Detect column mappings from header row.
        
        Returns dict with keys: ean_column, price_column, discount_column, name_column
        """
        if self.worksheet is None:
            self._load_worksheet()
        
        if header_row is None:
            header_row = self.detect_header_row()
        
        self.header_row = header_row
        
        # Get header row values
        header_cells = self.worksheet[header_row]
        headers = {}
        for idx, cell in enumerate(header_cells, start=1):
            if cell.value:
                header_name = str(cell.value).strip()
                headers[idx] = header_name.lower()
        
        # Find EAN column
        ean_column = None
        for col_idx, header in headers.items():
            if any(variant in header for variant in self.EAN_VARIANTS):
                ean_column = col_idx
                break
        
        if ean_column is None:
            raise ValueError("Could not find EAN column in header row")
        
        # Find price column
        price_column = None
        for col_idx, header in headers.items():
            if any(variant in header for variant in self.PRICE_VARIANTS):
                price_column = col_idx
                break
        
        if price_column is None:
            raise ValueError("Could not find price column in header row")
        
        # Find discount column (optional)
        discount_column = None
        for col_idx, header in headers.items():
            if any(variant in header for variant in self.DISCOUNT_VARIANTS):
                # Prefer Rabatt1 over Rabatt2, Rabatt2 over Rabatt
                if discount_column is None or "rabatt1" in header:
                    discount_column = col_idx
                elif "rabatt2" in header and "rabatt1" not in str(discount_column):
                    discount_column = col_idx
        
        # Find name column (optional)
        name_column = None
        for col_idx, header in headers.items():
            if any(variant in header for variant in self.NAME_VARIANTS):
                name_column = col_idx
                break
        
        mapping = {
            "ean_column": ean_column,
            "price_column": price_column,
            "discount_column": discount_column,
            "name_column": name_column,
        }
        
        logger.info(f"Detected column mapping: {mapping}")
        return mapping
    
    def parse_rows(self, column_mapping: Dict[str, Optional[int]], start_row: Optional[int] = None) -> List[Dict]:
        """Parse data rows from Excel file using optimized iter_rows."""
        if self.worksheet is None:
            self._load_worksheet()
        
        if start_row is None:
            start_row = self.header_row + 1 if self.header_row else 2
        
        # Get column indices
        ean_col = int(column_mapping["ean_column"]) if column_mapping.get("ean_column") else None
        price_col = int(column_mapping["price_column"]) if column_mapping.get("price_column") else None
        discount_col = int(column_mapping["discount_column"]) if column_mapping.get("discount_column") else None
        name_col = int(column_mapping["name_column"]) if column_mapping.get("name_column") else None
        
        if not ean_col or not price_col:
            raise ValueError("EAN and price columns are required")
        
        # ✅ FAST - Use iter_rows with read_only mode
        rows = []
        empty_row_count = 0
        max_empty_rows = 100
        
        for row_num, row in enumerate(self.worksheet.iter_rows(min_row=start_row, values_only=True), start=start_row):
            # Early stop if too many empty rows
            if empty_row_count >= max_empty_rows:
                logger.info(f"Stopped parsing at row {row_num} after {max_empty_rows} consecutive empty rows")
                break
            
            # values_only=True gives us a tuple of values, 0-indexed
            ean = self._clean_ean(row[ean_col - 1] if len(row) >= ean_col else None)
            
            if not ean:
                empty_row_count += 1
                continue
            
            empty_row_count = 0
            
            price = self._parse_float(row[price_col - 1] if len(row) >= price_col else None)
            
            if price is None or price <= 0:
                continue
            
            discount = 0.0
            if discount_col and len(row) >= discount_col:
                discount = self._parse_float(row[discount_col - 1]) or 0.0
            
            name = None
            if name_col and len(row) >= name_col:
                val = row[name_col - 1]
                name = str(val).strip() if val else None
            
            rows.append({
                "ean": ean,
                "price": price,
                "discount": discount,
                "name": name,
                "row_number": row_num,
            })
        
        logger.info(f"Parsed {len(rows)} rows from {self.file_path.name}")
        return rows
    
    def _load_worksheet(self) -> None:
        """Load the workbook and first worksheet."""
        self.workbook = openpyxl.load_workbook(self.file_path, read_only=True, data_only=True)
        self.worksheet = self.workbook.active
    
    def _clean_ean(self, value) -> Optional[str]:
        """Clean and validate EAN value."""
        if value is None:
            return None
        
        # Convert to string and remove whitespace
        ean = str(value).strip()
        
        # Remove non-digit characters (except if it's a valid format)
        ean = ''.join(c for c in ean if c.isdigit())
        
        # EAN should be 8, 13, or 14 digits
        if len(ean) in [8, 13, 14] and ean.isdigit():
            return ean
        
        return None
    
    def _parse_float(self, value) -> Optional[float]:
        """Parse float value, handling various formats."""
        if value is None:
            return None
        
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            # Remove common formatting
            value = value.replace(',', '.').replace(' ', '').replace('€', '').strip()
            try:
                return float(value)
            except ValueError:
                return None
        
        return None
    
    def close(self) -> None:
        """Close the workbook."""
        if self.workbook:
            self.workbook.close()
            self.workbook = None
            self.worksheet = None

