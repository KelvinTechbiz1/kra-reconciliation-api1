"""Guards for eTIMS CU numbers arriving as "<device serial>/<number>".

The KRA iTax portal renders a CU invoice number two ways:
  - TIMS:  |0040073470000188183
  - eTIMS: |KRACU0300007538/169681

SAP stores only the number itself, so every eTIMS row used to either miss its partner
entirely or pair through the amount/partner fallback and report CU Mismatch. In the real
August export used here that is *every* sales row (2,546 of 2,546 in the two SEC_B files).

The prefix is now dropped on both sides, so the two key the same reconciliation group.
"""

from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.domain.normalized_invoice import normalize_and_group_invoices
from app.domain.reconciliation_status import ReconciliationStatus
from app.schemas.invoice import Invoice, InvoiceSource
from app.services import kra_service, reconciliation_service
from app.services.normalization import normalize_invoice_data
from app.services.sap_mapper import extract_cu_number
from app.services.settings_service import SettingsService
from app.utils.cu_utils import canonical_cu_number

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "etims-cu-prefix"

# The August export is real client tax data and .gitignore excludes "*.CSV", so it is
# present locally but not on a clean checkout. The unit-level guards above cover the
# behaviour everywhere; these three add the end-to-end proof where the files exist.
needs_export = pytest.mark.skipif(
    not DATA_DIR.is_dir() or not any(DATA_DIR.glob("*.CSV")),
    reason=f"real KRA export not present at {DATA_DIR}",
)

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_etims_cu_db.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# A real eTIMS purchase from SEC_G_WITH_VAT_PIN1.CSV row 2.
ETIMS_RAW_CU = "|KRACU0300007538/169681"
ETIMS_CU = "169681"
ETIMS_PIN = "P051203730N"
ETIMS_AMOUNT = Decimal("3703.70")


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


# --- canonical_cu_number ----------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        # The eTIMS form: everything before the final "/" is the device, not the invoice.
        ("|KRACU0300007538/169681", "169681"),
        ("KRACU0400003361/11207", "11207"),
        ("KRACU0100043637/433", "433"),
        # The TIMS form is already the bare number.
        ("|0040073470000188183", "0040073470000188183"),
        ("0040076780000806904", "0040076780000806904"),
        # Import declarations carry a letter-bearing reference and no device prefix.
        ("|26MBAIM404780158", "26MBAIM404780158"),
        # Whitespace and the SAP UDF pipe.
        ("  |  KRACU0300007538/169681  ", "169681"),
        ("|| 12345 ", "12345"),
        # Nothing to key on.
        ("", ""),
        ("   ", ""),
        (None, ""),
        ("|", ""),
    ],
)
def test_canonical_cu_number(raw, expected):
    assert canonical_cu_number(raw) == expected


def test_trailing_slash_keeps_the_prefix_rather_than_emptying_the_cu():
    """A dangling separator must not turn a row into a "Missing CU Number" exception."""
    assert canonical_cu_number("KRACU0300007538/") == "KRACU0300007538"


def test_case_is_preserved():
    """CU numbers are compared verbatim elsewhere; canonicalizing must not re-case them."""
    assert canonical_cu_number("|26mbaim404780158") == "26mbaim404780158"


# --- the choke points -------------------------------------------------------------


def test_invoice_property_strips_the_device_prefix():
    inv = Invoice(
        pin=ETIMS_PIN, partner_name="NIXOMB LIMITED", invoice_number="INV1",
        cu_number=ETIMS_RAW_CU, vat_group="16", base_amount=ETIMS_AMOUNT,
        source=InvoiceSource.KRA,
    )
    assert inv.normalized_cu_number == ETIMS_CU


def test_ingest_normalization_stores_the_stripped_cu():
    normalized = normalize_invoice_data(
        pin=ETIMS_PIN, partner_name="NIXOMB LIMITED", invoice_number="INV1",
        invoice_date="26/08/2026", cu_number=ETIMS_RAW_CU, vat_group="16",
        base_amount=ETIMS_AMOUNT,
    )
    assert normalized["cu_number"] == ETIMS_CU


def test_sap_side_is_stripped_identically():
    """Applied to both sides, so a prefixed SAP value still meets a prefixed KRA one."""
    assert extract_cu_number({"U_CUINV": ETIMS_RAW_CU}, "U_CUINV") == ETIMS_CU
    assert extract_cu_number({"U_CUINV": "|169681"}, "U_CUINV") == ETIMS_CU


