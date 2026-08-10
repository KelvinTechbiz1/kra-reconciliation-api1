import os
import pytest
from pathlib import Path
from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.settings import KRAVATMapping
from app.services import kra_service
from app.services.settings_service import SettingsService
from app.services.parsing_profile_service import ParsingProfileService

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_sec_e_db.db"
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


def test_sec_e_default_seeding(db_session):
    mapping = db_session.query(KRAVATMapping).filter_by(section_prefix="SEC_E").first()
    assert mapping is not None
    assert mapping.canonical_rate == "EXEMPT"
    assert "Exempt Sales" in mapping.description


def test_sec_e_parsing_profile_lookup(db_session):
    profile = ParsingProfileService.get_required_profile(db_session, "SEC_E")
    assert profile.pin_column == 0
    assert profile.partner_name_column == 1
    assert profile.invoice_number_column == 2
    assert profile.invoice_date_column == 3
    assert profile.cu_number_column == 4
    assert profile.base_amount_column == 6


def test_parse_sec_e_without_pin_file(db_session):
    file_path = Path("/home/amar-salim/Documents/Projects/kra-reconciliation-api/data/client-request add section E/SEC_E_WITHOUT_PIN_AND_NON-VAT_PIN1.CSV")
    assert file_path.exists(), f"Sample file not found at {file_path}"

    with open(file_path, "rb") as f:
        upload_file = UploadFile(filename="SEC_E_WITHOUT_PIN_AND_NON-VAT_PIN1.CSV", file=f)
        response = kra_service.parse_kra_csv(upload_file, db_session)

    assert response.errors_count == 0
    assert response.rows == 28
    assert response.parsed == 28
    assert len(response.invoices) == 28

    for inv in response.invoices:
        assert inv.vat_group == "EXEMPT"
        assert inv.invoice_number != ""
        assert inv.cu_number != ""
        assert inv.base_amount is not None


def test_parse_sec_e_with_vat_pin_file(db_session):
    file_path = Path("/home/amar-salim/Documents/Projects/kra-reconciliation-api/data/client-request add section E/SEC_E_WITH_VAT_PIN1.CSV")
    assert file_path.exists(), f"Sample file not found at {file_path}"

    with open(file_path, "rb") as f:
        upload_file = UploadFile(filename="SEC_E_WITH_VAT_PIN1.CSV", file=f)
        response = kra_service.parse_kra_csv(upload_file, db_session)

    assert response.errors_count == 0
    assert response.rows == 707
    assert response.parsed == 707
    assert len(response.invoices) == 707

    for inv in response.invoices:
        assert inv.vat_group == "EXEMPT"
        assert inv.pin != ""
        assert isinstance(inv.partner_name, str)
        assert inv.invoice_number != ""
        assert inv.cu_number != ""
