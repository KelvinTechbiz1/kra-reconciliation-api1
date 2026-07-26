from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.import_profile import ImportProfile, ProfileScope, SourceFormat
from app.schemas.import_profile import (
    CanonicalColumnMappingSchema,
    ImportProfileCreate,
    ImportProfileSnapshot,
    ImportProfileUpdate,
    ParsingHintsSchema,
    PurchasesValidationRulesSchema,
    SalesValidationRulesSchema,
)
from app.schemas.invoice import ReconciliationType


# Built-in Default Profile Configurations
DEFAULT_BUILTIN_PROFILES = [
    {
        "name": "Zoho Books - Sales",
        "module": ReconciliationType.SALES,
        "provider": "ZOHO",
        "description": "Standard export format for Zoho Books Sales Invoices.",
        "source_format": SourceFormat.CSV,
        "parsing_hints": ParsingHintsSchema(has_header=True, header_row=1, data_start_row=2, delimiter=",").model_dump(),
        "column_mapping": CanonicalColumnMappingSchema(
            pin=["Customer PIN", "GST/VAT PIN", "PIN", "Tax Number"],
            partner_name=["Customer Name", "Customer", "Client Name"],
            invoice_number=["Invoice Number", "Invoice No", "Invoice #", "DocNum"],
            invoice_date=["Invoice Date", "Date"],
            cu_number=["CU Number", "ETR Number", "Control Unit No", "CU Serial"],
            vat_group=["Tax Rate", "VAT Code", "VAT Group", "Tax Type"],
            base_amount=["SubTotal", "Taxable Amount", "Base Amount", "Amount"],
        ).model_dump(),
        "validation_rules": SalesValidationRulesSchema().model_dump(),
        "is_builtin": True,
        "is_default": True,
    },
    {
        "name": "Zoho Books - Purchases",
        "module": ReconciliationType.PURCHASES,
        "provider": "ZOHO",
        "description": "Standard export format for Zoho Books Purchase Bills.",
        "source_format": SourceFormat.CSV,
        "parsing_hints": ParsingHintsSchema(has_header=True, header_row=1, data_start_row=2, delimiter=",").model_dump(),
        "column_mapping": CanonicalColumnMappingSchema(
            pin=["Vendor PIN", "Supplier PIN", "GST/VAT PIN", "Tax Number"],
            partner_name=["Vendor Name", "Supplier Name", "Vendor", "Supplier"],
            invoice_number=["Bill Number", "Bill No", "Invoice Number", "Invoice No"],
            invoice_date=["Bill Date", "Invoice Date", "Date"],
            cu_number=["CU Number", "ETR Number", "Control Unit No"],
            vat_group=["Tax Rate", "VAT Code", "VAT Group"],
            base_amount=["SubTotal", "Taxable Amount", "Base Amount", "Amount"],
        ).model_dump(),
        "validation_rules": PurchasesValidationRulesSchema().model_dump(),
        "is_builtin": True,
        "is_default": True,
    },
    {
        "name": "QuickBooks Online - Sales",
        "module": ReconciliationType.SALES,
        "provider": "QUICKBOOKS",
        "description": "Standard export format for QuickBooks Online Sales Invoices.",
        "source_format": SourceFormat.CSV,
        "parsing_hints": ParsingHintsSchema(has_header=True, header_row=1, data_start_row=2, delimiter=",").model_dump(),
        "column_mapping": CanonicalColumnMappingSchema(
            pin=["Tax Reg No", "Customer Tax PIN", "PIN"],
            partner_name=["Customer", "Customer Name"],
            invoice_number=["No.", "Invoice No", "Doc Number"],
            invoice_date=["Date", "Transaction Date", "Invoice Date"],
            cu_number=["CU Number", "ETR No", "Memo"],
            vat_group=["Tax Code", "Tax Rate"],
            base_amount=["Amount", "Subtotal", "Taxable Amount"],
        ).model_dump(),
        "validation_rules": SalesValidationRulesSchema().model_dump(),
        "is_builtin": True,
        "is_default": False,
    },
    {
        "name": "Generic ERP Template - Sales",
        "module": ReconciliationType.SALES,
        "provider": "GENERIC",
        "description": "Universal Sales CSV template format.",
        "source_format": SourceFormat.CSV,
        "parsing_hints": ParsingHintsSchema(has_header=True, header_row=1, data_start_row=2, delimiter=",").model_dump(),
        "column_mapping": CanonicalColumnMappingSchema(
            pin=["Customer PIN", "PIN"],
            partner_name=["Customer Name", "Customer"],
            invoice_number=["Invoice Number", "Invoice No"],
            invoice_date=["Invoice Date", "Date"],
            cu_number=["CU Number", "ETR Number"],
            vat_group=["VAT Group", "Tax Rate"],
            base_amount=["Base Amount", "Taxable Amount"],
        ).model_dump(),
        "validation_rules": SalesValidationRulesSchema().model_dump(),
        "is_builtin": True,
        "is_default": False,
    },
    {
        "name": "Generic ERP Template - Purchases",
        "module": ReconciliationType.PURCHASES,
        "provider": "GENERIC",
        "description": "Universal Purchases CSV template format.",
        "source_format": SourceFormat.CSV,
        "parsing_hints": ParsingHintsSchema(has_header=True, header_row=1, data_start_row=2, delimiter=",").model_dump(),
        "column_mapping": CanonicalColumnMappingSchema(
            pin=["Supplier PIN", "PIN"],
            partner_name=["Supplier Name", "Supplier"],
            invoice_number=["Invoice Number", "Invoice No"],
            invoice_date=["Invoice Date", "Date"],
            cu_number=["CU Number", "ETR Number"],
            vat_group=["VAT Group", "Tax Rate"],
            base_amount=["Base Amount", "Taxable Amount"],
        ).model_dump(),
        "validation_rules": PurchasesValidationRulesSchema().model_dump(),
        "is_builtin": True,
        "is_default": False,
    },
]


