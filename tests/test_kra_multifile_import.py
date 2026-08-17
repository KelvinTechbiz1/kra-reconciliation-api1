"""Guards for the "not all KRA files are imported" report.

Three independent ways rows went missing, each reproduced against the real June
export in data/purchasesjunetechbiz/:
  1. The header heuristic deleted the first invoice of a file whose first row merely
     contained a substring like "cu" (every "|KRACU..." CU number does).
  2. One unreadable file aborted the whole batch, discarding every good file with it.
  3. A second upload deleted everything the first upload had loaded.
"""

import io
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.reconciliation_session import SessionInvoice
from app.schemas.invoice import InvoiceSource, ReconciliationType
from app.services import kra_service
from app.services.kra_service import _looks_like_header_row
from app.services.settings_service import SettingsService

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "purchasesjunetechbiz"

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_kra_multifile_db.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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


def _upload(filename: str, body: bytes | None = None) -> UploadFile:
    if body is None:
        body = (DATA_DIR / filename).read_bytes()
    return UploadFile(filename=filename, file=io.BytesIO(body))


REAL_FILES = [
    "SEC_F_Digital_Supply1.CSV",
    "SEC_F_WITH_VAT_PIN1.CSV",
    "SEC_G_WITH_VAT_PIN1.CSV",
    "SEC_H_WITH_VAT_PIN1.CSV",
    "SEC_I_WITH_VAT_PIN1.CSV",
]


# --------------------------------------------------------------------------- #
# 1. The header heuristic must not eat data
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("cell", [
    "|KRACU0300000313/207924",   # contains "cu"
    "|0040076780000806904",
    "P051123223G",
    "08/06/2026",
])
def test_data_cells_are_never_read_as_headings(cell):
    assert not any(
        kra_service._kw_in_cell(kw, cell) for kw in kra_service.HEADER_KEYWORDS
    ), f"{cell!r} was treated as a column heading"


def test_kra_data_row_is_not_mistaken_for_a_header():
    row = ["Local", "P052299208I", "RITAKE CARE SERVICES", "08/06/2026",
           "|KRACU0200104934/113", "ETIMS/TIMS purchases", "", "4655.17"]
    assert _looks_like_header_row(row) is False


def test_a_genuine_header_row_is_still_detected():
    row = ["Pin Number", "Customer Name", "Invoice Number", "Invoice Date",
           "CU Number", "VAT Group", "Base Amount"]
    assert _looks_like_header_row(row) is True


@pytest.mark.parametrize("filename,expected_rows", [
    ("SEC_F_WITH_VAT_PIN1.CSV", 34),   # was 33 - first invoice was being deleted
    ("SEC_I_WITH_VAT_PIN1.CSV", 4),    # was 3
    ("SEC_G_WITH_VAT_PIN1.CSV", 24),
    ("SEC_H_WITH_VAT_PIN1.CSV", 5),
])
def test_every_line_of_a_real_export_is_imported(db_session, filename, expected_rows):
    res = kra_service.parse_kra_csv(_upload(filename), db_session)
    assert res.rows == expected_rows
    assert res.parsed == expected_rows
    assert res.errors_count == 0


def test_first_invoice_of_the_file_survives(db_session):
    """The row previously lost: a real KES 4,655.17 purchase."""
    res = kra_service.parse_kra_csv(_upload("SEC_F_WITH_VAT_PIN1.CSV"), db_session)
    first = res.invoices[0]
    assert first.partner_name == "RITAKE CARE SERVICES"
    assert first.pin == "P052299208I"
    assert first.base_amount == Decimal("4655.17")


# --------------------------------------------------------------------------- #
# 2. One bad file must not discard the good ones
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("bad_name,bad_body,reason", [
    ("SEC_D_UNKNOWN.CSV", b"a,b,c\n1,2,3\n", "unconfigured section"),
    ("SEC_B_EMPTY.CSV", b"", "empty file"),
    ("not_a_section.csv", b"a,b,c\n", "missing SEC_ prefix"),
    ("SEC_B_BINARY.CSV", b"\xff\xfe\x00bad", "not UTF-8"),
])
def test_one_unreadable_file_does_not_discard_the_batch(db_session, bad_name, bad_body, reason):
    batch = [_upload(n) for n in REAL_FILES] + [_upload(bad_name, bad_body)]
    invoices, statuses = kra_service.parse_multiple_kra_csvs(batch, db_session)

    assert len(statuses) == len(REAL_FILES) + 1, "every file must be reported on"
    assert len(invoices) == 70, f"good files were lost because of the {reason}"

    failed = [s for s in statuses if s.filename == bad_name][0]
    assert failed.parsed == 0
    assert failed.errors_count == 1
    assert failed.errors[0].message, "the failure reason must reach the user"

    for status in statuses:
        if status.filename != bad_name:
            assert status.parsed > 0


