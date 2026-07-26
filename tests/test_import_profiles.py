import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.company import Company
from app.models.import_profile import ImportProfile, ProfileScope, SourceFormat
from app.schemas.import_profile import (
    CanonicalColumnMappingSchema,
    ImportProfileCreate,
    ImportProfileUpdate,
    ParsingHintsSchema,
    SalesValidationRulesSchema,
)
from app.schemas.invoice import ReconciliationType
from app.services.erp_profile_service import ERPProfileService

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_profiles_db.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(name="db_session", scope="function")
def fixture_db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        company = Company(name="Test Company")
        db.add(company)
        db.commit()
        db.refresh(company)
        yield db, company
    finally:
        db.close()


def test_seed_builtin_profiles(db_session):
    db, company = db_session
    ERPProfileService.seed_builtin_profiles(db)
    builtins = db.query(ImportProfile).filter(ImportProfile.scope == ProfileScope.BUILTIN).all()
    assert len(builtins) >= 5
    names = [b.name for b in builtins]
    assert "Zoho Books - Sales" in names
    assert "Zoho Books - Purchases" in names


def test_create_and_update_import_profile(db_session):
    db, company = db_session
    ERPProfileService.seed_builtin_profiles(db)

    payload = ImportProfileCreate(
        name="Custom Zoho Sales",
        module=ReconciliationType.SALES,
        provider="ZOHO",
        description="Test profile",
        source_format=SourceFormat.CSV,
        parsing_hints=ParsingHintsSchema(),
        column_mapping=CanonicalColumnMappingSchema(pin=["Customer Tax PIN", "PIN"]),
        validation_rules=SalesValidationRulesSchema(),
        is_default=True,
    )

    profile = ERPProfileService.create_profile(db, company.id, payload)
    assert profile.id is not None
    assert profile.name == "Custom Zoho Sales"
    assert profile.is_default is True
    assert profile.version == 1

    # Update profile
    updated = ERPProfileService.update_profile(
        db, profile.id, company.id, ImportProfileUpdate(description="Updated description")
    )
    assert updated.description == "Updated description"
    assert updated.version == 2


def test_clone_profile(db_session):
    db, company = db_session
    ERPProfileService.seed_builtin_profiles(db)
    builtin = db.query(ImportProfile).filter(
        ImportProfile.scope == ProfileScope.BUILTIN,
        ImportProfile.name == "Zoho Books - Sales",
    ).first()

    cloned = ERPProfileService.clone_profile(db, builtin.id, company.id, new_name="My Company Zoho Sales")
    assert cloned.id != builtin.id
    assert cloned.scope == ProfileScope.COMPANY
    assert cloned.company_id == company.id
    assert cloned.name == "My Company Zoho Sales"
    assert cloned.provider == "ZOHO"


def test_atomic_default_reset_and_precedence(db_session):
    db, company = db_session
    ERPProfileService.seed_builtin_profiles(db)
    cid = company.id

    # Create profile 1 (default)
    p1 = ERPProfileService.create_profile(
        db,
        cid,
        ImportProfileCreate(
            name="Profile One",
            module=ReconciliationType.SALES,
            provider="CUSTOM",
            validation_rules=SalesValidationRulesSchema(),
            is_default=True,
        ),
    )
    assert p1.is_default is True

    # Create profile 2 (default) -> should reset p1 default
    p2 = ERPProfileService.create_profile(
        db,
        cid,
        ImportProfileCreate(
            name="Profile Two",
            module=ReconciliationType.SALES,
            provider="CUSTOM",
            validation_rules=SalesValidationRulesSchema(),
            is_default=True,
        ),
    )
    db.refresh(p1)
    assert p2.is_default is True
    assert p1.is_default is False

    # Resolve default profile deterministically
    resolved = ERPProfileService.resolve_profile_for_import(db, cid, ReconciliationType.SALES)
    assert resolved.id == p2.id
