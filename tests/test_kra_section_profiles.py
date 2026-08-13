import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from pydantic import ValidationError

from app.database.base import Base
from app.models.settings import KRAVATMapping, CompanySetting
from app.schemas.settings import KRAParsingProfilesConfig, KRAParsingProfileItem
from app.services.parsing_profile_service import ParsingProfileService, ParsingProfileError
from app.services.settings_service import SettingsService

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_profiles_db.db"
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


def test_custom_section_profile_schema_validation():
    # Valid custom section profiles: SEC_J, SEC_J1, SEC_SPECIAL
    valid_data = {
        "schema_version": 1,
        "profiles": {
            "SEC_J": KRAParsingProfileItem(
                pin_column=0, partner_name_column=1, invoice_number_column=2,
                invoice_date_column=3, cu_number_column=4, base_amount_column=6
            ),
            "SEC_J1": KRAParsingProfileItem(
                pin_column=1, partner_name_column=2, invoice_number_column=None,
                invoice_date_column=3, cu_number_column=4, base_amount_column=7
            )
        }
    }
    config = KRAParsingProfilesConfig(**valid_data)
    assert "SEC_J" in config.profiles
    assert "SEC_J1" in config.profiles

    # Invalid section prefix format should raise ValidationError
    with pytest.raises(ValidationError):
        KRAParsingProfilesConfig(
            profiles={
                "INVALID_PREFIX": KRAParsingProfileItem(
                    pin_column=0, partner_name_column=1, invoice_number_column=2,
                    invoice_date_column=3, cu_number_column=4, base_amount_column=6
                )
            }
        )


def test_add_and_retrieve_custom_section_profile(db_session):
    company_id = 1
    setting = SettingsService.get_or_create_company_settings(db_session, company_id)

    # 1. Update company settings to include SEC_J profile
    updated_profiles = dict(setting.kra_parsing_profiles.get("profiles", {}))
    updated_profiles["SEC_J"] = {
        "pin_column": 0,
        "partner_name_column": 1,
        "invoice_number_column": 2,
        "invoice_date_column": 3,
        "cu_number_column": 4,
        "base_amount_column": 6
    }
    setting.kra_parsing_profiles = {
        "schema_version": 1,
        "profiles": updated_profiles
    }
    setting.version += 1
    db_session.commit()

    # 2. Retrieve profile via ParsingProfileService for SEC_J
    profile_j = ParsingProfileService.get_required_profile(db_session, "SEC_J", company_id=company_id)
    assert profile_j.pin_column == 0
    assert profile_j.base_amount_column == 6


def test_delete_custom_section_profile(db_session):
    company_id = 2
    setting = SettingsService.get_or_create_company_settings(db_session, company_id)

    # Add SEC_J
    updated_profiles = dict(setting.kra_parsing_profiles.get("profiles", {}))
    updated_profiles["SEC_J"] = {
        "pin_column": 0, "partner_name_column": 1, "invoice_number_column": 2,
        "invoice_date_column": 3, "cu_number_column": 4, "base_amount_column": 6
    }
    setting.kra_parsing_profiles = {"schema_version": 1, "profiles": updated_profiles}
    setting.version += 1
    db_session.commit()

    # Verify present
    prof = ParsingProfileService.get_required_profile(db_session, "SEC_J", company_id=company_id)
    assert prof is not None

    # Delete SEC_J
    del updated_profiles["SEC_J"]
    setting.kra_parsing_profiles = {"schema_version": 1, "profiles": updated_profiles}
    setting.version += 1
    db_session.commit()

    # Expect ParsingProfileError for SEC_J now
    with pytest.raises(ParsingProfileError):
        ParsingProfileService.get_required_profile(db_session, "SEC_J", company_id=company_id)


def test_parse_custom_section_csv_requires_vat_mapping(db_session):
    from fastapi import UploadFile
    import io
    from app.services import kra_service

    company_id = 3
    setting = SettingsService.get_or_create_company_settings(db_session, company_id)

    # 1. Add parsing profile for SEC_J
    updated_profiles = dict(setting.kra_parsing_profiles.get("profiles", {}))
    updated_profiles["SEC_J"] = {
        "pin_column": 0, "partner_name_column": 1, "invoice_number_column": 2,
        "invoice_date_column": 3, "cu_number_column": 4, "base_amount_column": 6
    }
    setting.kra_parsing_profiles = {"schema_version": 1, "profiles": updated_profiles}
    setting.version += 1
    db_session.commit()

    csv_data = b"PIN,Customer,Invoice,Date,CU,VAT,Amount\nP051393568M,Test Customer,INV-001,02/03/2026,|0190439340000000455,16,1000.00\n"
    upload_file = UploadFile(filename="SEC_J_CUSTOM_FILE.csv", file=io.BytesIO(csv_data))

    # 2. Before VAT mapping is added: expect HTTP 400 with detail asking user to add VAT mapping
    with pytest.raises(HTTPException) as exc_info:
        kra_service.parse_kra_csv(upload_file, db_session, company_id=company_id)
    assert exc_info.value.status_code == 400
    assert "No KRA VAT mapping configured for section 'SEC_J'" in exc_info.value.detail

    # 3. Add VAT mapping for SEC_J
    db_session.add(KRAVATMapping(section_prefix="SEC_J", canonical_rate="16", description="J - Custom Section 16%"))
    db_session.commit()

    # 4. Re-upload SEC_J: now parses successfully!
    upload_file.file.seek(0)
    res = kra_service.parse_kra_csv(upload_file, db_session, company_id=company_id)
    assert res.parsed == 1
    assert res.errors_count == 0
    assert len(res.invoices) == 1

