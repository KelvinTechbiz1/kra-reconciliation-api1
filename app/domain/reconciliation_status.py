from enum import Enum


class ReconciliationStatus(str, Enum):
    """Canonical reconciliation status — lives in the domain layer, not schemas."""
    MATCH               = "Match"
    MISSING_IN_SAP      = "Missing in SAP"
    MISSING_IN_KRA      = "Missing in KRA"
    MISSING_CU_NUMBER   = "Missing CU Number"
    AMOUNT_MISMATCH     = "Amount Mismatch"
    VAT_MISMATCH        = "VAT Mismatch"
    CU_MISMATCH         = "CU Mismatch"
    PIN_MISMATCH        = "PIN Mismatch"
    MULTIPLE_MISMATCHES = "Multiple Mismatches"
    DUPLICATE_SOURCE_KEY = "Duplicate Source Key"