def test_all_real_files_import_in_one_batch(db_session):
    invoices, statuses = kra_service.parse_multiple_kra_csvs(
        [_upload(n) for n in REAL_FILES], db_session
    )
    assert len(statuses) == 5
    assert [s.parsed for s in statuses] == [3, 34, 24, 5, 4]
    assert len(invoices) == 70


# --------------------------------------------------------------------------- #
# Section coverage
# --------------------------------------------------------------------------- #

# Verbatim row from a real SEC_D2 export. Exports have no local PIN and no customer
# name, and the amount sits at index 11 rather than 6/7/8 like the other sections.
SEC_D2_ROW = (
    b'"",,KRAMW019202207043934,12/03/2026,|0190439340000000463,'
    b'Services,Exported Services,,,,,110700.00\n'
)


def test_sec_d2_exports_are_importable(db_session):
    res = kra_service.parse_kra_csv(_upload("SEC_D2_EXPORTS1.CSV", SEC_D2_ROW), db_session)

    assert res.errors_count == 0, res.errors
    assert res.parsed == 1
    invoice = res.invoices[0]
    assert invoice.invoice_number == "KRAMW019202207043934"
    assert invoice.cu_number == "0190439340000000463"
    assert invoice.base_amount == Decimal("110700.00")
    # Exports are zero-rated, and must stay distinct from EXEMPT.
    assert invoice.vat_group == "0"
    # Blank PIN / customer name are normal for exports, not an error.
    assert invoice.pin == ""
    assert invoice.partner_name == ""


def test_every_seeded_section_has_both_a_profile_and_a_vat_mapping(db_session):
    """A section configured on one side only fails at upload time with a 400."""
    from app.models.settings import KRAVATMapping
    from app.services.parsing_profile_service import DEFAULT_PARSING_PROFILES

    mapped = {m.section_prefix.upper() for m in db_session.query(KRAVATMapping)}
    profiled = set(DEFAULT_PARSING_PROFILES)
    assert profiled == mapped, (
        f"profile but no VAT mapping: {sorted(profiled - mapped)}; "
        f"VAT mapping but no profile: {sorted(mapped - profiled)}"
    )


def test_settings_shows_every_section_the_importer_supports(db_session):
    """Settings read from a stored JSON snapshot that can predate newer sections.

    A section missing there but present in the importer's table imports fine yet is
    invisible in the UI, which reads as "not configured".
    """
    from app.services.settings_service import _with_default_profiles
    from app.services.parsing_profile_service import DEFAULT_PARSING_PROFILES

    stored_before_sec_d2 = {
        "schema_version": 1,
        "profiles": {"SEC_B": {
            "pin_column": 0, "partner_name_column": 1, "invoice_number_column": 2,
            "invoice_date_column": 3, "cu_number_column": 4, "base_amount_column": 6,
        }},
    }
    shown = _with_default_profiles(stored_before_sec_d2)["profiles"]

    assert set(shown) == set(DEFAULT_PARSING_PROFILES)
    # An operator's customization still wins over the default.
    assert shown["SEC_B"]["base_amount_column"] == 6


def test_operator_customizations_are_not_overwritten_by_defaults():
    from app.services.settings_service import _with_default_profiles

    customized = {
        "schema_version": 1,
        "profiles": {"SEC_F": {
            "pin_column": 1, "partner_name_column": 2, "invoice_number_column": None,
            "invoice_date_column": 3, "cu_number_column": 4, "base_amount_column": 99,
        }},
    }
    assert _with_default_profiles(customized)["profiles"]["SEC_F"]["base_amount_column"] == 99


# --------------------------------------------------------------------------- #
# Multi-tenant profile isolation
# --------------------------------------------------------------------------- #

