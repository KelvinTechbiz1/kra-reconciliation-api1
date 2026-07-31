import datetime
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch
import httpx

from app.core.config import get_settings, BaseAmountPolicy
from app.core.exceptions import SAPConfigurationError, SAPConnectionError, SAPQueryError
from app.core.sap_client import SAPClient
from app.services import invoice_service
from app.services.sap_mapper import map_sap_document_to_canonical_rows, parse_sap_date


def test_parse_sap_date():
    assert parse_sap_date("2026-03-02T00:00:00Z") == datetime.date(2026, 3, 2)
    assert parse_sap_date("2026-03-02 12:00:00") == datetime.date(2026, 3, 2)
    assert parse_sap_date("2026-03-02") == datetime.date(2026, 3, 2)
    assert parse_sap_date(datetime.date(2026, 3, 2)) == datetime.date(2026, 3, 2)
    
    with pytest.raises(ValueError):
        parse_sap_date("invalid-date-format")


def test_sap_client_login_success():
    client = SAPClient()
    # Mock settings
    client.base_url = "https://sap-test:50000/b1s/v1"
    client.username = "test-user"
    client.password = "test-pass"
    client.company_db = "test-db"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "SessionId": "test-session-12345",
        "SessionTimeout": 30
    }
    mock_response.cookies = {"B1SESSION": "test-session-12345", "ROUTEID": "node1"}

    with patch.object(client.client, "post", return_value=mock_response) as mock_post:
        client.login()
        mock_post.assert_called_once_with(
            "https://sap-test:50000/b1s/v1/Login",
            json={"CompanyDB": "test-db", "UserName": "test-user", "Password": "test-pass"}
        )
        assert client.session_id == "test-session-12345"
        assert client.cookies["B1SESSION"] == "test-session-12345"
        assert client.cookies["ROUTEID"] == "node1"
        assert client.session_expiry > datetime.datetime.now()


def test_sap_client_login_failure():
    client = SAPClient()
    client.base_url = "https://sap-test:50000/b1s/v1"

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with patch.object(client.client, "post", return_value=mock_response):
        with pytest.raises(SAPConnectionError, match="SAP Login failed"):
            client.login()


def test_sap_client_get_invoices_pagination():
    client = SAPClient()
    client.base_url = "https://sap-test:50000/b1s/v1"
    client.session_id = "active-session"
    client.cookies = {"B1SESSION": "active-session"}
    client.session_expiry = datetime.datetime.now() + datetime.timedelta(minutes=10)

    # Page 1 response (with nextLink)
    page1_response = MagicMock()
    page1_response.status_code = 200
    page1_response.json.return_value = {
        "value": [{"DocNum": 100, "DocDate": "2026-03-01"}],
        "odata.nextLink": "Invoices?$skip=1"
    }

    # Page 2 response (no nextLink)
    page2_response = MagicMock()
    page2_response.status_code = 200
    page2_response.json.return_value = {
        "value": [{"DocNum": 101, "DocDate": "2026-03-02"}]
    }

    def mock_request(method, url, params=None, cookies=None, headers=None):
        if url == "https://sap-test:50000/b1s/v1/Invoices":
            return page1_response
        elif url == "https://sap-test:50000/b1s/v1/Invoices?$skip=1":
            return page2_response
        raise ValueError(f"Unexpected URL: {url}")

    with patch.object(client, "_execute_request_with_retry", side_effect=mock_request) as mock_exec:
        pages = list(client.get_documents_pages("2026-03-01", "2026-03-02", "Invoices", page_size=500))
        
        assert len(pages) == 2
        assert pages[0][0]["DocNum"] == 100
        assert pages[1][0]["DocNum"] == 101
        assert mock_exec.call_count == 2


