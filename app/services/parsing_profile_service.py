from typing import Dict, Optional
from sqlalchemy.orm import Session
from app.schemas.settings import KRAParsingProfileItem, KRAParsingProfilesConfig

class ParsingProfileError(Exception):
    pass

# NOTE: Column indexes below follow the documented standard KRA ETIMS export layout.
# They are best-guess defaults — VERIFY against a real KRA export before relying on them.
DEFAULT_PARSING_PROFILES: Dict[str, KRAParsingProfileItem] = {
    "SEC_B": KRAParsingProfileItem(
        pin_column=0, partner_name_column=1, invoice_number_column=2,
        invoice_date_column=3, cu_number_column=4, base_amount_column=6
    ),
    # D2 (Exports) verified against a real export, 2026-08-17. Exports carry no local
    # PIN and often no customer name — both columns are legitimately blank — and the
    # amount sits at index 11, well right of the other sales sections.
    "SEC_D2": KRAParsingProfileItem(
        pin_column=0, partner_name_column=1, invoice_number_column=2,
        invoice_date_column=3, cu_number_column=4, base_amount_column=11
    ),
    "SEC_E": KRAParsingProfileItem(
        pin_column=0, partner_name_column=1, invoice_number_column=2,
        invoice_date_column=3, cu_number_column=4, base_amount_column=6
    ),
    "SEC_F": KRAParsingProfileItem(
        pin_column=1, partner_name_column=2, invoice_number_column=None,
        invoice_date_column=3, cu_number_column=4, base_amount_column=7
    ),
    "SEC_G": KRAParsingProfileItem(
        pin_column=1, partner_name_column=2, invoice_number_column=None,
        invoice_date_column=3, cu_number_column=4, base_amount_column=7
    ),
    "SEC_H": KRAParsingProfileItem(
        pin_column=1, partner_name_column=2, invoice_number_column=None,
        invoice_date_column=3, cu_number_column=4, base_amount_column=8
    ),
    "SEC_I": KRAParsingProfileItem(
        pin_column=1, partner_name_column=2, invoice_number_column=None,
        invoice_date_column=3, cu_number_column=4, base_amount_column=7
    ),
}

class ParsingProfileService:
    _cached_profiles: Optional[KRAParsingProfilesConfig] = None
    _cached_version: int = 0

    @classmethod
    def get_profiles(cls, db: Session, company_id: Optional[int] = None) -> KRAParsingProfilesConfig:
        """Fetches the parsing profiles from the company's settings, using an in-memory
        cache based on the setting version. Falls back to defaults when no company is given."""
        from app.services.settings_service import SettingsService

        if company_id is None:
            return KRAParsingProfilesConfig(profiles=cls._get_default_profiles())

        setting = SettingsService.get_or_create_company_settings(db, company_id)

        # If cache is valid, return it
        if cls._cached_profiles and cls._cached_version == setting.version:
            return cls._cached_profiles

        # Fallback to defaults if empty
        if not setting.kra_parsing_profiles:
            defaults = cls._get_default_profiles()
            # We don't save it to DB here to avoid transaction side-effects during read.
            # It will be saved if the user updates settings.
            cls._cached_profiles = KRAParsingProfilesConfig(profiles=defaults)
        else:
            try:
                cls._cached_profiles = KRAParsingProfilesConfig(**setting.kra_parsing_profiles)
            except Exception as e:
                raise ParsingProfileError(f"Failed to parse KRA parsing profiles JSON: {e}")

        cls._cached_version = setting.version
        return cls._cached_profiles

    @classmethod
    def get_required_profile(cls, db: Session, section_prefix: str, company_id: Optional[int] = None) -> KRAParsingProfileItem:
        """Looks up the parsing profile for a specific section (e.g., 'SEC_B')."""
        config = cls.get_profiles(db, company_id)
        prefix_upper = section_prefix.strip().upper()
        if prefix_upper in config.profiles:
            return config.profiles[prefix_upper]
        if prefix_upper in DEFAULT_PARSING_PROFILES:
            return DEFAULT_PARSING_PROFILES[prefix_upper]
        raise ParsingProfileError(f"Unknown KRA section '{prefix_upper}'. Configure a parsing profile before importing this file.")

    @classmethod
    def _get_default_profiles(cls) -> Dict[str, KRAParsingProfileItem]:
        return dict(DEFAULT_PARSING_PROFILES)

    @classmethod
    def seed_default_profiles(cls, db: Session, company_id: Optional[int] = None) -> None:
        """Idempotently persist the default KRA parsing profiles into the company settings.

        Only fills the column when empty; never overwrites operator-customized values.
        A None company_id is a no-op (no global settings row is maintained).
        """
        if company_id is None:
            return
        from app.services.settings_service import SettingsService
        setting = SettingsService.get_or_create_company_settings(db, company_id)
        if setting.kra_parsing_profiles:
            return
        config = KRAParsingProfilesConfig(
            schema_version=1,
            profiles={k: v.model_dump() for k, v in DEFAULT_PARSING_PROFILES.items()},
        )
        setting.kra_parsing_profiles = config.model_dump()
        setting.version += 1
        db.commit()
