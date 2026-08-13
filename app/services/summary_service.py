from app.domain.reconciliation_status import ReconciliationStatus
from app.reporting.export_row import ReconciliationExportRow
from app.schemas.reconciliation import MismatchStats, ReconciliationSummary


def build_summary(
    rows: list[ReconciliationExportRow],
    total_sap: int,
    total_kra: int,
) -> ReconciliationSummary:
    """Pure function. Shared by compare API, export, dashboard, and future callers."""
    matches = sum(1 for r in rows if r.status == ReconciliationStatus.MATCH)
    missing_in_sap = sum(1 for r in rows if r.status == ReconciliationStatus.MISSING_IN_SAP)
    missing_in_kra = sum(1 for r in rows if r.status == ReconciliationStatus.MISSING_IN_KRA)
    missing_cu = sum(1 for r in rows if r.status == ReconciliationStatus.MISSING_CU_NUMBER)
    mismatches = sum(1 for r in rows if r.status in (
        ReconciliationStatus.AMOUNT_MISMATCH,
        ReconciliationStatus.VAT_MISMATCH,
        ReconciliationStatus.CU_MISMATCH,
        ReconciliationStatus.PIN_MISMATCH,
        ReconciliationStatus.MULTIPLE_MISMATCHES,
    ))
    duplicate_cu = sum(1 for r in rows if r.status == ReconciliationStatus.DUPLICATE_SOURCE_KEY)

    # total_distinct_cus = total number of unique rows
    total_distinct_cus = len(rows)
    match_percentage = (matches / total_distinct_cus) * 100.0 if total_distinct_cus > 0 else 100.0
    completion_percentage = (matches / total_sap) * 100.0 if total_sap > 0 else 100.0

    mismatch_stats = MismatchStats(amount=0, vat=0, date=0)
    for r in rows:
        if r.status in (
            ReconciliationStatus.AMOUNT_MISMATCH,
            ReconciliationStatus.VAT_MISMATCH,
            ReconciliationStatus.MULTIPLE_MISMATCHES,
        ):
            if not r.amount_match:
                mismatch_stats.amount += 1
            if not r.vat_match:
                mismatch_stats.vat += 1

    return ReconciliationSummary(
        total_sap=total_sap,
        total_kra=total_kra,
        matches=matches,
        missing_in_sap=missing_in_sap,
        missing_in_kra=missing_in_kra,
        missing_cu=missing_cu,
        mismatches=mismatches,
        duplicate_cu=duplicate_cu,
        match_percentage=match_percentage,
        completion_percentage=completion_percentage,
        total_reconciled_rows=total_distinct_cus,
        mismatch_stats=mismatch_stats,
    )
