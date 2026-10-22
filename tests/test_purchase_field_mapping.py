"""Configurable SAP fields for Purchase Invoice comparison (VAT code and base amount)."""
import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import SAPQueryError
from app.core.security import hash_password
from app.database.base import Base
from app.database.database import get_db
from app.main import app
from app.models.settings import SettingAuditLog
from app.models.user import User
from app.services.sap_mapper import PurchaseFieldMapping, map_sap_document_to_canonical_rows

LINE_UDFS = PurchaseFieldMapping(vat_field="U_Taxable", amount_field="U_ExcVat")
HEADER_FIELDS = PurchaseFieldMapping(
    vat_field="U_Taxable", vat_level="header", amount_field="U_DocTotal", amount_level="header"
)


def _zero_rated_doc(**header):
    """A supplier invoice booked in SAP as zero-rated with the VAT-inclusive amount, while
    the UDFs carry what KRA shows: 16% on 1000."""
    return {
        "DocNum": 501,
        "DocDate": "2026-10-01",
        "CardName": "Supplier Ltd",
        "FederalTaxID": "P000000001A",
        "U_CUINV": "KRAMW001202610000001",
        "DocumentLines": [
            {"VatGroup": "I2", "TaxPercentagePerRow": 0, "LineTotal": 1160, "U_Taxable": "I1", "U_ExcVat": 1000},
        ],
        **header,
    }


def _map(doc, mapping=None, doc_type="Invoice", **kwargs):
    kwargs.setdefault("base_amount_policy", "allow")
    return map_sap_document_to_canonical_rows(
        doc, doc_type, "PurchaseInvoices", reconciliation_type="purchases", field_mapping=mapping, **kwargs
    )


def _breakdown(rows):
    return {r.vat_group: r.base_amount for r in rows}


# --------------------------------------------------------------------------- #
# Mapper
# --------------------------------------------------------------------------- #
def test_without_mapping_standard_fields_are_used():
    assert _breakdown(_map(_zero_rated_doc())) == {"0": Decimal("1160.00")}
    assert _breakdown(_map(_zero_rated_doc(), PurchaseFieldMapping())) == {"0": Decimal("1160.00")}


def test_line_level_udfs_replace_vat_code_and_amount():
    assert _breakdown(_map(_zero_rated_doc(), LINE_UDFS)) == {"16": Decimal("1000.00")}


def test_lines_grouped_by_custom_vat_code():
    doc = _zero_rated_doc()
    doc["DocumentLines"] = [
        {"VatGroup": "I2", "LineTotal": 1160, "U_Taxable": "I1", "U_ExcVat": 1000},
        {"VatGroup": "I2", "LineTotal": 580, "U_Taxable": "16%", "U_ExcVat": 500},
        {"VatGroup": "I2", "LineTotal": 200, "U_Taxable": "X1", "U_ExcVat": 200},
    ]
    assert _breakdown(_map(doc, LINE_UDFS)) == {"16": Decimal("1500.00"), "EXEMPT": Decimal("200.00")}


@pytest.mark.parametrize("value, expected", [("I1", "16"), ("16", "16"), ("16%", "16"), (8.0, "8"), ("exempt", "EXEMPT")])
def test_custom_vat_code_accepts_mapped_codes_and_rates(value, expected):
    doc = _zero_rated_doc()
    doc["DocumentLines"][0]["U_Taxable"] = value
    assert _breakdown(_map(doc, LINE_UDFS)) == {expected: Decimal("1000.00")}


def test_only_vat_field_configured_keeps_line_total():
    rows = _map(_zero_rated_doc(), PurchaseFieldMapping(vat_field="U_Taxable"))
    assert _breakdown(rows) == {"16": Decimal("1160.00")}


def test_header_level_fields_give_one_row_per_document():
    doc = _zero_rated_doc(U_Taxable="I1", U_DocTotal=1000)
    doc["DocumentLines"].append({"VatGroup": "I2", "LineTotal": 40})
    assert _breakdown(_map(doc, HEADER_FIELDS)) == {"16": Decimal("1000.00")}


def test_header_vat_with_line_amounts_sums_lines():
    doc = _zero_rated_doc(U_Taxable="I1")
    doc["DocumentLines"].append({"VatGroup": "I2", "LineTotal": 580, "U_ExcVat": 500})
    mapping = PurchaseFieldMapping(vat_field="U_Taxable", vat_level="header", amount_field="U_ExcVat")
    assert _breakdown(_map(doc, mapping)) == {"16": Decimal("1500.00")}


LINE_VAT_HEADER_AMOUNT = PurchaseFieldMapping(vat_field="U_Taxable", amount_field="U_DocTotal", amount_level="header")