def test_rows_from_one_device_no_longer_collapse_into_one_group():
    """Grouping keys on the CU, so the sequence must survive — only the device goes."""
    rows = [
        Invoice(pin=ETIMS_PIN, partner_name="A", invoice_number=str(n),
                cu_number=f"|KRACU0400003361/{n}", vat_group="16",
                base_amount=Decimal("100.00"), source=InvoiceSource.KRA)
        for n in (11207, 11215, 11125)
    ]
    grouped, missing = normalize_and_group_invoices(rows)
    assert missing == []
    assert sorted(g.cu_number for g in grouped) == ["11125", "11207", "11215"]


# --- reconciliation ---------------------------------------------------------------


def test_prefixed_kra_row_matches_bare_sap_row():
    """The reported bug: identical invoices reported as CU Mismatch."""
    common = dict(
        pin=ETIMS_PIN, partner_name="NIXOMB LIMITED", invoice_number="INV1",
        vat_group="16", base_amount=ETIMS_AMOUNT,
    )
    sap = Invoice(cu_number=ETIMS_CU, source=InvoiceSource.SAP, **common)
    kra = Invoice(cu_number=ETIMS_RAW_CU, source=InvoiceSource.KRA, **common)

    summary, results = reconciliation_service.reconcile_invoices(
        [sap], [kra], amount_tolerance=Decimal("0.01")
    )
    assert len(results) == 1
    assert results[0].status == ReconciliationStatus.MATCH
    assert results[0].cu_number == ETIMS_CU
    assert summary.matches == 1


def test_a_genuine_cu_difference_is_still_reported():
    """Stripping must not make every CU look alike."""
    common = dict(
        pin=ETIMS_PIN, partner_name="NIXOMB LIMITED", invoice_number="INV1",
        vat_group="16", base_amount=ETIMS_AMOUNT,
    )
    sap = Invoice(cu_number="|KRACU0300007538/169681", source=InvoiceSource.SAP, **common)
    kra = Invoice(cu_number="|KRACU0300007538/999999", source=InvoiceSource.KRA, **common)

    summary, results = reconciliation_service.reconcile_invoices(
        [sap], [kra], amount_tolerance=Decimal("0.01")
    )
    assert len(results) == 1
    # Paired by the amount/partner fallback, then reported as differing.
    assert results[0].status == ReconciliationStatus.CU_MISMATCH


# --- against the real August export -----------------------------------------------


@needs_export
def test_real_purchase_export_yields_a_bare_cu(db_session):
    response = _parse(db_session, "SEC_G_WITH_VAT_PIN1.CSV")
    matches = [i for i in response.invoices if i.cu_number == ETIMS_CU]
    assert len(matches) == 1
    assert matches[0].pin == ETIMS_PIN
    assert matches[0].base_amount == ETIMS_AMOUNT


@needs_export
def test_no_parsed_cu_still_carries_a_device_prefix(db_session):
    """Every section, not just the one under test."""
    for filename in sorted(p.name for p in DATA_DIR.glob("*.CSV")):
        response = _parse(db_session, filename)
        assert response.invoices, f"{filename} parsed no rows"
        offenders = [i.cu_number for i in response.invoices if "/" in i.cu_number]
        assert not offenders, f"{filename}: {offenders[:3]}"


@needs_export
def test_whole_sales_export_reconciles_against_bare_sap_cus(db_session):
    """The headline case: before this fix none of these 2,546 rows could pair."""
    kra_rows = []
    for filename in ("SEC_B_WITH_VAT_PIN1.CSV", "SEC_B_WITHOUT_PIN_AND_NON-VAT_PIN1.CSV"):
        kra_rows.extend(_parse(db_session, filename).invoices)
    assert len(kra_rows) > 2000

    # SAP holds the same invoices without the device prefix.
    sap_rows = [
        Invoice(
            pin=r.pin, partner_name=r.partner_name, invoice_number=r.invoice_number,
            invoice_date=r.invoice_date, cu_number=r.cu_number, vat_group=r.vat_group,
            base_amount=r.base_amount, source=InvoiceSource.SAP,
        )
        for r in kra_rows
    ]

    summary, results = reconciliation_service.reconcile_invoices(
        sap_rows, kra_rows, amount_tolerance=Decimal("0.01")
    )
    assert summary.missing_in_sap == 0
    assert summary.missing_in_kra == 0
    assert all(r.status == ReconciliationStatus.MATCH for r in results)