class ERPProfileService:
    @classmethod
    def seed_builtin_profiles(cls, db: Session) -> None:
        """Idempotently seed standard built-in ERP import profiles."""
        from app.database.base import Base
        try:
            Base.metadata.create_all(bind=db.get_bind())
        except Exception:
            pass

        for item in DEFAULT_BUILTIN_PROFILES:

            existing = db.query(ImportProfile).filter(
                ImportProfile.scope == ProfileScope.BUILTIN,
                ImportProfile.module == item["module"],
                ImportProfile.name == item["name"],
            ).first()
            if not existing:
                profile = ImportProfile(
                    company_id=None,
                    scope=ProfileScope.BUILTIN,
                    name=item["name"],
                    module=item["module"],
                    provider=item["provider"],
                    description=item["description"],
                    source_format=item["source_format"],
                    parsing_hints=item["parsing_hints"],
                    column_mapping=item["column_mapping"],
                    validation_rules=item["validation_rules"],
                    is_builtin=True,
                    is_default=item["is_default"],
                    is_active=True,
                    version=1,
                )
                db.add(profile)
        db.commit()

    @classmethod
    def list_profiles(
        cls, db: Session, company_id: Optional[int], module: Optional[ReconciliationType] = None
    ) -> List[ImportProfile]:
        """Returns profiles visible to company sorted by precedence (Company Default -> Company -> Builtin)."""
        query = db.query(ImportProfile).filter(ImportProfile.is_active == True)

        if company_id is not None:
            query = query.filter(
                (ImportProfile.company_id == company_id) | (ImportProfile.scope == ProfileScope.BUILTIN)
            )
        else:
            query = query.filter(ImportProfile.scope == ProfileScope.BUILTIN)

        if module:
            query = query.filter(ImportProfile.module == module)

        profiles = query.all()

        # Sort profiles deterministically:
        # 1. Company Default
        # 2. Company Custom profiles (newest first)
        # 3. Builtin Presets
        def sort_key(p: ImportProfile):
            is_company_default = 0 if (p.company_id == company_id and p.is_default) else 1
            is_company = 0 if p.company_id == company_id else 1
            created_ts = -p.created_at.timestamp() if p.created_at else 0
            return (is_company_default, is_company, created_ts)

        return sorted(profiles, key=sort_key)

    @classmethod
    def get_profile(cls, db: Session, profile_id: int, company_id: Optional[int] = None) -> Optional[ImportProfile]:
        query = db.query(ImportProfile).filter(ImportProfile.id == profile_id, ImportProfile.is_active == True)
        if company_id is not None:
            query = query.filter(
                (ImportProfile.company_id == company_id) | (ImportProfile.scope == ProfileScope.BUILTIN)
            )
        return query.first()

    @classmethod
    def create_profile(cls, db: Session, company_id: int, payload: ImportProfileCreate) -> ImportProfile:
        existing = db.query(ImportProfile).filter(
            ImportProfile.company_id == company_id,
            ImportProfile.module == payload.module,
            ImportProfile.name == payload.name.strip(),
            ImportProfile.is_active == True,
        ).first()
        if existing:
            raise ValueError(f"An active import profile named '{payload.name}' already exists for {payload.module.value}.")

        if payload.is_default:
            db.query(ImportProfile).filter(
                ImportProfile.company_id == company_id,
                ImportProfile.module == payload.module,
            ).update({"is_default": False}, synchronize_session=False)

        profile = ImportProfile(
            company_id=company_id,
            scope=ProfileScope.COMPANY,
            name=payload.name.strip(),
            module=payload.module,
            provider=payload.provider.strip().upper(),
            description=payload.description,
            source_format=payload.source_format,
            parsing_hints=payload.parsing_hints.model_dump(),
            column_mapping=payload.column_mapping.model_dump(),
            validation_rules=payload.validation_rules.model_dump(),
            is_builtin=False,
            is_default=payload.is_default,
            is_active=True,
            version=1,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile

    @classmethod
    def update_profile(
        cls, db: Session, profile_id: int, company_id: int, payload: ImportProfileUpdate
    ) -> ImportProfile:
        profile = db.query(ImportProfile).filter(
            ImportProfile.id == profile_id,
            ImportProfile.company_id == company_id,
            ImportProfile.is_active == True,
        ).with_for_update().first()

        if not profile:
            raise ValueError("Import profile not found, inactive, or belongs to system built-in presets.")

        if payload.name and payload.name.strip() != profile.name:
            dup = db.query(ImportProfile).filter(
                ImportProfile.company_id == company_id,
                ImportProfile.module == profile.module,
                ImportProfile.name == payload.name.strip(),
                ImportProfile.id != profile_id,
                ImportProfile.is_active == True,
            ).first()
            if dup:
                raise ValueError(f"An import profile named '{payload.name}' already exists.")
            profile.name = payload.name.strip()

        if payload.provider is not None:
            profile.provider = payload.provider.strip().upper()
        if payload.description is not None:
            profile.description = payload.description
        if payload.source_format is not None:
            profile.source_format = payload.source_format
        if payload.parsing_hints is not None:
            profile.parsing_hints = payload.parsing_hints.model_dump()
        if payload.column_mapping is not None:
            profile.column_mapping = payload.column_mapping.model_dump()
        if payload.validation_rules is not None:
            profile.validation_rules = payload.validation_rules.model_dump()

        if payload.is_default is True:
            db.query(ImportProfile).filter(
                ImportProfile.company_id == company_id,
                ImportProfile.module == profile.module,
                ImportProfile.id != profile_id,
            ).update({"is_default": False}, synchronize_session=False)
            profile.is_default = True
        elif payload.is_default is False:
            profile.is_default = False

        if payload.is_active is not None:
            profile.is_active = payload.is_active
            if not payload.is_active:
                profile.archived_at = datetime.now(timezone.utc)

        profile.version += 1
        db.commit()
        db.refresh(profile)
        return profile

    @classmethod
    def set_default_profile(cls, db: Session, company_id: int, profile_id: int) -> ImportProfile:
        with db.begin_nested():
            profile = db.query(ImportProfile).filter(
                ImportProfile.id == profile_id,
                (ImportProfile.company_id == company_id) | (ImportProfile.scope == ProfileScope.BUILTIN),
                ImportProfile.is_active == True,
            ).with_for_update().first()

            if not profile:
                raise ValueError("Import profile not found or inactive.")

            # Clear previous defaults for this company & module
            db.query(ImportProfile).filter(
                ImportProfile.company_id == company_id,
                ImportProfile.module == profile.module,
                ImportProfile.id != profile_id,
            ).update({"is_default": False}, synchronize_session=False)

            profile.is_default = True

        db.commit()
        db.refresh(profile)
        return profile

    @classmethod
    def clone_profile(cls, db: Session, source_profile_id: int, company_id: int, new_name: Optional[str] = None) -> ImportProfile:
        source = db.query(ImportProfile).filter(
            ImportProfile.id == source_profile_id,
            ImportProfile.is_active == True,
        ).first()

        if not source:
            raise ValueError(f"Source import profile ID {source_profile_id} not found.")

        target_name = (new_name or f"{source.name} (Copy)").strip()
        dup = db.query(ImportProfile).filter(
            ImportProfile.company_id == company_id,
            ImportProfile.module == source.module,
            ImportProfile.name == target_name,
            ImportProfile.is_active == True,
        ).first()
        if dup:
            target_name = f"{target_name} ({int(datetime.now().timestamp())})"

        cloned = ImportProfile(
            company_id=company_id,
            scope=ProfileScope.COMPANY,
            name=target_name,
            module=source.module,
            provider=source.provider,
            description=f"Cloned from {source.name}",
            source_format=source.source_format,
            parsing_hints=source.parsing_hints,
            column_mapping=source.column_mapping,
            validation_rules=source.validation_rules,
            is_builtin=False,
            is_default=False,
            is_active=True,
            version=1,
        )
        db.add(cloned)
        db.commit()
        db.refresh(cloned)
        return cloned

    @classmethod
    def resolve_profile_for_import(
        cls, db: Session, company_id: Optional[int], module: ReconciliationType, explicit_profile_id: Optional[int] = None
    ) -> ImportProfile:
        # Rule 1: Explicit profile_id if provided
        if explicit_profile_id is not None:
            p = db.query(ImportProfile).filter(
                ImportProfile.id == explicit_profile_id, ImportProfile.is_active == True
            ).first()
            if p:
                return p
            raise ValueError(f"Specified import profile ID {explicit_profile_id} was not found or is inactive.")

        if company_id is not None:
            # Rule 2: Active Company Default for module
            p = db.query(ImportProfile).filter(
                ImportProfile.company_id == company_id,
                ImportProfile.module == module,
                ImportProfile.is_default == True,
                ImportProfile.is_active == True,
            ).first()
            if p:
                return p

            # Rule 3: Most recently updated active company profile for module
            p = db.query(ImportProfile).filter(
                ImportProfile.company_id == company_id,
                ImportProfile.module == module,
                ImportProfile.is_active == True,
            ).order_by(ImportProfile.updated_at.desc()).first()
            if p:
                return p

        # Rule 4: Active System Built-in Preset matching module
        p = db.query(ImportProfile).filter(
            ImportProfile.scope == ProfileScope.BUILTIN,
            ImportProfile.module == module,
            ImportProfile.is_active == True,
        ).order_by(ImportProfile.is_default.desc(), ImportProfile.id.asc()).first()
        if p:
            return p

        raise RuntimeError(f"No valid import profile found for module '{module.value}'.")

    @classmethod
    def create_snapshot(cls, profile: ImportProfile) -> ImportProfileSnapshot:
        """Generates an immutable Pydantic snapshot from an ImportProfile model instance."""
        rules = profile.validation_rules
        if profile.module == ReconciliationType.SALES:
            typed_rules = SalesValidationRulesSchema(**rules)
        else:
            typed_rules = PurchasesValidationRulesSchema(**rules)

        return ImportProfileSnapshot(
            profile_id=profile.id,
            profile_name=profile.name,
            profile_version=profile.version,
            module=profile.module,
            provider=profile.provider,
            source_format=profile.source_format,
            parsing_hints=ParsingHintsSchema(**profile.parsing_hints),
            column_mapping=CanonicalColumnMappingSchema(**profile.column_mapping),
            validation_rules=typed_rules,
            snapshot_timestamp=datetime.now(timezone.utc),
        )