def test_sap_mapper_line_aggregation():
    # Test that 1 SAP invoice with 3 lines of same VAT group aggregates to exactly 1 record
    raw_invoice = {
        "DocNum": 764,
        "CardName": "Welding Alloys Ltd",
        "FederalTaxID": "P000609554G",
        "DocDate": "2026-03-02T00:00:00Z",
        "U_CUINV": "0190439340000000134",
        "DocumentLines": [
            {"VatGroup": "O1", "LineTotal": 172005.12},
            {"VatGroup": "O1", "LineTotal": 267563.52},
            {"VatGroup": "O1", "LineTotal": 442400.00}
        ]
    }

    records = map_sap_document_to_canonical_rows(raw_invoice, "Invoice", "Invoices")
    assert len(records) == 1
    assert records[0].invoice_number == "764"
    assert records[0].base_amount == Decimal("881968.64")
    assert records[0].pin == "P000609554G"
    assert records[0].cu_number == "0190439340000000134"


def test_sap_mapper_purchase_cu_source_alternate_field():
    # When purchase_cu_source points at a different SAP field, that field is used for cu_number.
    raw_invoice = {
        "DocNum": 900,
        "CardName": "Acme Ltd",
        "FederalTaxID": "P99999",
        "DocDate": "2026-03-02T00:00:00Z",
        "U_CUINV": "SHOULD_BE_IGNORED",
        "NumAtCard": "VEND-INV-123",
        "DocumentLines": [{"VatGroup": "O1", "LineTotal": 100.00}]
    }

    records = map_sap_document_to_canonical_rows(
        raw_invoice, "Invoice", "Invoices", purchase_cu_source="NumAtCard"
    )
    assert len(records) == 1
    assert records[0].cu_number == "VEND-INV-123"


def test_sap_mapper_purchase_cu_source_comments_field():
    raw_invoice = {
        "DocNum": 901,
        "CardName": "Acme Ltd",
        "FederalTaxID": "P99999",
        "DocDate": "2026-03-02T00:00:00Z",
        "Comments": "CU: 0190439340000000999",
        "DocumentLines": [{"VatGroup": "O1", "LineTotal": 100.00}]
    }

    records = map_sap_document_to_canonical_rows(
        raw_invoice, "Invoice", "Invoices", purchase_cu_source="Comments"
    )
    assert len(records) == 1
    assert records[0].cu_number == "CU: 0190439340000000999"



def test_sap_mapper_aggregation_boundaries():
    # Test that aggregation never combines lines from different SAP invoices even if they share CU and VAT.
    invoice_a = {
        "DocNum": 100,
        "CardName": "Customer A",
        "FederalTaxID": "P12345",
        "DocDate": "2026-03-01T00:00:00Z",
        "U_CUINV": "CU1",
        "DocumentLines": [{"VatGroup": "O1", "LineTotal": 100.00}]
    }
    invoice_b = {
        "DocNum": 101,
        "CardName": "Customer B",
        "FederalTaxID": "P12345",
        "DocDate": "2026-03-02T00:00:00Z",
        "U_CUINV": "CU1",
        "DocumentLines": [{"VatGroup": "O1", "LineTotal": 200.00}]
    }

    records_a = map_sap_document_to_canonical_rows(invoice_a, "Invoice", "Invoices")
    records_b = map_sap_document_to_canonical_rows(invoice_b, "Invoice", "Invoices")

    assert len(records_a) == 1
    assert records_a[0].invoice_number == "100"
    assert records_a[0].base_amount == Decimal("100.00")

    assert len(records_b) == 1
    assert records_b[0].invoice_number == "101"
    assert records_b[0].base_amount == Decimal("200.00")


def test_sap_mapper_vat_group_normalization():
    # Test that SAP VAT codes are normalized to canonical percentage strings
    raw_invoice = {
        "DocNum": 765,
        "CardName": "Welding Alloys Ltd",
        "FederalTaxID": "P000609554G",
        "DocDate": "2026-03-02T00:00:00Z",
        "U_CUINV": "0190439340000000134",
        "DocumentLines": [
            {"VatGroup": "O1", "LineTotal": 100.00},
            {"VatGroup": "A16", "LineTotal": 200.00}
        ]
    }

    records = map_sap_document_to_canonical_rows(raw_invoice, "Invoice", "Invoices", reconciliation_type="sales")
    assert len(records) == 2
    assert records[0].vat_group == "16"   # O1 -> 16
    assert records[1].vat_group == "A16"  # unknown code passes through


