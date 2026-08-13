from app.domain.reconciliation_status import ReconciliationStatus

# ---------------------------------------------------------------------------
# Status ordering
# ---------------------------------------------------------------------------
# Single canonical sequence — priorities derived automatically via enumerate.
# Changing STATUS_ORDER automatically updates STATUS_PRIORITY and SQL sort order.
# Starting at 1: 0 conventionally means "unspecified" in CASE expressions.
STATUS_ORDER: tuple[ReconciliationStatus, ...] = (
    ReconciliationStatus.DUPLICATE_SOURCE_KEY,
    ReconciliationStatus.MISSING_CU_NUMBER,
    ReconciliationStatus.MISSING_IN_SAP,
    ReconciliationStatus.MISSING_IN_KRA,
    ReconciliationStatus.MULTIPLE_MISMATCHES,
    ReconciliationStatus.AMOUNT_MISMATCH,
    ReconciliationStatus.VAT_MISMATCH,
    ReconciliationStatus.CU_MISMATCH,
    ReconciliationStatus.PIN_MISMATCH,
    ReconciliationStatus.MATCH,
)

STATUS_PRIORITY: dict[ReconciliationStatus, int] = {
    s: i for i, s in enumerate(STATUS_ORDER, start=1)
}

# ---------------------------------------------------------------------------
# Remark text
# ---------------------------------------------------------------------------
# Change here = change everywhere (export, future email, PDF, dashboard).
# No versioning: treat wording changes as deliberate, explicit migrations.
REMARK_MAP: dict[ReconciliationStatus, str] = {
    ReconciliationStatus.MATCH:               "Match",
    ReconciliationStatus.AMOUNT_MISMATCH:     "Amount Mismatch",
    ReconciliationStatus.VAT_MISMATCH:        "VAT Mismatch",
    ReconciliationStatus.CU_MISMATCH:         "CU Mismatch",
    ReconciliationStatus.PIN_MISMATCH:        "PIN Mismatch",
    ReconciliationStatus.MULTIPLE_MISMATCHES: "Multiple Mismatches",
    ReconciliationStatus.MISSING_IN_SAP:      "Missing in SAP",
    ReconciliationStatus.MISSING_IN_KRA:      "Missing in KRA",
    ReconciliationStatus.MISSING_CU_NUMBER:   "Missing CU Number",
    ReconciliationStatus.DUPLICATE_SOURCE_KEY: "Duplicate MatchKey detected (CU Number + VAT Group)",
}

# ---------------------------------------------------------------------------
# Versioning policy
# ---------------------------------------------------------------------------
# STATUS_PRIORITY_VERSION — increment ONLY when STATUS_ORDER changes
# EXPORT_SCHEMA_VERSION   — increment ONLY when workbook layout or Export.json structure changes
# REMARK_MAP              — change wording freely; no version tracked
STATUS_PRIORITY_VERSION: str = "3"
EXPORT_SCHEMA_VERSION:   str = "2.0"
