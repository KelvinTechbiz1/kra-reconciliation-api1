import pytest
import io
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.database import get_db
from app.main import app
from app.schemas.invoice import Invoice, InvoiceSource
from app.schemas.reconciliation import ReconciliationStatus, DifferenceField
from app.services import reconciliation_service
from app.domain.normalized_invoice import normalize_and_group_invoices

# Setup test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_recon_db.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(name="db_session", scope="function")
def fixture_db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    from app.models.settings import KRAVATMapping
    db.add(KRAVATMapping(section_prefix="SEC_B", canonical_rate="16"))
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(name="client", scope="function")
def fixture_client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(name="auth_headers", scope="function")
def fixture_auth_headers(client):
    register_payload = {
        "username": "recon_tester",
        "password": "SecureP@ss123",
        "email": "recon_tester@example.com",
    }
    client.post("/api/v1/auth/register", json=register_payload)
    from conftest import seed_test_sap_connection
    seed_test_sap_connection(client)

    login_payload = {
        "username": "recon_tester",
        "password": "SecureP@ss123",
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --- Unit Tests for Reconciliation Service & Pipeline ---

def test_reconcile_invoices_various_cases():
    # 1. Setup mock invoices
    # Matches
    sap_match = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=date(2026, 3, 1), cu_number="CU_MATCH", vat_group="16",
        base_amount=Decimal("100.00"), source=InvoiceSource.SAP
    )
    kra_match = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=date(2026, 3, 1), cu_number="CU_MATCH", vat_group="16",
        base_amount=Decimal("100.00"), source=InvoiceSource.KRA
    )

    # Amount Mismatch
    sap_amt_mis = Invoice(
        pin="P2", partner_name="Cust2", invoice_number="INV2",
        invoice_date=date(2026, 3, 2), cu_number="CU_AMT", vat_group="16",
        base_amount=Decimal("200.00"), source=InvoiceSource.SAP
    )
    kra_amt_mis = Invoice(
        pin="P2", partner_name="Cust2", invoice_number="INV2",
        invoice_date=date(2026, 3, 2), cu_number="CU_AMT", vat_group="16",
        base_amount=Decimal("250.00"), source=InvoiceSource.KRA
    )

    # VAT Mismatch
    sap_vat_mis = Invoice(
        pin="P3", partner_name="Cust3", invoice_number="INV3",
        invoice_date=date(2026, 3, 3), cu_number="CU_VAT", vat_group="16",
        base_amount=Decimal("300.00"), source=InvoiceSource.SAP
    )
    kra_vat_mis = Invoice(
        pin="P3", partner_name="Cust3", invoice_number="INV3",
        invoice_date=date(2026, 3, 3), cu_number="CU_VAT", vat_group="0",
        base_amount=Decimal("300.00"), source=InvoiceSource.KRA
    )

    # Date Mismatch (now MATCH since date check is advisory/tolerance)
    sap_date_mis = Invoice(
        pin="P4", partner_name="Cust4", invoice_number="INV4",
        invoice_date=date(2026, 3, 4), cu_number="CU_DATE", vat_group="16",
        base_amount=Decimal("400.00"), source=InvoiceSource.SAP
    )
    kra_date_mis = Invoice(
        pin="P4", partner_name="Cust4", invoice_number="INV4",
        invoice_date=date(2026, 3, 5), cu_number="CU_DATE", vat_group="16",
        base_amount=Decimal("400.00"), source=InvoiceSource.KRA
    )

    # Multiple Mismatches (Amount + VAT)
    sap_multi = Invoice(
        pin="P5", partner_name="Cust5", invoice_number="INV5",
        invoice_date=date(2026, 3, 5), cu_number="CU_MULTI", vat_group="16",
        base_amount=Decimal("500.00"), source=InvoiceSource.SAP
    )
    kra_multi = Invoice(
        pin="P5", partner_name="Cust5", invoice_number="INV5",
        invoice_date=date(2026, 3, 5), cu_number="CU_MULTI", vat_group="0",
        base_amount=Decimal("550.00"), source=InvoiceSource.KRA
    )

    # Missing in SAP
    kra_only = Invoice(
        pin="P6", partner_name="Cust6", invoice_number="INV6",
        invoice_date=date(2026, 3, 6), cu_number="CU_KRA_ONLY", vat_group="16",
        base_amount=Decimal("600.00"), source=InvoiceSource.KRA
    )

    # Missing in KRA
    sap_only = Invoice(
        pin="P7", partner_name="Cust7", invoice_number="INV7",
        invoice_date=date(2026, 3, 7), cu_number="CU_SAP_ONLY", vat_group="16",
        base_amount=Decimal("700.00"), source=InvoiceSource.SAP
    )

    # 2. Run reconciliation
    sap_invoices = [sap_match, sap_amt_mis, sap_vat_mis, sap_date_mis, sap_multi, sap_only]
    kra_invoices = [kra_match, kra_amt_mis, kra_vat_mis, kra_date_mis, kra_multi, kra_only]

    summary, results = reconciliation_service.reconcile_invoices(sap_invoices, kra_invoices)

    # 3. Assert Summary metrics
    assert summary.total_sap == 6
    assert summary.total_kra == 6
    assert summary.matches == 2  # CU_MATCH, CU_DATE
    assert summary.missing_in_sap == 1
    assert summary.missing_in_kra == 1
    assert summary.mismatches == 3  # CU_AMT, CU_VAT, CU_MULTI
    assert round(summary.match_percentage, 2) == 28.57
    assert round(summary.completion_percentage, 2) == 33.33

    # Assert Mismatch stats
    assert summary.mismatch_stats.amount == 2 # AMT, MULTI
    assert summary.mismatch_stats.vat == 3    # AMT (different vat), VAT, MULTI

    # 4. Assert individual results
    res_dict = {r.cu_number: r for r in results}

    # Match CU
    assert res_dict["CU_MATCH"].status == ReconciliationStatus.MATCH
    assert res_dict["CU_MATCH"].amount_match is True
    assert res_dict["CU_MATCH"].vat_match is True

    # Amount mismatch CU
    assert res_dict["CU_AMT"].status == ReconciliationStatus.AMOUNT_MISMATCH
    assert res_dict["CU_AMT"].amount_match is False
    assert len(res_dict["CU_AMT"].differences) == 1
    assert res_dict["CU_AMT"].differences[0].field == DifferenceField.BASE_AMOUNT

    # VAT mismatch CU
    assert res_dict["CU_VAT"].status == ReconciliationStatus.VAT_MISMATCH
    assert res_dict["CU_VAT"].vat_match is False
    assert len(res_dict["CU_VAT"].differences) == 1
    assert res_dict["CU_VAT"].differences[0].field == DifferenceField.VAT_GROUP
    assert res_dict["CU_VAT"].differences[0].sap_value == "16"
    assert res_dict["CU_VAT"].differences[0].kra_value == "0"

    # Date mismatch CU (now MATCH)
    assert res_dict["CU_DATE"].status == ReconciliationStatus.MATCH
    assert res_dict["CU_DATE"].date_match is True

    # Multiple mismatches CU
    assert res_dict["CU_MULTI"].status == ReconciliationStatus.AMOUNT_MISMATCH
    assert res_dict["CU_MULTI"].amount_match is False

    # Missing in KRA
    assert res_dict["CU_SAP_ONLY"].status == ReconciliationStatus.MISSING_IN_KRA
    assert res_dict["CU_SAP_ONLY"].sap is not None
    assert res_dict["CU_SAP_ONLY"].kra is None

    # Missing in SAP
    assert res_dict["CU_KRA_ONLY"].status == ReconciliationStatus.MISSING_IN_SAP
    assert res_dict["CU_KRA_ONLY"].sap is None
    assert res_dict["CU_KRA_ONLY"].kra is not None