def test_sap_mapper_fallback_warnings():
    # Test fallback warning logic for missing FederalTaxID
    raw_invoice = {
        "DocNum": 766,
        "CardName": "Welding Alloys Ltd",
        "DocDate": "2026-03-02T00:00:00Z",
        "U_CUINV": "CU1",
        "DocumentLines": [
            {"VatGroup": "O1", "LineTotal": 100.00}
        ]
    }

    with patch("app.services.sap_mapper.logger.warning") as mock_warn:
        records = map_sap_document_to_canonical_rows(raw_invoice, "Invoice", "Invoices")
        assert len(records) == 1
        assert records[0].pin == ""
        assert records[0].cu_number == "CU1"
        # 1 warning expected (for FederalTaxID)
        assert mock_warn.call_count == 1


def test_sap_mapper_base_amount_policies():
    raw_invoice = {
        "DocNum": 767,
        "CardName": "Welding Alloys Ltd",
        "FederalTaxID": "P000609554G",
        "DocDate": "2026-03-02T00:00:00Z",
        "U_CUINV": "CU1",
        "DocumentLines": [
            {"VatGroup": "O1", "LineTotal": 100.00},
            {"VatGroup": "O1", "LineTotal": 0.00},     # <= 0
            {"VatGroup": "O1", "LineTotal": -50.00}    # <= 0
        ]
    }

    settings = get_settings()
    original_policy = settings.sap_base_amount_policy

    try:
        # 1. SKIP Policy (skips 0.00, allows negative lines: 100 + -50 = 50.00)
        settings.sap_base_amount_policy = BaseAmountPolicy.SKIP
        records = map_sap_document_to_canonical_rows(raw_invoice, "Invoice", "Invoices")
        assert len(records) == 1
        assert records[0].base_amount == Decimal("50.00")

        # 2. REJECT Policy (rejects on 0.00)
        settings.sap_base_amount_policy = BaseAmountPolicy.REJECT
        with pytest.raises(SAPQueryError, match="Base Amount is zero"):
            map_sap_document_to_canonical_rows(raw_invoice, "Invoice", "Invoices")

        # 3. ALLOW Policy (allows 0.00 and negative lines: 100 + 0 + -50 = 50.00)
        settings.sap_base_amount_policy = BaseAmountPolicy.ALLOW
        records = map_sap_document_to_canonical_rows(raw_invoice, "Invoice", "Invoices")
        assert len(records) == 1
        assert records[0].base_amount == Decimal("50.00")
    finally:
        settings.sap_base_amount_policy = original_policy


def test_sap_mapper_explicit_base_amount_policy_overrides_env():
    raw_invoice = {
        "DocNum": 770,
        "CardName": "Welding Alloys Ltd",
        "FederalTaxID": "P000609554G",
        "DocDate": "2026-03-02T00:00:00Z",
        "U_CUINV": "CU1",
        "DocumentLines": [
            {"VatGroup": "O1", "LineTotal": 100.00},
            {"VatGroup": "O1", "LineTotal": 0.00},
        ]
    }

    settings = get_settings()
    original_policy = settings.sap_base_amount_policy

    try:
        # Env default is SKIP, but the per-company policy passed explicitly wins.
        settings.sap_base_amount_policy = BaseAmountPolicy.SKIP
        records = map_sap_document_to_canonical_rows(
            raw_invoice, "Invoice", "Invoices", base_amount_policy="allow"
        )
        assert len(records) == 1
        assert records[0].base_amount == Decimal("100.00")
    finally:
        settings.sap_base_amount_policy = original_policy


def test_sap_mapper_credit_note_and_debit_note_sign_normalization():
    # Test Credit Note (negative mapping)
    raw_credit_note = {
        "DocNum": 768,
        "CardName": "Customer",
        "FederalTaxID": "P123",
        "DocDate": "2026-03-02T00:00:00Z",
        "U_CUINV": "CU1",
        "DocumentLines": [{"VatGroup": "16", "LineTotal": 500.00}]
    }
    
    # Even if line total is positive, credit note maps to negative
    cn_records = map_sap_document_to_canonical_rows(raw_credit_note, "CreditNote", "CreditNotes")
    assert len(cn_records) == 1
    assert cn_records[0].base_amount == Decimal("-500.00")
    assert cn_records[0].provenance.source_document_type == "CreditNote"

    # Test Debit Note mapping (+abs) via DocumentSubType
    raw_debit_note = {
        "DocNum": 769,
        "CardName": "Customer",
        "FederalTaxID": "P123",
        "DocDate": "2026-03-02T00:00:00Z",
        "U_CUINV": "CU1",
        "DocumentSubType": "bod_DebitMemo",
        "DocumentLines": [{"VatGroup": "16", "LineTotal": -200.00}]
    }

    settings = get_settings()
    settings.sap_base_amount_policy = BaseAmountPolicy.ALLOW # allow negative line
    dn_records = map_sap_document_to_canonical_rows(raw_debit_note, "Invoice", "Invoices")
    assert len(dn_records) == 1
    assert dn_records[0].base_amount == Decimal("200.00")
    assert dn_records[0].provenance.source_document_type == "DebitNote"


