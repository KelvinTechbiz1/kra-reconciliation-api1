"""Regression tests for two production reporting defects.

1. A CU Mismatch row displayed the SAP CU on both sides, so the two values that were
   supposed to differ rendered identically and the row looked wrongly flagged.
2. A business partner whose KRA PIN was added to the BP master after an invoice was
   posted reconciled as a PIN Mismatch, because only the document's FederalTaxID
   snapshot was ever read.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.core.sap_client import SAPClient
from app.repositories.reconciliation_repository import _to_projection
from app.reporting.export_row import to_export_rows
from app.reporting.sheet_definitions import WORKBOOK_DEFINITIONS
from app.schemas.invoice import Invoice, InvoiceSource
from app.services.invoice_service import _backfill_pins_from_business_partners
from app.services.reconciliation_service import reconcile_invoices
from app.domain.reconciliation_status import ReconciliationStatus


SAP_CU = "0190439340000000511"
KRA_CU = "0190349340000000511"  # same digits, two transposed — a real CU typo


def _invoice(source, cu, pin="P051421525N", amount="243810.00"):
    return Invoice(
        pin=pin,
        partner_name="AGRICHEM AFRICA LIMITED",
        invoice_number="1132",
        invoice_date=date(2026, 7, 15),
        cu_number=cu,
        vat_group="16",
        base_amount=Decimal(amount),
        source=source,
    )


# --------------------------------------------------------------------------- #
# 1. Per-side CU numbers
# --------------------------------------------------------------------------- #

def test_cu_mismatch_keeps_both_cu_numbers():
    """The fallback pairing is the only route to CU_MISMATCH, and it pairs rows whose
    CUs differ — so each side must keep its own value."""
    _, results = reconcile_invoices(
        [_invoice(InvoiceSource.SAP, SAP_CU)],
        [_invoice(InvoiceSource.KRA, KRA_CU)],
    )
    row = next(r for r in results if r.status == ReconciliationStatus.CU_MISMATCH)

    assert row.sap.cu_number == SAP_CU
    assert row.kra.cu_number == KRA_CU
    assert row.sap.cu_number != row.kra.cu_number


def test_matching_cu_is_not_reported_as_mismatch():
    _, results = reconcile_invoices(
        [_invoice(InvoiceSource.SAP, SAP_CU)],
        [_invoice(InvoiceSource.KRA, SAP_CU)],
    )
    assert [r.status for r in results] == [ReconciliationStatus.MATCH]


class _StoredResult:
    """Stand-in for a SessionReconciliationResult row."""

    def __init__(self, **kw):
        defaults = dict(
            cu_number=SAP_CU, invoice_type="Single Tax",
            status=ReconciliationStatus.CU_MISMATCH.value,
            amount_match=True, vat_match=True, date_match=True,
            sap_invoice_number="1132", sap_partner_name="AGRICHEM AFRICA LIMITED",
            sap_pin="P051421525N", sap_invoice_date=date(2026, 7, 15),
            sap_base_amount=Decimal("243810.00"), sap_vat_group="16",
            kra_invoice_number="KRAMW019202207043934", kra_partner_name="AGRICHEM AFRICA LIMITED",
            kra_pin="P051421525N", kra_invoice_date=date(2026, 7, 15),
            kra_base_amount=Decimal("243810.00"), kra_vat_group="16",
            sap_cu_number=SAP_CU, kra_cu_number=KRA_CU,
        )
        defaults.update(kw)
        for key, value in defaults.items():
            setattr(self, key, value)


def test_projection_carries_each_side_cu():
    p = _to_projection(_StoredResult())
    assert (p.sap_cu_number, p.kra_cu_number) == (SAP_CU, KRA_CU)


def test_projection_falls_back_for_rows_compared_before_the_columns_existed():
    """Old rows have no per-side value; both sides fall back to the single stored key
    rather than rendering blank."""
    p = _to_projection(_StoredResult(sap_cu_number=None, kra_cu_number=None))
    assert p.sap_cu_number == SAP_CU
    assert p.kra_cu_number == SAP_CU


def test_export_row_and_cu_sheet_expose_both_cu_numbers():
    rows = to_export_rows([_to_projection(_StoredResult())])
    assert (rows[0].sap_cu_number, rows[0].kra_cu_number) == (SAP_CU, KRA_CU)

    sheet = next(
        s for wb in WORKBOOK_DEFINITIONS for s in wb.sheets if s.title == "CU Mismatch"
    )
    attrs = [c.attr for c in sheet.columns]
    assert "sap_cu_number" in attrs and "kra_cu_number" in attrs


# --------------------------------------------------------------------------- #
# 2. Business Partner PIN fallback
# --------------------------------------------------------------------------- #

class _FakeClient:
    """Records the CardCodes asked for, so caching can be asserted."""

    def __init__(self, pins):
        self.pins = pins
        self.calls = []

    def get_business_partner_pins(self, card_codes, reconciliation_session_id="N/A"):
        self.calls.append(sorted(card_codes))
        return {c: self.pins[c] for c in card_codes if c in self.pins}


def test_missing_document_pin_is_filled_from_the_bp_master():
    client = _FakeClient({"C0042": "P052446394S"})
    page = [{"CardCode": "C0042", "FederalTaxID": "", "DocNum": 1131}]

    assert _backfill_pins_from_business_partners(client, page, {}, "s") == 1
    assert page[0]["FederalTaxID"] == "P052446394S"


def test_document_pin_is_never_overwritten():
    client = _FakeClient({"C0042": "PFROMMASTER"})
    page = [{"CardCode": "C0042", "FederalTaxID": "PONDOCUMENT", "DocNum": 1131}]

    assert _backfill_pins_from_business_partners(client, page, {}, "s") == 0
    assert page[0]["FederalTaxID"] == "PONDOCUMENT"
    assert client.calls == []  # nothing missing, so no lookup at all


def test_each_card_code_is_looked_up_once_across_pages():
    client = _FakeClient({"C0042": "P052446394S"})
    cache: dict[str, str] = {}
    for _ in range(3):
        page = [{"CardCode": "C0042", "FederalTaxID": ""}, {"CardCode": "C0099", "FederalTaxID": ""}]
        _backfill_pins_from_business_partners(client, page, cache, "s")

    assert client.calls == [["C0042", "C0099"]]
    assert cache == {"C0042": "P052446394S", "C0099": ""}  # the miss is cached too


def test_partner_with_no_pin_anywhere_stays_empty():
    client = _FakeClient({})
    page = [{"CardCode": "C0099", "FederalTaxID": ""}]

    assert _backfill_pins_from_business_partners(client, page, {}, "s") == 0
    assert page[0]["FederalTaxID"] == ""


def test_bp_lookup_failure_does_not_break_the_load():
    """A supplementary lookup must never fail a reconciliation — the affected rows
    keep the empty PIN they already had."""
    class _Exploding:
        def get_business_partner_pins(self, *a, **kw):
            raise RuntimeError("service layer down")

    page = [{"CardCode": "C0042", "FederalTaxID": ""}]
    cache: dict[str, str] = {}

    assert _backfill_pins_from_business_partners(_Exploding(), page, cache, "s") == 0
    assert page[0]["FederalTaxID"] == ""
    assert cache == {"C0042": ""}  # cached as a miss, so the failure is not retried


def test_get_business_partner_pins_swallows_transport_errors():
    """The swallowing lives in SAPClient, so a real outage leaves PINs empty
    instead of failing the reconciliation."""
    client = SAPClient(base_url="http://sap.invalid")
    client._ensure_session = lambda: None
    client._execute_request_with_retry = lambda *a, **kw: (_ for _ in ()).throw(
        RuntimeError("connection reset")
    )
    assert client.get_business_partner_pins(["C0042"], "s") == {}


def test_get_business_partner_pins_ignores_blank_and_duplicate_codes():
    client = SAPClient(base_url="http://sap.invalid")
    client._ensure_session = lambda: None
    calls = []

    class _Response:
        status_code = 200

        @staticmethod
        def json():
            return {"value": [{"CardCode": "C0042", "FederalTaxID": "P052446394S"},
                              {"CardCode": "C0099", "FederalTaxID": ""}]}

    def _fake_request(method, url, params=None, cookies=None, headers=None):
        calls.append(params["$filter"])
        return _Response()

    client._execute_request_with_retry = _fake_request

    result = client.get_business_partner_pins(["C0042", " C0042 ", "", None, "C0099"], "s")
    assert result == {"C0042": "P052446394S"}  # blank PIN omitted
    assert calls == ["CardCode eq 'C0042' or CardCode eq 'C0099'"]


def test_business_partner_pins_returns_empty_without_codes():
    client = SAPClient(base_url="http://sap.invalid")
    assert client.get_business_partner_pins([], "s") == {}