def test_line_vat_with_header_amount_uses_the_lines_single_vat_group():
    doc = _zero_rated_doc(U_DocTotal=1000)
    doc["DocumentLines"].append({"VatGroup": "I2", "LineTotal": 40, "U_Taxable": "16%"})
    stats = {}
    assert _breakdown(_map(doc, LINE_VAT_HEADER_AMOUNT, stats=stats)) == {"16": Decimal("1000.00")}
    assert stats == {"custom": 1}


def test_header_amount_with_standard_vat_uses_line_vat_group():
    doc = _zero_rated_doc(U_DocTotal=1000)
    doc["DocumentLines"][0]["VatGroup"] = "I1"
    doc["DocumentLines"][0]["TaxPercentagePerRow"] = 16
    mapping = PurchaseFieldMapping(amount_field="U_DocTotal", amount_level="header")
    assert _breakdown(_map(doc, mapping)) == {"16": Decimal("1000.00")}


def test_header_amount_with_mixed_line_vat_groups_falls_back():
    doc = _zero_rated_doc(U_DocTotal=1000)
    doc["DocumentLines"].append({"VatGroup": "I2", "LineTotal": 40, "U_Taxable": "X1"})
    stats = {}
    with patch("app.services.sap_mapper.logger.warning") as warn:
        rows = _map(doc, LINE_VAT_HEADER_AMOUNT, stats=stats)
    # Standard fields for the whole document: VatGroup I2 (0%) on 1160 + 40.
    assert _breakdown(rows) == {"0": Decimal("1200.00")}
    assert stats == {"fallback": 1}
    assert "different VAT codes" in str(warn.call_args_list)


def test_header_amount_with_empty_line_vat_falls_back():
    doc = _zero_rated_doc(U_DocTotal=1000)
    doc["DocumentLines"][0]["U_Taxable"] = ""
    stats = {}
    assert _breakdown(_map(doc, LINE_VAT_HEADER_AMOUNT, stats=stats)) == {"0": Decimal("1160.00")}
    assert stats == {"fallback": 1}


@pytest.mark.parametrize("blank", [None, "", "  "])
def test_empty_udf_falls_back_to_standard_fields_for_that_line(blank):
    doc = _zero_rated_doc()
    doc["DocumentLines"].append({"VatGroup": "I1", "LineTotal": 300, "U_Taxable": blank, "U_ExcVat": 999})
    stats = {}
    rows = _map(doc, LINE_UDFS, stats=stats)
    # The UDF line gives 16/1000; the line with an empty U_Taxable uses VatGroup+LineTotal
    # together (16/300), never the custom amount 999 with a standard code.
    assert _breakdown(rows) == {"16": Decimal("1300.00")}
    assert stats == {"fallback": 1}


def test_header_mapping_falls_back_when_header_fields_empty():
    stats = {}
    rows = _map(_zero_rated_doc(), HEADER_FIELDS, stats=stats)
    assert _breakdown(rows) == {"0": Decimal("1160.00")}
    assert stats == {"fallback": 1}


def test_stats_count_custom_documents():
    stats = {}
    _map(_zero_rated_doc(), LINE_UDFS, stats=stats)
    _map(_zero_rated_doc(), LINE_UDFS, stats=stats)
    assert stats == {"custom": 2}


def test_unmapped_custom_code_follows_unmapped_policy():
    doc = _zero_rated_doc()
    doc["DocumentLines"][0]["U_Taxable"] = "ZZ9"
    with patch("app.services.sap_mapper.logger.warning") as warn:
        rows = _map(doc, LINE_UDFS)
    assert _breakdown(rows) == {"ZZ9": Decimal("1000.00")}
    assert "ZZ9" in str(warn.call_args_list) and "line 0" in str(warn.call_args_list)

    with pytest.raises(SAPQueryError, match="ZZ9"):
        _map(doc, LINE_UDFS, unmapped_vat_policy="reject_invoice")


def test_invalid_custom_amount_raises():
    doc = _zero_rated_doc()
    doc["DocumentLines"][0]["U_ExcVat"] = "abc"
    with pytest.raises(SAPQueryError, match="invalid U_ExcVat"):
        _map(doc, LINE_UDFS)


def test_credit_note_custom_amount_is_negative():
    assert _breakdown(_map(_zero_rated_doc(), LINE_UDFS, doc_type="CreditNote")) == {"16": Decimal("-1000.00")}


def test_zero_custom_amount_respects_base_amount_policy():
    doc = _zero_rated_doc()
    doc["DocumentLines"][0]["U_ExcVat"] = 0
    assert _map(doc, LINE_UDFS, base_amount_policy="skip") == []


