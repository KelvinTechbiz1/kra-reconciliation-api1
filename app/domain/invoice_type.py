from enum import Enum


class InvoiceType(str, Enum):
    """
    Metadata property describing the tax composition of an invoice.
    
    An invoice can legitimately contain items from multiple tax categories
    (e.g., 16%, 0%, EXEMPT) under a single CU Number.
    
    `InvoiceType` is metadata describing the invoice structure,
    NOT a reconciliation result or error status.
    """
    SINGLE_TAX = "Single Tax"
    MIXED_TAX = "Mixed Tax"
