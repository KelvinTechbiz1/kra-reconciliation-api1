import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest

from app.schemas.invoice import Invoice, InvoiceSource, ReconciliationType
from app.schemas.reconciliation import ReconciliationStatus
from app.services.sap_mapper import map_sap_document_to_canonical_rows
from app.services.normalization import normalize_invoice_data
from app.services.reconciliation_service import reconcile_invoices
from app.core.sap_client import SAPClient
from app.services import invoice_service


def test_missing_cu_number_and_partner_name_ingested():
    # Verify that raw document with missing U_CUINV (CU Number) and CardName (Customer name) is imported
    raw_doc = {
        "DocNum": 12345,
        "DocDate": "2026-03-02T00:00:00Z",
        # Missing CardName and U_CUINV
        "DocumentLines": [
            {"VatGroup": "O1", "LineTotal": 1000.00}
        ]
    }
    
    rows = map_sap_document_to_canonical_rows(raw_doc, "Invoice", "Invoices")
    assert len(rows) == 1
    assert rows[0].cu_number == ""
    assert rows[0].partner_name == ""
    assert rows[0].pin == ""  # PIN is also missing/empty

    # Test normalization function directly
    normalized = normalize_invoice_data(
        pin=None,
        partner_name=None,
        invoice_number="12345",
        invoice_date="2026-03-02",
        cu_number=None,
        vat_group="16.0",
        base_amount=1000.00,
        allow_negative=True
    )
    assert normalized["pin"] == ""
    assert normalized["partner_name"] == ""
    assert normalized["cu_number"] == ""


def test_cancelled_documents_excluded_in_query():
    # Verify that cancelled documents are excluded by checking the OData filter string
    client = SAPClient()
    client.base_url = "https://sap-test:50000/b1s/v1"
    client.username = "user"
    client.password = MagicMock()
    client.password.get_secret_value.return_value = "pass"
    client.company_db = "db"
    client.session_id = "test-session"
    client.cookies = {}
    client.session_expiry = datetime.datetime.now() + datetime.timedelta(minutes=10)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"value": []}

    with patch.object(client, "_execute_request_with_retry", return_value=mock_response) as mock_exec:
        # Consume the generator to trigger the request
        list(client.get_documents_pages("2026-03-01", "2026-03-02", "Invoices", page_size=500))
        
        # Verify that Cancelled eq 'tNO' is in the request filter query
        mock_exec.assert_called_once()
        args, kwargs = mock_exec.call_args
        params = kwargs.get("params", {})
        filter_str = params.get("$filter", "")
        assert "Cancelled eq 'tNO'" in filter_str


def test_draft_documents_excluded_from_endpoints():
    # Verify draft documents endpoint is never queried when fetching invoices
    with patch("app.core.sap_client.SAPClient.get_documents_pages", return_value=[]) as mock_get:
        invoice_service.get_invoices(
            from_date=datetime.date(2026, 3, 1),
            to_date=datetime.date(2026, 3, 30),
            reconciliation_type=ReconciliationType.SALES
        )
        
        # Check called endpoints: should only query Invoices and CreditNotes, never Drafts or DocumentDrafts
        called_endpoints = []
        for call in mock_get.mock_calls:
            args = call[1]
            kwargs = call[2]
            if "endpoint_name" in kwargs:
                called_endpoints.append(kwargs["endpoint_name"])
            elif len(args) >= 3:
                called_endpoints.append(args[2])
                
        assert "Invoices" in called_endpoints
        assert "CreditNotes" in called_endpoints
        assert "Drafts" not in called_endpoints
        assert "DocumentDrafts" not in called_endpoints


def test_amount_tolerance_matching():
    # Amount tolerance = 10.00 KES
    tolerance = Decimal("10.00")
    
    sap_inv = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=datetime.date(2026, 3, 1), cu_number="CU1", vat_group="16",
        base_amount=Decimal("100.00"), source=InvoiceSource.SAP
    )
    
    # 1. Difference of 9.99 KES -> Match
    kra_9_99 = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=datetime.date(2026, 3, 1), cu_number="CU1", vat_group="16",
        base_amount=Decimal("109.99"), source=InvoiceSource.KRA
    )
    summary_9_99, results_9_99 = reconcile_invoices([sap_inv], [kra_9_99], amount_tolerance=tolerance)
    assert summary_9_99.matches == 1
    assert results_9_99[0].amount_match is True
    assert len(results_9_99[0].differences) == 0

    # 2. Difference of exactly 10.00 KES -> Match
    kra_10_00 = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=datetime.date(2026, 3, 1), cu_number="CU1", vat_group="16",
        base_amount=Decimal("110.00"), source=InvoiceSource.KRA
    )
    summary_10_00, results_10_00 = reconcile_invoices([sap_inv], [kra_10_00], amount_tolerance=tolerance)
    assert summary_10_00.matches == 1
    assert results_10_00[0].amount_match is True
    assert len(results_10_00[0].differences) == 0

    # 3. Difference of 10.01 KES -> Amount Mismatch
    kra_10_01 = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=datetime.date(2026, 3, 1), cu_number="CU1", vat_group="16",
        base_amount=Decimal("110.01"), source=InvoiceSource.KRA
    )
    summary_10_01, results_10_01 = reconcile_invoices([sap_inv], [kra_10_01], amount_tolerance=tolerance)
    assert summary_10_01.matches == 0
    assert summary_10_01.mismatches == 1
    assert results_10_01[0].amount_match is False
    assert len(results_10_01[0].differences) == 1
    assert results_10_01[0].differences[0].field == "base_amount"