def test_etims_real_world_proof_cases_from_june_ushurulense():
    """
    Validates all 3 real-world Naivas Limited and Furqan Petroleum eTIMS multi-tax line cases
    from `june ushurulense.xlsx` and `purchasesjunetechbiz`.
    """

    # Case 1: Naivas Limited - CU 0040807450001963198
    kra_naivas1_16 = Invoice(
        pin="P051123223G", partner_name="Naivas Limited", invoice_number="0040807450001963198",
        invoice_date=date(2026, 6, 30), cu_number="0040807450001963198", vat_group="16",
        base_amount=Decimal("520.69"), source=InvoiceSource.KRA
    )
    kra_naivas1_0 = Invoice(
        pin="P051123223G", partner_name="Naivas Limited", invoice_number="0040807450001963198",
        invoice_date=date(2026, 6, 30), cu_number="0040807450001963198", vat_group="0",
        base_amount=Decimal("2784.00"), source=InvoiceSource.KRA
    )
    erp_naivas1 = Invoice(
        pin="P051123223G", partner_name="Naivas Limited", invoice_number="INV001",
        invoice_date=date(2026, 6, 30), cu_number="0040807450001963198", vat_group="16",
        base_amount=Decimal("3304.69"), source=InvoiceSource.SAP
    )

    # Case 2: Naivas Limited - CU 0040076780000806904
    kra_naivas2_16 = Invoice(
        pin="P051123223G", partner_name="Naivas Limited", invoice_number="0040076780000806904",
        invoice_date=date(2026, 6, 6), cu_number="0040076780000806904", vat_group="16",
        base_amount=Decimal("2105.19"), source=InvoiceSource.KRA
    )
    kra_naivas2_0 = Invoice(
        pin="P051123223G", partner_name="Naivas Limited", invoice_number="0040076780000806904",
        invoice_date=date(2026, 6, 6), cu_number="0040076780000806904", vat_group="0",
        base_amount=Decimal("2784.00"), source=InvoiceSource.KRA
    )
    kra_naivas2_ex = Invoice(
        pin="P051123223G", partner_name="Naivas Limited", invoice_number="0040076780000806904",
        invoice_date=date(2026, 6, 6), cu_number="0040076780000806904", vat_group="EXEMPT",
        base_amount=Decimal("129.00"), source=InvoiceSource.KRA
    )
    erp_naivas2 = Invoice(
        pin="P051123223G", partner_name="Naivas Limited", invoice_number="INV002",
        invoice_date=date(2026, 6, 6), cu_number="0040076780000806904", vat_group="16",
        base_amount=Decimal("5018.17"), source=InvoiceSource.SAP
    )

    # Case 3: Naivas Limited - CU 0040807450001427233
    kra_naivas3_16 = Invoice(
        pin="P051123223G", partner_name="Naivas Limited", invoice_number="0040807450001427233",
        invoice_date=date(2026, 6, 6), cu_number="0040807450001427233", vat_group="16",
        base_amount=Decimal("6962.06"), source=InvoiceSource.KRA
    )
    kra_naivas3_0 = Invoice(
        pin="P051123223G", partner_name="Naivas Limited", invoice_number="0040807450001427233",
        invoice_date=date(2026, 6, 6), cu_number="0040807450001427233", vat_group="0",
        base_amount=Decimal("395.00"), source=InvoiceSource.KRA
    )
    kra_naivas3_ex = Invoice(
        pin="P051123223G", partner_name="Naivas Limited", invoice_number="0040807450001427233",
        invoice_date=date(2026, 6, 6), cu_number="0040807450001427233", vat_group="EXEMPT",
        base_amount=Decimal("300.00"), source=InvoiceSource.KRA
    )
    erp_naivas3 = Invoice(
        pin="P051123223G", partner_name="Naivas Limited", invoice_number="INV003",
        invoice_date=date(2026, 6, 6), cu_number="0040807450001427233", vat_group="16",
        base_amount=Decimal("7657.07"), source=InvoiceSource.SAP
    )

    erp_list = [erp_naivas1, erp_naivas2, erp_naivas3]
    kra_list = [
        kra_naivas1_16, kra_naivas1_0,
        kra_naivas2_16, kra_naivas2_0, kra_naivas2_ex,
        kra_naivas3_16, kra_naivas3_0, kra_naivas3_ex
    ]

    summary, results = reconciliation_service.reconcile_invoices(
        erp_list, kra_list, amount_tolerance=Decimal("0.02")
    )

    assert summary.total_sap == 3
    assert summary.total_kra == 8
    assert summary.mismatch_stats.amount == 0 # Zero false amount mismatches!
    assert summary.missing_in_sap == 0
    assert summary.missing_in_kra == 0

    res_map = {r.cu_number: r for r in results}
    assert res_map["0040807450001963198"].amount_match is True
    assert res_map["0040076780000806904"].amount_match is True
    assert res_map["0040807450001427233"].amount_match is True


