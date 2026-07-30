from dataclasses import dataclass

from app.domain.reconciliation_status import ReconciliationStatus


@dataclass(frozen=True)
class SheetColumn:
    header: str
    attr: str
    is_amount: bool = False
    is_date: bool = False
    is_bool: bool = False
    is_cu: bool = False
    width: float = 20.0


@dataclass(frozen=True)
class SheetDefinition:
    title: str
    columns: tuple[SheetColumn, ...]
    statuses: frozenset[ReconciliationStatus] | None = None  # None = all rows
    is_compact: bool = False  # compact = no redundant SAP/KRA columns


@dataclass(frozen=True)
class WorkbookDefinition:
    filename: str
    sheets: tuple[SheetDefinition, ...]


# Reusable column sets
_CU_COL = SheetColumn(header="CU Number", attr="cu_number", is_cu=True, width=22)
_INVOICE_TYPE_COL = SheetColumn(header="Invoice Type", attr="invoice_type", width=14)
_AMOUNT_MATCH_COL = SheetColumn(header="Amount Match", attr="amount_match_symbol", width=14)
_VAT_MATCH_COL = SheetColumn(header="VAT Breakdown Match", attr="vat_match_symbol", width=18)
_REMARK_COL = SheetColumn(header="Remark", attr="remark", width=20)

_SAP_PIN = SheetColumn(header="SAP PIN", attr="sap_pin", width=18)
_SAP_PARTNER = SheetColumn(header="SAP Partner", attr="sap_partner_name", width=30)
_SAP_INV_NUM = SheetColumn(header="SAP Invoice #", attr="sap_invoice_number", width=18)
_SAP_DATE = SheetColumn(header="SAP Date", attr="sap_invoice_date", is_date=True, width=14)
_SAP_AMOUNT = SheetColumn(header="SAP Amount", attr="sap_base_amount", is_amount=True, width=18)
_SAP_VAT = SheetColumn(header="SAP VAT", attr="sap_vat_group", width=12)
_SAP_TAX_BREAKDOWN = SheetColumn(header="SAP Tax Breakdown", attr="sap_tax_breakdown", width=26)

_KRA_PIN = SheetColumn(header="KRA PIN", attr="kra_pin", width=18)
_KRA_PARTNER = SheetColumn(header="KRA Partner", attr="kra_partner_name", width=30)
_KRA_INV_NUM = SheetColumn(header="KRA Invoice #", attr="kra_invoice_number", width=18)
_KRA_DATE = SheetColumn(header="KRA Date", attr="kra_invoice_date", is_date=True, width=14)
_KRA_AMOUNT = SheetColumn(header="KRA Amount", attr="kra_base_amount", is_amount=True, width=18)
_KRA_VAT = SheetColumn(header="KRA VAT", attr="kra_vat_group", width=12)
_KRA_TAX_BREAKDOWN = SheetColumn(header="KRA Tax Breakdown", attr="kra_tax_breakdown", width=26)


NEEDS_REVIEW_STATUSES = frozenset({
    ReconciliationStatus.DUPLICATE_SOURCE_KEY,
    ReconciliationStatus.MISSING_CU_NUMBER,
    ReconciliationStatus.MISSING_IN_SAP,
    ReconciliationStatus.MISSING_IN_KRA,
    ReconciliationStatus.AMOUNT_MISMATCH,
    ReconciliationStatus.VAT_MISMATCH,
    ReconciliationStatus.MULTIPLE_MISMATCHES,
})

MATCH_STATUSES = frozenset({ReconciliationStatus.MATCH})