def test_sap_mapper_multiple_vat_groups_emit_multiple_rows():
    raw_doc = {
        "DocNum": 770,
        "CardName": "Customer",
        "FederalTaxID": "P123",
        "DocDate": "2026-03-02T00:00:00Z",
        "U_CUINV": "CU1",
        "DocumentLines": [
            {"VatGroup": "O1", "LineTotal": 100.00},
            {"VatGroup": "0", "LineTotal": 50.00}
        ]
    }
    
    records = map_sap_document_to_canonical_rows(raw_doc, "Invoice", "Invoices")
    assert len(records) == 2
    assert records[0].vat_group == "16" # O1 mapped
    assert records[0].base_amount == Decimal("100.00")
    assert records[1].vat_group == "0"
    assert records[1].base_amount == Decimal("50.00")


def test_sap_configuration_startup_validation():
    # Test that invalid configurations fail fast at startup
    from app.core.config import Settings
    
    with pytest.raises(SAPConfigurationError):
        Settings(
            DATABASE_URL="sqlite:///test.db",
            SECRET_KEY="some-secret-key",
            SAP_BASE_URL="https://sap-test:50000/b1s/v1",
            SAP_USERNAME=""  # Missing username
        )


def test_sap_mapper_tax_percentage_per_row_primary():
    # Test that TaxPercentagePerRow is used as the authoritative tax rate, even with custom/company-specific VatGroup strings
    raw_doc = {
        "DocNum": 801,
        "CardName": "Custom SAP Customer",
        "FederalTaxID": "P000000000A",
        "DocDate": "2026-03-02T00:00:00Z",
        "U_CUINV": "CU100",
        "DocumentLines": [
            {"TaxPercentagePerRow": 16.0, "VatGroup": "SALEVAT", "LineTotal": 1000.00},
            {"TaxPercentagePerRow": 8.0, "VatGroup": "REDUCED8", "LineTotal": 500.00}
        ]
    }
    records = map_sap_document_to_canonical_rows(raw_doc, "Invoice", "Invoices", reconciliation_type="sales")
    assert len(records) == 2
    vat_map = {r.vat_group: r.base_amount for r in records}
    assert vat_map["16"] == Decimal("1000.00")
    assert vat_map["8"] == Decimal("500.00")


def test_sap_mapper_tax_percentage_per_row_zero_vs_exempt():
    # Test that TaxPercentagePerRow == 0.0 checks VatGroup to differentiate Exempt from Zero Rated
    raw_doc = {
        "DocNum": 802,
        "CardName": "Custom SAP Customer",
        "FederalTaxID": "P000000000A",
        "DocDate": "2026-03-02T00:00:00Z",
        "U_CUINV": "CU101",
        "DocumentLines": [
            {"TaxPercentagePerRow": 0.0, "VatGroup": "X0", "LineTotal": 300.00},  # X0 maps to EXEMPT in sales output_map
            {"TaxPercentagePerRow": 0.0, "VatGroup": "Z0", "LineTotal": 200.00}   # Z0 is Zero Rated -> "0"
        ]
    }
    records = map_sap_document_to_canonical_rows(raw_doc, "Invoice", "Invoices", reconciliation_type="sales")
    assert len(records) == 2
    vat_map = {r.vat_group: r.base_amount for r in records}
    assert vat_map["EXEMPT"] == Decimal("300.00")
    assert vat_map["0"] == Decimal("200.00")