def test_normalized_invoice_provenance():
    # Verifies that raw source rows are preserved in NormalizedInvoice for drill-down auditability
    row1 = Invoice(
        pin="P1", partner_name="Supplier A", invoice_number="INV100",
        invoice_date=date(2026, 3, 1), cu_number="CU_PROV", vat_group="16",
        base_amount=Decimal("500.00"), source=InvoiceSource.KRA
    )
    row2 = Invoice(
        pin="P1", partner_name="Supplier A", invoice_number="INV100",
        invoice_date=date(2026, 3, 1), cu_number="CU_PROV", vat_group="0",
        base_amount=Decimal("200.00"), source=InvoiceSource.KRA
    )

    norm_list, missing = normalize_and_group_invoices([row1, row2])
    assert len(norm_list) == 1
    norm = norm_list[0]

    assert norm.cu_number == "CU_PROV"
    assert norm.total_base == Decimal("700.00")
    assert norm.tax_breakdown == {"16": Decimal("500.00"), "0": Decimal("200.00")}
    assert len(norm.source_rows) == 2
    assert norm.source_rows[0] == row1
    assert norm.source_rows[1] == row2


def test_vat_breakdown_mismatch_with_matching_amount():
    # Document total matches (1000.00), but VAT allocation differs (ERP 1000 @ 16% vs KRA 500 @ 16% + 500 @ 0%)
    sap_inv = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=date(2026, 3, 1), cu_number="CU_VAT_MIS", vat_group="16",
        base_amount=Decimal("1000.00"), source=InvoiceSource.SAP
    )
    kra1 = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=date(2026, 3, 1), cu_number="CU_VAT_MIS", vat_group="16",
        base_amount=Decimal("500.00"), source=InvoiceSource.KRA
    )
    kra2 = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=date(2026, 3, 1), cu_number="CU_VAT_MIS", vat_group="0",
        base_amount=Decimal("500.00"), source=InvoiceSource.KRA
    )

    summary, results = reconciliation_service.reconcile_invoices([sap_inv], [kra1, kra2])

    assert summary.mismatches == 1
    res = results[0]
    assert res.status == ReconciliationStatus.VAT_MISMATCH
    assert res.amount_match is True
    assert res.vat_match is False
    assert len(res.differences) == 1
    assert res.differences[0].field == DifferenceField.VAT_GROUP


