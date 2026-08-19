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


# ---------------------------------------------------------------------------
# Result filters
# ---------------------------------------------------------------------------
# The names the results table offers as filter chips, mapped to the statuses each
# one selects. Filtering runs in SQL rather than over the rows the browser happens
# to have scrolled into memory: a filter that only searched loaded rows forced the
# user to scroll until a matching row appeared before its chip was even usable.
# "All" is deliberately absent — it means "no filter", not "every status".
RESULT_FILTERS: dict[str, frozenset[ReconciliationStatus]] = {
    "Matches": frozenset({ReconciliationStatus.MATCH}),
    "Issues": frozenset(s for s in ReconciliationStatus if s != ReconciliationStatus.MATCH),
    "Missing CU": frozenset({ReconciliationStatus.MISSING_CU_NUMBER}),
    "Missing SAP": frozenset({ReconciliationStatus.MISSING_IN_SAP}),
    "Missing KRA": frozenset({ReconciliationStatus.MISSING_IN_KRA}),
    "Amount": frozenset({ReconciliationStatus.AMOUNT_MISMATCH}),
    "VAT": frozenset({ReconciliationStatus.VAT_MISMATCH}),
    "CU": frozenset({ReconciliationStatus.CU_MISMATCH}),
    "PIN": frozenset({ReconciliationStatus.PIN_MISMATCH}),
    "Multiple": frozenset({
        ReconciliationStatus.MULTIPLE_MISMATCHES,
        ReconciliationStatus.DUPLICATE_SOURCE_KEY,
    }),
}

RESULT_FILTER_ALL = "All"


def result_filter_counts(status_counts: dict[ReconciliationStatus, int]) -> dict[str, int]:
    """Rolls per-status totals up into per-chip totals.

    Every chip is reported, zeros included, so the caller can decide whether to hide
    an empty one without having to know which statuses feed it.
    """
    counts = {
        name: sum(status_counts.get(status, 0) for status in statuses)
        for name, statuses in RESULT_FILTERS.items()
    }
    counts[RESULT_FILTER_ALL] = sum(status_counts.values())
    return counts


# ---------------------------------------------------------------------------
# Result sorting
# ---------------------------------------------------------------------------
# Columns the results table can sort by, mapped to the (SAP, KRA) column pair that
# backs each one. The table shows the SAP value and falls back to KRA, so sorting
# follows the same rule. Sorting runs in SQL for the same reason filtering does:
# ordering only the rows already scrolled into memory answers the wrong question.
RESULT_SORT_FIELDS: dict[str, tuple[str, str] | None] = {
    "pin": ("sap_pin", "kra_pin"),
    "invoice_number": ("sap_invoice_number", "kra_invoice_number"),
    "invoice_date": ("sap_invoice_date", "kra_invoice_date"),
    "base_amount": ("sap_base_amount", "kra_base_amount"),
    "vat_group": ("sap_vat_group", "kra_vat_group"),
    # Ordered by STATUS_ORDER priority rather than alphabetically, so the statuses
    # that need attention lead.
    "status": None,
}

RESULT_SORT_ORDERS = ("asc", "desc")