# Verbatim rows from a real SEC_E export. Date sits at index 3.
SEC_E_ROWS = (
    b"A000178861W,KARAMA MAHFUDH BREK ATHMAN,KRAMW019202207043370,02/05/2026,"
    b"|0190433700000033286,ETIMS/TIMS sales,155100.00\n"
)


def _company_with_profiles(db, name, profiles):
    from app.models.company import Company
    from app.services.settings_service import SettingsService

    company = Company(name=name)
    db.add(company)
    db.commit()
    setting = SettingsService.get_or_create_company_settings(db, company.id)
    setting.kra_parsing_profiles = profiles
    db.commit()
    return company


def test_one_companys_profiles_are_never_served_to_another(db_session):
    """Reproduces the production failure: same file, one company OK, another rejected.

    Both companies sit at settings version 1. A cache keyed only on that version handed
    the second company the first company's column indices.
    """
    from app.services.parsing_profile_service import ParsingProfileService

    ParsingProfileService._profile_cache.clear()

    # Company A has customized SEC_E so the date is read from a different column.
    company_a = _company_with_profiles(db_session, "Company A", {
        "schema_version": 1,
        "profiles": {"SEC_E": {
            "pin_column": 0, "partner_name_column": 1, "invoice_number_column": 2,
            "invoice_date_column": 4, "cu_number_column": 3, "base_amount_column": 6,
        }},
    })
    # Company B uses the standard layout, with the date at index 3.
    company_b = _company_with_profiles(db_session, "Company B", {
        "schema_version": 1,
        "profiles": {"SEC_E": {
            "pin_column": 0, "partner_name_column": 1, "invoice_number_column": 2,
            "invoice_date_column": 3, "cu_number_column": 4, "base_amount_column": 6,
        }},
    })

    setting_a = ParsingProfileService.get_profiles(db_session, company_a.id)
    setting_b = ParsingProfileService.get_profiles(db_session, company_b.id)
    assert setting_a.profiles["SEC_E"].invoice_date_column == 4
    assert setting_b.profiles["SEC_E"].invoice_date_column == 3, (
        "company B was served company A's profile"
    )

    # Company A loading first must not poison the parse for company B.
    kra_service.parse_kra_csv(_upload("SEC_E_X.CSV", SEC_E_ROWS), db_session, company_id=company_a.id)
    res_b = kra_service.parse_kra_csv(
        _upload("SEC_E_WITH_VAT_PIN1.CSV", SEC_E_ROWS), db_session, company_id=company_b.id
    )

    assert res_b.errors_count == 0, res_b.errors
    assert res_b.parsed == 1
    assert res_b.invoices[0].invoice_date == date(2026, 5, 2)


def test_profile_cache_still_refreshes_when_settings_change(db_session):
    """Per-company keying must not stop an edit from taking effect."""
    from app.services.parsing_profile_service import ParsingProfileService
    from app.services.settings_service import SettingsService

    ParsingProfileService._profile_cache.clear()
    company = _company_with_profiles(db_session, "Company C", {
        "schema_version": 1,
        "profiles": {"SEC_E": {
            "pin_column": 0, "partner_name_column": 1, "invoice_number_column": 2,
            "invoice_date_column": 3, "cu_number_column": 4, "base_amount_column": 6,
        }},
    })
    assert ParsingProfileService.get_profiles(db_session, company.id).profiles["SEC_E"].base_amount_column == 6

    setting = SettingsService.get_or_create_company_settings(db_session, company.id)
    setting.kra_parsing_profiles = {
        "schema_version": 1,
        "profiles": {"SEC_E": {
            "pin_column": 0, "partner_name_column": 1, "invoice_number_column": 2,
            "invoice_date_column": 3, "cu_number_column": 4, "base_amount_column": 5,
        }},
    }
    setting.version += 1
    db_session.commit()

    assert ParsingProfileService.get_profiles(db_session, company.id).profiles["SEC_E"].base_amount_column == 5


def test_batch_of_only_unreadable_files_still_fails_loudly(db_session):
    """With nothing importable there is no "rest" to keep - don't fake success."""
    from app.api.v1 import _session_helpers

    session, user = _make_session(db_session)
    with pytest.raises(HTTPException) as exc:
        _session_helpers.upload_kra_csvs(
            db_session, user, ReconciliationType.PURCHASES,
            [_upload("SEC_B_EMPTY.CSV", b"")], session.id,
        )
    assert exc.value.status_code == 400