# ==============================================================================
# EXPORT FORMAT CONTRACT:
# Workbook names, worksheet names, and worksheet order are part of the public
# export format. They MUST NOT be changed without incrementing EXPORT_SCHEMA_VERSION.
# ==============================================================================
WORKBOOK_DEFINITIONS: tuple[WorkbookDefinition, ...] = (
    WorkbookDefinition(
        filename="02 Exceptions.xlsx",
        sheets=(
            SheetDefinition(
                title="Missing CU Number",
                columns=(
                    _CU_COL,
                    _SAP_PIN, _SAP_PARTNER, _SAP_INV_NUM, _SAP_DATE, _SAP_AMOUNT, _SAP_VAT, _SAP_TAX_BREAKDOWN,
                    _KRA_PIN, _KRA_PARTNER, _KRA_INV_NUM, _KRA_DATE, _KRA_AMOUNT, _KRA_VAT, _KRA_TAX_BREAKDOWN,
                ),
                statuses=frozenset({ReconciliationStatus.MISSING_CU_NUMBER}),
            ),
            SheetDefinition(
                title="Missing in SAP",
                columns=(
                    _CU_COL,
                    _KRA_PIN, _KRA_PARTNER, _KRA_INV_NUM, _KRA_DATE, _KRA_AMOUNT, _KRA_VAT, _KRA_TAX_BREAKDOWN,
                ),
                statuses=frozenset({ReconciliationStatus.MISSING_IN_SAP}),
                is_compact=True,
            ),
            SheetDefinition(
                title="Missing in KRA",
                columns=(
                    _CU_COL,
                    _SAP_PIN, _SAP_PARTNER, _SAP_INV_NUM, _SAP_DATE, _SAP_AMOUNT, _SAP_VAT, _SAP_TAX_BREAKDOWN,
                ),
                statuses=frozenset({ReconciliationStatus.MISSING_IN_KRA}),
                is_compact=True,
            ),
            SheetDefinition(
                title="Amount Mismatch",
                columns=(
                    _CU_COL,
                    _SAP_PIN, _SAP_PARTNER, _SAP_INV_NUM, _SAP_DATE, _SAP_AMOUNT, _SAP_VAT, _SAP_TAX_BREAKDOWN,
                    _KRA_PIN, _KRA_PARTNER, _KRA_INV_NUM, _KRA_DATE, _KRA_AMOUNT, _KRA_VAT, _KRA_TAX_BREAKDOWN,
                ),
                statuses=frozenset({ReconciliationStatus.AMOUNT_MISMATCH}),
            ),
            SheetDefinition(
                title="VAT Mismatch",
                columns=(
                    _CU_COL,
                    _SAP_PIN, _SAP_PARTNER, _SAP_INV_NUM, _SAP_DATE, _SAP_AMOUNT, _SAP_VAT, _SAP_TAX_BREAKDOWN,
                    _KRA_PIN, _KRA_PARTNER, _KRA_INV_NUM, _KRA_DATE, _KRA_AMOUNT, _KRA_VAT, _KRA_TAX_BREAKDOWN,
                ),
                statuses=frozenset({ReconciliationStatus.VAT_MISMATCH}),
            ),
            SheetDefinition(
                title="Duplicate CU",
                columns=(
                    _CU_COL,
                    _SAP_PIN, _SAP_PARTNER, _SAP_INV_NUM, _SAP_DATE, _SAP_AMOUNT, _SAP_VAT, _SAP_TAX_BREAKDOWN,
                    _KRA_PIN, _KRA_PARTNER, _KRA_INV_NUM, _KRA_DATE, _KRA_AMOUNT, _KRA_VAT, _KRA_TAX_BREAKDOWN,
                ),
                statuses=frozenset({ReconciliationStatus.DUPLICATE_SOURCE_KEY}),
            ),
            SheetDefinition(
                title="Multiple Issues",
                columns=(
                    _CU_COL,
                    _SAP_PIN, _SAP_PARTNER, _SAP_INV_NUM, _SAP_DATE, _SAP_AMOUNT, _SAP_VAT, _SAP_TAX_BREAKDOWN,
                    _KRA_PIN, _KRA_PARTNER, _KRA_INV_NUM, _KRA_DATE, _KRA_AMOUNT, _KRA_VAT, _KRA_TAX_BREAKDOWN,
                ),
                statuses=frozenset({ReconciliationStatus.MULTIPLE_MISMATCHES}),
            ),
        ),
    ),
    WorkbookDefinition(
        filename="03 Matches.xlsx",
        sheets=(
            SheetDefinition(
                title="Matches",
                columns=(
                    _CU_COL,
                    _SAP_PIN, _SAP_PARTNER, _SAP_INV_NUM, _SAP_DATE, _SAP_AMOUNT, _SAP_VAT, _SAP_TAX_BREAKDOWN,
                    _KRA_INV_NUM, _KRA_DATE, _KRA_AMOUNT, _KRA_VAT, _KRA_TAX_BREAKDOWN,
                ),
                statuses=frozenset({ReconciliationStatus.MATCH}),
                is_compact=True,
            ),
        ),
    ),
)
