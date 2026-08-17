"""End-to-end guard against false VAT mismatches, using real KRA export files.

Covers the production bug where invoices whose VAT was economically identical were
reported as "VAT Mismatch". Two independent causes:
  1. Divergent VAT label formats ("16" vs "16.00" vs "16%") keying different buckets.
  2. Company-specific SAP VAT codes never resolving, because the vat_mappings table
     was not consulted during reconciliation.
"""

from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.schemas.invoice import Invoice, InvoiceSource
from app.services import kra_service, reconciliation_service
from app.services.settings_service import SettingsService
from app.services.sap_mapper import map_sap_document_to_canonical_rows
from app.services.vat_normalizer import VatNormalizer
from app.domain.reconciliation_status import ReconciliationStatus

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "purchasesjunetechbiz"

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_vat_regression_db.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# A CU number that the real KRA export splits across the zero-rated (SEC_H) and
# exempt (SEC_I) sections. SAP reports it as a single line.
SPLIT_CU = "0040076780000806904"
SPLIT_ZERO_RATED = Decimal("2784.00")
SPLIT_EXEMPT = Decimal("129.00")


@pytest.fixture(name="db_session", scope="function")
def fixture_db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    SettingsService.seed_default_kra_section_profiles(db)
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def _parse(db, filename):
    path = DATA_DIR / filename
    assert path.exists(), f"Sample file not found at {path}"
    with open(path, "rb") as f:
        return kra_service.parse_kra_csv(UploadFile(filename=filename, file=f), db)


def _kra_rows_for_split_cu(db):
    rows = []
    for filename in ("SEC_H_WITH_VAT_PIN1.CSV", "SEC_I_WITH_VAT_PIN1.CSV"):
        response = _parse(db, filename)
        rows.extend(i for i in response.invoices if i.cu_number == SPLIT_CU)
    return rows


def test_real_kra_export_splits_one_cu_across_zero_rated_and_exempt(db_session):
    """Golden fixture: the real files really do split this CU across two rate sections."""
    rows = _kra_rows_for_split_cu(db_session)
    assert len(rows) == 2

    by_rate = {r.vat_group: r.base_amount for r in rows}
    assert by_rate == {"0": SPLIT_ZERO_RATED, "EXEMPT": SPLIT_EXEMPT}


def test_sap_with_unresolved_exempt_code_still_mismatches(db_session):
    """Without a mapping, SAP collapses exempt into "0" and the row cannot match.

    This is the residual, honest failure: SAP genuinely has not told us which portion
    was exempt. The engine must report it rather than silently pass.
    """
    kra_rows = _kra_rows_for_split_cu(db_session)
    sap_collapsed = Invoice(
        pin="P051123223G", partner_name="Naivas Limited", invoice_number="INV1",
        invoice_date=kra_rows[0].invoice_date, cu_number=SPLIT_CU, vat_group="0",
        base_amount=SPLIT_ZERO_RATED + SPLIT_EXEMPT, source=InvoiceSource.SAP,
    )

    summary, results = reconciliation_service.reconcile_invoices(
        [sap_collapsed], kra_rows, amount_tolerance=Decimal("10.00")
    )
    assert len(results) == 1
    # Totals agree, so this is purely a VAT allocation difference
    assert results[0].amount_match is True
    assert results[0].status == ReconciliationStatus.VAT_MISMATCH


def test_sap_with_mapped_exempt_code_reconciles_against_real_kra_rows(db_session):
    """With the company's exempt code mapped, SAP keeps the split and the row matches."""
    kra_rows = _kra_rows_for_split_cu(db_session)
    invoice_date = kra_rows[0].invoice_date

    # SAP reports two zero-rate lines distinguished only by a company-specific
    # VatGroup code; "ZX" is this company's exempt code.
    normalizer = VatNormalizer(input_map={"ZR": "0", "ZX": "EXEMPT"})
    raw_doc = {
        "DocNum": 1234,
        "FederalTaxID": "P051123223G",
        "CardName": "Naivas Limited",
        "DocDate": f"{invoice_date.isoformat()}T00:00:00Z",
        "U_CUINV": f"|{SPLIT_CU}",
        "DocumentLines": [
            {"VatGroup": "ZR", "TaxPercentagePerRow": 0, "LineTotal": float(SPLIT_ZERO_RATED)},
            {"VatGroup": "ZX", "TaxPercentagePerRow": 0, "LineTotal": float(SPLIT_EXEMPT)},
        ],
    }
    rows = map_sap_document_to_canonical_rows(
        raw_doc, "Invoice", "PurchaseInvoices",
        reconciliation_type="purchases", vat_normalizer_override=normalizer,
    )
    assert {r.vat_group for r in rows} == {"0", "EXEMPT"}

    sap_invoices = [
        Invoice(
            pin=r.pin, partner_name=r.partner_name, invoice_number=r.invoice_number,
            invoice_date=r.invoice_date, cu_number=r.cu_number, vat_group=r.vat_group,
            base_amount=r.base_amount, source=InvoiceSource.SAP,
        )
        for r in rows
    ]

    summary, results = reconciliation_service.reconcile_invoices(
        sap_invoices, kra_rows, amount_tolerance=Decimal("10.00")
    )
    assert len(results) == 1
    assert results[0].status == ReconciliationStatus.MATCH
    assert results[0].vat_match is True


def test_real_kra_rows_match_sap_regardless_of_rate_label_format(db_session):
    """A SAP line labelled "16.00" must match KRA's "16" on real parsed data."""
    response = _parse(db_session, "SEC_F_WITH_VAT_PIN1.CSV")
    kra_row = response.invoices[0]
    assert kra_row.vat_group == "16"

    sap_row = Invoice(
        pin=kra_row.pin, partner_name=kra_row.partner_name,
        invoice_number=kra_row.invoice_number, invoice_date=kra_row.invoice_date,
        cu_number=kra_row.cu_number, vat_group="16.00",
        base_amount=kra_row.base_amount, source=InvoiceSource.SAP,
    )

    summary, results = reconciliation_service.reconcile_invoices(
        [sap_row], [kra_row], amount_tolerance=Decimal("10.00")
    )
    assert results[0].status == ReconciliationStatus.MATCH
    assert results[0].vat_match is True


def test_no_difference_value_leaks_a_python_repr(db_session):
    """User-facing difference strings must never contain a raw dict/Decimal repr."""
    kra_rows = _kra_rows_for_split_cu(db_session)
    sap_collapsed = Invoice(
        pin="P051123223G", partner_name="Naivas Limited", invoice_number="INV1",
        invoice_date=kra_rows[0].invoice_date, cu_number=SPLIT_CU, vat_group="0",
        base_amount=SPLIT_ZERO_RATED + SPLIT_EXEMPT, source=InvoiceSource.SAP,
    )
    summary, results = reconciliation_service.reconcile_invoices(
        [sap_collapsed], kra_rows, amount_tolerance=Decimal("10.00")
    )

    for result in results:
        for diff in result.differences:
            for value in (diff.sap_value, diff.kra_value):
                assert "Decimal(" not in value
                assert "{" not in value
