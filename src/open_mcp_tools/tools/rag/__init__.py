"""RAG Pipeline Tools Module

Auto-discovery for RAG pipeline price list tools.
"""

# Import tools to trigger registration
from .import_pricelist import RagImportPricelistTool  # noqa: F401
from .lookup_ean import RagLookupEanTool  # noqa: F401
from .bulk_lookup_ean import RagBulkLookupEanTool  # noqa: F401
from .price_history import RagPriceHistoryTool  # noqa: F401
from .search_products import RagSearchProductsTool  # noqa: F401
from .supplier_stats import RagSupplierStatsTool  # noqa: F401
from .compare_basket import RagCompareBasketTool  # noqa: F401
from .list_pricelists import RagListPricelistsTool  # noqa: F401
from .delete_pricelist import RagDeletePricelistTool  # noqa: F401

__all__ = [
    "RagImportPricelistTool",
    "RagLookupEanTool",
    "RagBulkLookupEanTool",
    "RagPriceHistoryTool",
    "RagSearchProductsTool",
    "RagSupplierStatsTool",
    "RagCompareBasketTool",
    "RagListPricelistsTool",
    "RagDeletePricelistTool",
]