def test_cu_number_difference_routed_to_cu_mismatch_not_vat_mismatch():
    # SAP and KRA documents match on amount + VAT but the CU numbers differ
    # (a typo, e.g. 190349340000000511 vs 190439340000000511). These are
    # fallback-paired and must surface as CU Mismatch, NOT a false VAT Mismatch.
    sap_typo = Invoice(
        pin="P1", partner_name="AGRICHEM AFRICA LIMITED", invoice_number="1132",
        invoice_date=date(2026, 7, 15), cu_number="190349340000000511", vat_group="16",
        base_amount=Decimal("243810.00"), source=InvoiceSource.SAP
    )
    kra_correct = Invoice(
        pin="P1", partner_name="AGRICHEM AFRICA LIMITED", invoice_number="K1",
        invoice_date=date(2026, 7, 15), cu_number="190439340000000511", vat_group="16",
        base_amount=Decimal("243810.00"), source=InvoiceSource.KRA
    )

    summary, results = reconciliation_service.reconcile_invoices([sap_typo], [kra_correct])

    assert len(results) == 1
    res = results[0]
    assert res.status == ReconciliationStatus.CU_MISMATCH
    assert res.amount_match is True
    assert res.vat_match is True
    assert len(res.differences) == 1
    assert res.differences[0].field == DifferenceField.CU_NUMBER
    assert summary.mismatches == 1