def test_empty_cu_numbers_do_not_match():
    # Verify that two records with empty CU numbers do not match in Phase 1 or 2, and receive MISSING_CU_NUMBER status.
    sap_inv = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=datetime.date(2026, 3, 1), cu_number="", vat_group="16",
        base_amount=Decimal("100.00"), source=InvoiceSource.SAP
    )
    kra_inv = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=datetime.date(2026, 3, 1), cu_number="", vat_group="16",
        base_amount=Decimal("100.00"), source=InvoiceSource.KRA
    )
    
    summary, results = reconcile_invoices([sap_inv], [kra_inv], amount_tolerance=Decimal("10.00"))
    # Should not pair them. They should receive MISSING_CU_NUMBER status.
    assert summary.matches == 0
    assert summary.missing_cu == 2
    assert len(results) == 2
    assert results[0].status == "Missing CU Number"
    assert results[1].status == "Missing CU Number"


def test_amount_tolerance_sign_check():
    # Verify that even if difference is <= tolerance, different signs do not match.
    sap_inv = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=datetime.date(2026, 3, 1), cu_number="CU1", vat_group="16",
        base_amount=Decimal("2.00"), source=InvoiceSource.SAP
    )
    kra_inv = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=datetime.date(2026, 3, 1), cu_number="CU1", vat_group="16",
        base_amount=Decimal("-2.00"), source=InvoiceSource.KRA
    )
    
    summary, results = reconcile_invoices([sap_inv], [kra_inv], amount_tolerance=Decimal("10.00"))
    assert summary.matches == 0
    assert summary.mismatches == 1
    assert results[0].amount_match is False


def test_missing_cu_number_cannot_participate_in_reconciliation():
    # Verify that a document with empty/missing CU number cannot participate in reconciliation
    sap_inv = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=datetime.date(2026, 3, 1), cu_number="", vat_group="16",
        base_amount=Decimal("100.00"), source=InvoiceSource.SAP
    )
    kra_inv = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=datetime.date(2026, 3, 1), cu_number="", vat_group="16",
        base_amount=Decimal("100.00"), source=InvoiceSource.KRA
    )
    
    summary, results = reconcile_invoices([sap_inv], [kra_inv])
    assert summary.matches == 0
    assert summary.missing_cu == 2
    for r in results:
        assert r.status == ReconciliationStatus.MISSING_CU_NUMBER


def test_cu_level_accumulation_and_missing_cu_preservation():
    # Multiple documents with empty/missing CU number are preserved and treated as missing CU numbers.
    sap_inv_empty1 = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=datetime.date(2026, 3, 1), cu_number="", vat_group="16",
        base_amount=Decimal("100.00"), source=InvoiceSource.SAP
    )
    sap_inv_empty2 = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV2",
        invoice_date=datetime.date(2026, 3, 1), cu_number="", vat_group="16",
        base_amount=Decimal("100.00"), source=InvoiceSource.SAP
    )
    
    # Non-empty CU keys: under CU-level normalization, multiple items with same CU are aggregated
    sap_inv_dup1 = Invoice(
        pin="P2", partner_name="Cust2", invoice_number="INV3",
        invoice_date=datetime.date(2026, 3, 1), cu_number="CU_DUP", vat_group="16",
        base_amount=Decimal("100.00"), source=InvoiceSource.SAP
    )
    sap_inv_dup2 = Invoice(
        pin="P2", partner_name="Cust2", invoice_number="INV4",
        invoice_date=datetime.date(2026, 3, 1), cu_number="CU_DUP", vat_group="16",
        base_amount=Decimal("150.00"), source=InvoiceSource.SAP
    )
    
    summary, results = reconcile_invoices([sap_inv_empty1, sap_inv_empty2, sap_inv_dup1, sap_inv_dup2], [])
    
    assert summary.missing_cu == 2
    assert summary.missing_in_kra == 1  # Accumulated CU_DUP (250.00) missing in KRA
    
    empty_results = [r for r in results if r.status == ReconciliationStatus.MISSING_CU_NUMBER]
    missing_kra_results = [r for r in results if r.status == ReconciliationStatus.MISSING_IN_KRA]
    
    assert len(empty_results) == 2
    assert len(missing_kra_results) == 1
    assert missing_kra_results[0].sap.base_amount == Decimal("250.00")


def test_unknown_vat_group_handling_graceful():
    # Verify that an unknown VAT group from SAP is handled gracefully:
    # it is passed through stripped and doesn't cause any crashes or exceptions.
    sap_inv = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=datetime.date(2026, 3, 1), cu_number="CU1", vat_group="UK_VAT_UNKNOWN",
        base_amount=Decimal("100.00"), source=InvoiceSource.SAP
    )
    kra_inv = Invoice(
        pin="P1", partner_name="Cust1", invoice_number="INV1",
        invoice_date=datetime.date(2026, 3, 1), cu_number="CU1", vat_group="16",
        base_amount=Decimal("100.00"), source=InvoiceSource.KRA
    )
    
    summary, results = reconcile_invoices([sap_inv], [kra_inv])
    # The different VAT groups ("UK_VAT_UNKNOWN" vs "16") will cause a VAT mismatch,
    # but the reconciliation process completes successfully without crashing.
    assert summary.matches == 0
    assert summary.mismatches == 1
    assert results[0].status == ReconciliationStatus.VAT_MISMATCH
    assert results[0].vat_match is False
    assert results[0].differences[0].sap_value == "UK_VAT_UNKNOWN"
    assert results[0].differences[0].kra_value == "16"