def test_sap_mapper_tax_percentage_missing_fallback():
    # Test fallback to VatGroup when TaxPercentagePerRow is missing
    raw_doc = {
        "DocNum": 803,
        "CardName": "Fallback Test",
        "FederalTaxID": "P000000000A",
        "DocDate": "2026-03-02T00:00:00Z",
        "U_CUINV": "CU102",
        "DocumentLines": [
            {"VatGroup": "O1", "LineTotal": 400.00}
        ]
    }
    records = map_sap_document_to_canonical_rows(raw_doc, "Invoice", "Invoices", reconciliation_type="sales")
    assert len(records) == 1
    assert records[0].vat_group == "16"
    assert records[0].base_amount == Decimal("400.00")


def test_sap_mapper_missing_both_tax_fields_raises_error():
    # Test error raised when neither TaxPercentagePerRow nor VatGroup is present
    raw_doc = {
        "DocNum": 804,
        "CardName": "No Tax Field Test",
        "FederalTaxID": "P000000000A",
        "DocDate": "2026-03-02T00:00:00Z",
        "U_CUINV": "CU103",
        "DocumentLines": [
            {"LineTotal": 400.00}
        ]
    }
    with pytest.raises(SAPQueryError) as exc_info:
        map_sap_document_to_canonical_rows(raw_doc, "Invoice", "Invoices", reconciliation_type="sales")
    assert "missing tax fields" in str(exc_info.value)


def test_sap_client_clone_session_isolation():
    client = SAPClient(
        base_url="https://sap-test:50000/b1s/v1",
        username="user1",
        password="pass1",
        company_db="db1",
        verify_ssl=False,
    )
    client.session_id = "original-session-999"
    client.cookies = {"B1SESSION": "original-session-999"}
    client.session_expiry = datetime.datetime.now() + datetime.timedelta(minutes=10)

    cloned = client.clone()

    # Connection configuration must match
    assert cloned.base_url == client.base_url
    assert cloned.username == client.username
    assert cloned.password == client.password
    assert cloned.company_db == client.company_db
    assert cloned.verify_ssl == client.verify_ssl

    # Session authentication state MUST NOT be shared
    assert cloned.session_id is None
    assert cloned.cookies == {}
    assert cloned.session_expiry is None
    assert cloned.client is not client.client


def test_sap_client_get_documents_pages_sends_prefer_header():
    client = SAPClient()
    client.base_url = "https://sap-test:50000/b1s/v1"
    client.session_id = "active-session"
    client.cookies = {"B1SESSION": "active-session"}
    client.session_expiry = datetime.datetime.now() + datetime.timedelta(minutes=10)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"value": []}

    with patch.object(client, "_execute_request_with_retry", return_value=mock_response) as mock_exec:
        list(client.get_documents_pages("2026-03-01", "2026-03-02", "Invoices", page_size=250))
        mock_exec.assert_called_once()
        _, kwargs = mock_exec.call_args
        params = kwargs.get("params", {})
        headers = kwargs.get("headers", {})
        assert "$top" not in params
        assert headers.get("Prefer") == "odata.maxpagesize=250"


def test_sap_page_size_setting_validation():
    from pydantic import ValidationError
    from app.core.config import Settings

    # Valid bounds (1 .. 1000)
    s = Settings(
        DATABASE_URL="sqlite:///test.db",
        SECRET_KEY="some-secret-key",
        SAP_PAGE_SIZE=200,
    )
    assert s.sap_page_size == 200

    # Invalid: 0 (less than 1)
    with pytest.raises(ValidationError):
        Settings(
            DATABASE_URL="sqlite:///test.db",
            SECRET_KEY="some-secret-key",
            SAP_PAGE_SIZE=0,
        )

    # Invalid: 1500 (greater than 1000)
    with pytest.raises(ValidationError):
        Settings(
            DATABASE_URL="sqlite:///test.db",
            SECRET_KEY="some-secret-key",
            SAP_PAGE_SIZE=1500,
        )


def test_sap_client_get_documents_pages_requires_page_size():
    client = SAPClient()
    with pytest.raises(ValueError, match="page_size must be explicitly provided"):
        list(client.get_documents_pages("2026-03-01", "2026-03-02", "Invoices"))