# --------------------------------------------------------------------------- #
# 3. A second upload must add to the session, not replace it
# --------------------------------------------------------------------------- #

def _make_session(db):
    from app.models.company import Company
    from app.models.reconciliation_session import ReconciliationSession
    from app.models.user import User

    company = Company(name="Techbiz")
    db.add(company)
    db.commit()
    user = User(username="importer", password_hash="x", company_id=company.id, role="admin")
    db.add(user)
    db.commit()
    session = ReconciliationSession(
        company_id=company.id, user_id=user.id,
        from_date=date(2026, 6, 1), to_date=date(2026, 6, 30),
        session_type=ReconciliationType.PURCHASES, is_compared=False,
    )
    db.add(session)
    db.commit()
    return session, user


def _kra_rows(db, session_id):
    return db.query(SessionInvoice).filter(
        SessionInvoice.session_id == session_id,
        SessionInvoice.source == InvoiceSource.KRA,
    ).count()


def test_second_upload_adds_to_the_first(db_session):
    """The reported failure: uploading in two passes kept only the last pass."""
    from app.api.v1 import _session_helpers

    session, user = _make_session(db_session)

    first = _session_helpers.upload_kra_csvs(
        db_session, user, ReconciliationType.PURCHASES,
        [_upload(n) for n in ("SEC_F_WITH_VAT_PIN1.CSV", "SEC_G_WITH_VAT_PIN1.CSV")],
        session.id,
    )
    assert first["added"] == 58
    assert _kra_rows(db_session, session.id) == 58

    second = _session_helpers.upload_kra_csvs(
        db_session, user, ReconciliationType.PURCHASES,
        [_upload(n) for n in ("SEC_H_WITH_VAT_PIN1.CSV", "SEC_I_WITH_VAT_PIN1.CSV")],
        session.id,
    )
    assert second["added"] == 9
    assert second["total_kra_records"] == 67
    assert _kra_rows(db_session, session.id) == 67, "the first upload was discarded"


def test_re_uploading_the_same_file_does_not_double_count(db_session):
    from app.api.v1 import _session_helpers

    session, user = _make_session(db_session)
    args = (db_session, user, ReconciliationType.PURCHASES)

    _session_helpers.upload_kra_csvs(*args, [_upload("SEC_G_WITH_VAT_PIN1.CSV")], session.id)
    repeat = _session_helpers.upload_kra_csvs(
        *args, [_upload("SEC_G_WITH_VAT_PIN1.CSV")], session.id
    )

    assert repeat["added"] == 0
    assert repeat["duplicates_skipped"] == 24
    assert _kra_rows(db_session, session.id) == 24


def test_appended_rows_get_unique_row_numbers(db_session):
    """session_invoices has UniqueConstraint(session_id, source, row_number)."""
    from app.api.v1 import _session_helpers

    session, user = _make_session(db_session)
    args = (db_session, user, ReconciliationType.PURCHASES)

    _session_helpers.upload_kra_csvs(*args, [_upload("SEC_G_WITH_VAT_PIN1.CSV")], session.id)
    _session_helpers.upload_kra_csvs(*args, [_upload("SEC_H_WITH_VAT_PIN1.CSV")], session.id)

    numbers = [
        r.row_number for r in db_session.query(SessionInvoice).filter(
            SessionInvoice.session_id == session.id,
            SessionInvoice.source == InvoiceSource.KRA,
        )
    ]
    assert len(numbers) == len(set(numbers)) == 29
    assert sorted(numbers) == list(range(1, 30))


def test_upload_invalidates_a_cached_comparison(db_session):
    """Adding rows must force a recompare, or the summary would go stale."""
    from app.api.v1 import _session_helpers

    session, user = _make_session(db_session)
    _session_helpers.upload_kra_csvs(
        db_session, user, ReconciliationType.PURCHASES,
        [_upload("SEC_G_WITH_VAT_PIN1.CSV")], session.id,
    )
    session.is_compared = True
    session.comparison_results = {"summary": {"matches": 1}}
    db_session.commit()

    _session_helpers.upload_kra_csvs(
        db_session, user, ReconciliationType.PURCHASES,
        [_upload("SEC_H_WITH_VAT_PIN1.CSV")], session.id,
    )
    db_session.refresh(session)
    assert session.is_compared is False
    assert session.comparison_results is None