# --------------------------------------------------------------------------- #
# Settings API
# --------------------------------------------------------------------------- #
engine = create_engine("sqlite:///./test_purchase_fields_db.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(name="db_session")
def fixture_db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        from app.models.company import Company

        db.add(Company(name="Default Company"))
        db.add(User(username="admin_tester", email="a@example.com", password_hash=hash_password("pw123456"), role="admin"))
        db.commit()
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(name="client")
def fixture_client(db_session):
    app.dependency_overrides[get_db] = lambda: (yield db_session)
    with TestClient(app) as test_client:
        res = test_client.post("/api/v1/auth/login", json={"username": "admin_tester", "password": "pw123456"})
        test_client.headers["Authorization"] = f"Bearer {res.json()['access_token']}"
        yield test_client
    app.dependency_overrides.clear()


def _system_settings(client):
    return client.get("/api/v1/settings?company_id=1").json()["system_settings"]


def _put(client, **fields):
    version = _system_settings(client)["version"]
    return client.put("/api/v1/settings/system-settings?company_id=1", json={"version": version, **fields})


def test_defaults_are_standard_fields(client):
    s = _system_settings(client)
    assert s["purchase_vat_field"] is None and s["purchase_amount_field"] is None
    assert s["purchase_vat_field_level"] == "line" and s["purchase_amount_field_level"] == "line"


def test_save_and_clear_fields(client, db_session):
    res = _put(client, purchase_vat_field=" U_Taxable ", purchase_amount_field="U_ExcVat")
    assert res.status_code == 200
    assert res.json()["purchase_vat_field"] == "U_Taxable"
    assert _system_settings(client)["purchase_amount_field"] == "U_ExcVat"
    assert any(
        "purchase_vat_field" in (log.changes_json or {}) for log in db_session.query(SettingAuditLog).all()
    )

    res = _put(client, purchase_vat_field="", purchase_amount_field=None)
    assert res.status_code == 200
    assert res.json()["purchase_vat_field"] is None and res.json()["purchase_amount_field"] is None


@pytest.mark.parametrize("name", ["U Taxable", "1abc", "U_X,DocTotal", "x" * 51])
def test_invalid_field_name_rejected(client, name):
    assert _put(client, purchase_vat_field=name).status_code == 422


@pytest.mark.parametrize("vat_level", ["line", "header"])
@pytest.mark.parametrize("amount_level", ["line", "header"])
def test_levels_are_independent(client, vat_level, amount_level):
    res = _put(
        client,
        purchase_vat_field="U_Taxable", purchase_vat_field_level=vat_level,
        purchase_amount_field="U_DocTotal", purchase_amount_field_level=amount_level,
    )
    assert res.status_code == 200
    assert res.json()["purchase_vat_field_level"] == vat_level
    assert res.json()["purchase_amount_field_level"] == amount_level


# --------------------------------------------------------------------------- #
# Load path
# --------------------------------------------------------------------------- #
def _get_invoices(reconciliation_type, mapping):
    from app.core.sap_client import SAPClient
    from app.schemas.invoice import ReconciliationType
    from app.services import invoice_service

    calls = []

    def fake_pages(self, from_date, to_date, endpoint_name, *args, **kwargs):
        calls.append((endpoint_name, kwargs.get("extra_select_fields")))
        return iter([[_zero_rated_doc(U_Taxable="I1", U_DocTotal=1000)]] if endpoint_name.endswith("Invoices") else [])

    with patch.object(SAPClient, "get_documents_pages", fake_pages):
        invoices = invoice_service.get_invoices(
            datetime.date(2026, 10, 1), datetime.date(2026, 10, 31),
            reconciliation_type=ReconciliationType(reconciliation_type),
            sap_client=SAPClient(), page_size=100, base_amount_policy="allow",
            purchase_field_mapping=mapping,
        )
    return invoices, calls


def test_get_invoices_applies_mapping_to_purchases():
    invoices, calls = _get_invoices("purchases", HEADER_FIELDS)
    assert {(i.vat_group, i.base_amount) for i in invoices} == {("16", Decimal("1000.00"))}
    assert ("PurchaseInvoices", ["U_Taxable", "U_DocTotal"]) in calls


def test_get_invoices_ignores_mapping_for_sales():
    invoices, calls = _get_invoices("sales", HEADER_FIELDS)
    assert {(i.vat_group, i.base_amount) for i in invoices} == {("0", Decimal("1160.00"))}
    assert all(extra is None for _, extra in calls)