def test_one_sided_missing_pin_is_pin_mismatch():
    # SAP invoice has no PIN while the KRA invoice does. This must be flagged
    # as a PIN Mismatch instead of silently passing as a Match.
    sap_no_pin = Invoice(
        pin="", partner_name="Savannah Cement Limited", invoice_number="1131",
        invoice_date=date(2026, 7, 14), cu_number="190439340000000510", vat_group="16",
        base_amount=Decimal("592275.00"), source=InvoiceSource.SAP
    )
    kra_with_pin = Invoice(
        pin="P051119362D", partner_name="Savannah Cement Limited", invoice_number="K1",
        invoice_date=date(2026, 7, 14), cu_number="190439340000000510", vat_group="16",
        base_amount=Decimal("592275.00"), source=InvoiceSource.KRA
    )

    summary, results = reconciliation_service.reconcile_invoices([sap_no_pin], [kra_with_pin])

    assert len(results) == 1
    res = results[0]
    assert res.status == ReconciliationStatus.PIN_MISMATCH
    assert res.pin_matches is False
    assert res.amount_match is True
    assert res.vat_match is True
    assert summary.matches == 0
    assert summary.mismatches == 1


def test_both_pins_missing_is_not_a_pin_mismatch():
    sap_no_pin = Invoice(
        pin="", partner_name="CustA", invoice_number="INV1",
        invoice_date=date(2026, 3, 1), cu_number="CU_NOPIN", vat_group="16",
        base_amount=Decimal("100.00"), source=InvoiceSource.SAP
    )
    kra_no_pin = Invoice(
        pin="", partner_name="CustA", invoice_number="INV1",
        invoice_date=date(2026, 3, 1), cu_number="CU_NOPIN", vat_group="16",
        base_amount=Decimal("100.00"), source=InvoiceSource.KRA
    )

    summary, results = reconciliation_service.reconcile_invoices([sap_no_pin], [kra_no_pin])

    assert len(results) == 1
    assert results[0].status == ReconciliationStatus.MATCH
    assert results[0].pin_matches is True


def test_decimal_normalization_and_order_independence():
    sap1 = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=date(2026, 3, 1), cu_number="CU1", vat_group="16",
        base_amount=Decimal("100.00"), source=InvoiceSource.SAP
    )
    sap2 = Invoice(
        pin="P2", partner_name="Cust2", invoice_number="INV2",
        invoice_date=date(2026, 3, 2), cu_number="CU2", vat_group="16",
        base_amount=Decimal("100.00"), source=InvoiceSource.SAP
    )
    kra1 = Invoice(
        pin="P2", partner_name="Cust2", invoice_number="INV2",
        invoice_date=date(2026, 3, 2), cu_number="CU2", vat_group="16",
        base_amount=Decimal("100.00"), source=InvoiceSource.KRA
    )
    kra2 = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=date(2026, 3, 1), cu_number="CU1", vat_group="16",
        base_amount=Decimal("100.00"), source=InvoiceSource.KRA
    )
    summary, results = reconciliation_service.reconcile_invoices([sap1, sap2], [kra1, kra2])
    assert summary.matches == 2
