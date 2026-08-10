import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.settings import (
    BaseAmountPolicy,
    CompanySAPConnection,
    CompanySetting,
    SettingAuditLog,
    UnmappedVatPolicy,
    PurchaseCUField,
    VATMapping,
    KRAVATMapping,
    VatModule,
)
from app.models.user import User
from app.schemas.settings import (
    SAPConnectionCreate,
    SAPConnectionResponse,
    SAPConnectionUpdate,
    SettingsCompositeResponse,
    StepResult,
    SystemSettingsResponse,
    SystemSettingsUpdate,
    TestConnectionRequest,
    TestConnectionResponse,
    VATMappingItem,
    VATMappingsUpdatePayload,
    KRAVATMappingItem,
    KRAVATMappingsUpdatePayload,
)


# Default built-in VAT codes for seeding newly initialized SAP connections
DEFAULT_BUILTIN_VAT_MAPPINGS = [
    {"module": VatModule.PURCHASES, "sap_code": "I1", "description": "Standard Input VAT 16%", "canonical_rate": "16"},
    {"module": VatModule.PURCHASES, "sap_code": "I2", "description": "Zero Rated Input VAT 0%", "canonical_rate": "0"},
    {"module": VatModule.PURCHASES, "sap_code": "I3", "description": "Reduced Input VAT 8%", "canonical_rate": "8"},
    {"module": VatModule.PURCHASES, "sap_code": "X1", "description": "Exempt Input VAT", "canonical_rate": "EXEMPT"},
    {"module": VatModule.PURCHASES, "sap_code": "N2", "description": "Non-Deductible Input VAT 16%", "canonical_rate": "16"},
    {"module": VatModule.SALES, "sap_code": "O1", "description": "Standard Output VAT 16%", "canonical_rate": "16"},
    {"module": VatModule.SALES, "sap_code": "O2", "description": "Zero Rated Output VAT 0%", "canonical_rate": "0"},
    {"module": VatModule.SALES, "sap_code": "X0", "description": "Exempt Output VAT", "canonical_rate": "EXEMPT"},
]


DEFAULT_KRA_PARSING_PROFILES = {
    "schema_version": 1,
    "profiles": {
        "SEC_B": {"pin_column": 0, "partner_name_column": 1, "invoice_number_column": 2, "invoice_date_column": 3, "cu_number_column": 4, "base_amount_column": 6},
        "SEC_E": {"pin_column": 0, "partner_name_column": 1, "invoice_number_column": 2, "invoice_date_column": 3, "cu_number_column": 4, "base_amount_column": 6},
        "SEC_F": {"pin_column": 1, "partner_name_column": 2, "invoice_number_column": None, "invoice_date_column": 3, "cu_number_column": 4, "base_amount_column": 7},
        "SEC_G": {"pin_column": 1, "partner_name_column": 2, "invoice_number_column": None, "invoice_date_column": 3, "cu_number_column": 4, "base_amount_column": 7},
        "SEC_H": {"pin_column": 1, "partner_name_column": 2, "invoice_number_column": None, "invoice_date_column": 3, "cu_number_column": 4, "base_amount_column": 8},
        "SEC_I": {"pin_column": 1, "partner_name_column": 2, "invoice_number_column": None, "invoice_date_column": 3, "cu_number_column": 4, "base_amount_column": 7},
    },
}


class SettingsConflictError(Exception):
    """Raised on optimistic locking version mismatch."""
    pass


class SettingsService:
    # ------------------------------------------------------------------ #
    # Per-company settings retrieval / creation
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_or_create_company_settings(db: Session, company_id: int) -> CompanySetting:
        setting = (
            db.query(CompanySetting)
            .filter(CompanySetting.company_id == company_id)
            .first()
        )
        if setting is None:
            setting = CompanySetting(
                company_id=company_id,
                amount_tolerance=Decimal("10.00"),
                base_amount_policy=BaseAmountPolicy.ALLOW,
                unmapped_vat_policy=UnmappedVatPolicy.NEEDS_REVIEW,
                ignore_missing_cu=False,
                include_credit_notes=True,
                include_debit_notes=True,
                skip_cancelled=True,
                sales_cu_source="U_CUINV",
                purchase_cu_source="U_CUINV",
                version=1,
                kra_parsing_profiles=DEFAULT_KRA_PARSING_PROFILES,
            )
            db.add(setting)
            db.commit()
            db.refresh(setting)
        return setting

    @staticmethod
    def get_active_connection(db: Session, company_id: int) -> Optional[CompanySAPConnection]:
        setting = SettingsService.get_or_create_company_settings(db, company_id)
        if setting.active_connection_id:
            conn = (
                db.query(CompanySAPConnection)
                .filter(CompanySAPConnection.id == setting.active_connection_id)
                .first()
            )
            if conn and conn.is_active:
                return conn
        # Fall back to first active connection for the company
        return (
            db.query(CompanySAPConnection)
            .filter(
                CompanySAPConnection.company_id == company_id,
                CompanySAPConnection.is_active == True,  # noqa: E712
            )
            .first()
        )

    # ------------------------------------------------------------------ #
    # Seeding helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def seed_default_vat_mappings(cls, db: Session, connection_id: int):
        existing_codes = {
            (m.module, m.sap_code)
            for m in db.query(VATMapping).filter(VATMapping.connection_id == connection_id).all()
        }
        to_add = []
        for m in DEFAULT_BUILTIN_VAT_MAPPINGS:
            key = (m["module"], m["sap_code"])
            if key not in existing_codes:
                to_add.append(
                    VATMapping(
                        connection_id=connection_id,
                        module=m["module"],
                        sap_code=m["sap_code"],
                        description=m["description"],
                        canonical_rate=m["canonical_rate"],
                        is_builtin=True,
                        is_system_generated=True,
                    )
                )
        if to_add:
            db.add_all(to_add)
            db.commit()

    @classmethod
    def seed_default_kra_section_profiles(cls, db: Session):
        defaults = [
            {"section_prefix": "SEC_B", "canonical_rate": "16", "description": "B – General Rated Supplies (Sales) 16%"},
            {"section_prefix": "SEC_E", "canonical_rate": "EXEMPT", "description": "E – Exempt Sales (eTIMS/TIMS) Exempt"},
            {"section_prefix": "SEC_F", "canonical_rate": "16", "description": "F – General Rated Purchases (local) 16%"},
            {"section_prefix": "SEC_G", "canonical_rate": "8", "description": "G – Other Rated Purchases 8% (Petroleum)"},
            {"section_prefix": "SEC_H", "canonical_rate": "0", "description": "H – Zero-Rated Purchases 0%"},
            {"section_prefix": "SEC_I", "canonical_rate": "EXEMPT", "description": "I – Exempt Purchases Exempt"},
        ]
        existing = {m.section_prefix.strip().upper(): m for m in db.query(KRAVATMapping).all()}
        to_add = []
        for d in defaults:
            prefix = d["section_prefix"].upper()
            if prefix not in existing:
                to_add.append(KRAVATMapping(**d))
            else:
                item = existing[prefix]
                if prefix == "SEC_G" and item.canonical_rate == "16":
                    item.canonical_rate = "8"
                    item.description = d["description"]
                elif prefix == "SEC_I" and item.canonical_rate == "8":
                    item.canonical_rate = "EXEMPT"
                    item.description = d["description"]
        if to_add:
            db.add_all(to_add)
        db.commit()

    # ------------------------------------------------------------------ #
    # Composite (read) settings, scoped to a company
    # ------------------------------------------------------------------ #
    @classmethod
    def get_composite_settings(cls, db: Session, company_id: int) -> SettingsCompositeResponse:
        setting = cls.get_or_create_company_settings(db, company_id)
        active_conn = cls.get_active_connection(db, company_id)

        sap_conn_resp: Optional[SAPConnectionResponse] = None
        vat_mappings_items: List[VATMappingItem] = []

        if active_conn:
            cls.seed_default_vat_mappings(db, active_conn.id)
            sap_conn_resp = cls._connection_to_response(active_conn)
            raw_mappings = db.query(VATMapping).filter(VATMapping.connection_id == active_conn.id).all()
            vat_mappings_items = [VATMappingItem.model_validate(m) for m in raw_mappings]

        cls.seed_default_kra_section_profiles(db)
        raw_kra_mappings = db.query(KRAVATMapping).all()
        kra_vat_mappings_items = [KRAVATMappingItem.model_validate(m) for m in raw_kra_mappings]

        warning = None
        if setting.amount_tolerance > Decimal("1000.00"):
            warning = f"Warning: Amount tolerance (KES {setting.amount_tolerance}) exceeds KES 1,000.00. High variance will auto-match."

        sys_resp = SystemSettingsResponse(
            id=setting.id,
            company_id=setting.company_id,
            active_connection_id=setting.active_connection_id,
            amount_tolerance=setting.amount_tolerance,
            base_amount_policy=setting.base_amount_policy,
            unmapped_vat_policy=setting.unmapped_vat_policy,
            ignore_missing_cu=setting.ignore_missing_cu,
            include_credit_notes=setting.include_credit_notes,
            include_debit_notes=setting.include_debit_notes,
            skip_cancelled=setting.skip_cancelled,
            sales_cu_source=setting.sales_cu_source or "U_CUINV",
            purchase_cu_source=setting.purchase_cu_source or "U_CUINV",
            kra_parsing_profiles=setting.kra_parsing_profiles or DEFAULT_KRA_PARSING_PROFILES,
            version=setting.version,
            updated_at=setting.updated_at,
            warning=warning,
        )

        return SettingsCompositeResponse(
            sap_connection=sap_conn_resp,
            system_settings=sys_resp,
            vat_mappings=vat_mappings_items,
            kra_vat_mappings=kra_vat_mappings_items,
            is_using_env_fallback=False,
        )

    # ------------------------------------------------------------------ #
    # SAP connection management (per company)
    # ------------------------------------------------------------------ #
    @classmethod
    def save_or_update_sap_connection(
        cls,
        db: Session,
        company_id: int,
        payload: SAPConnectionUpdate,
        current_user: Optional[User] = None,
    ) -> SAPConnectionResponse:
        setting = cls.get_or_create_company_settings(db, company_id)
        active_conn = cls.get_active_connection(db, company_id)

        changes: Dict[str, Any] = {}
        user_id = current_user.id if current_user else None
        user_email = current_user.email if current_user else "system"

        if not active_conn:
            if not payload.base_url or not payload.company_db or not payload.username or not payload.password:
                raise ValueError("base_url, company_db, username, and password are required for initial SAP setup.")

            conn = CompanySAPConnection(
                company_id=company_id,
                name=payload.name or "Primary SAP Connection",
                base_url=payload.base_url,
                company_db=payload.company_db,
                username=payload.username,
                password=payload.password,
                verify_ssl=True,
                is_active=True,
                version=1,
                updated_by_id=user_id,
            )
            db.add(conn)
            db.commit()
            db.refresh(conn)

            setting.active_connection_id = conn.id
            db.commit()

            cls.seed_default_vat_mappings(db, conn.id)

            changes["connection"] = {"old": None, "new": f"Created SAP connection '{conn.name}' ({conn.base_url})"}
            cls.record_audit_log(db, company_id, user_id, user_email, "create_sap_connection", changes)

            return cls._connection_to_response(conn)

        if active_conn.version != payload.version:
            raise SettingsConflictError(
                f"Optimistic lock conflict: Connection version is {active_conn.version}, but payload supplied {payload.version}."
            )

        if payload.name is not None and payload.name != active_conn.name:
            changes["name"] = {"old": active_conn.name, "new": payload.name}
            active_conn.name = payload.name
        if payload.base_url is not None and payload.base_url != active_conn.base_url:
            changes["base_url"] = {"old": active_conn.base_url, "new": payload.base_url}
            active_conn.base_url = payload.base_url
        if payload.company_db is not None and payload.company_db != active_conn.company_db:
            changes["company_db"] = {"old": active_conn.company_db, "new": payload.company_db}
            active_conn.company_db = payload.company_db
        if payload.username is not None and payload.username != active_conn.username:
            changes["username"] = {"old": active_conn.username, "new": payload.username}
            active_conn.username = payload.username
        if not active_conn.verify_ssl:
            changes["verify_ssl"] = {"old": active_conn.verify_ssl, "new": True}
            active_conn.verify_ssl = True
        if payload.password:
            changes["password"] = {"old": "••••••••", "new": "•••••••• (Updated)"}
            active_conn.password = payload.password

        if changes:
            active_conn.version += 1
            active_conn.updated_by_id = user_id
            db.commit()
            db.refresh(active_conn)
            cls.record_audit_log(db, company_id, user_id, user_email, "update_sap_connection", changes)

        return cls._connection_to_response(active_conn)

    # ------------------------------------------------------------------ #
    # System settings management (per company)
    # ------------------------------------------------------------------ #
    @classmethod
    def update_system_settings(
        cls,
        db: Session,
        company_id: int,
        payload: SystemSettingsUpdate,
        current_user: Optional[User] = None,
    ) -> SystemSettingsResponse:
        setting = cls.get_or_create_company_settings(db, company_id)

        if setting.version != payload.version:
            raise SettingsConflictError(
                f"Optimistic lock conflict: System settings version is {setting.version}, but payload supplied {payload.version}."
            )

        changes: Dict[str, Any] = {}
        user_id = current_user.id if current_user else None
        user_email = current_user.email if current_user else "system"

        fields_to_check = [
            "amount_tolerance",
            "base_amount_policy",
            "unmapped_vat_policy",
            "ignore_missing_cu",
            "include_credit_notes",
            "include_debit_notes",
            "skip_cancelled",
            "sales_cu_source",
            "purchase_cu_source",
            "kra_parsing_profiles",
        ]

        for field_name in fields_to_check:
            if field_name not in payload.model_fields_set:
                continue
            new_val = getattr(payload, field_name)
            if hasattr(new_val, "model_dump"):
                new_val = new_val.model_dump()
            old_val = getattr(setting, field_name)
            if new_val != old_val:
                changes[field_name] = {"old": str(old_val), "new": str(new_val)}
                setattr(setting, field_name, new_val)

        if changes:
            setting.version += 1
            setting.updated_by_id = user_id
            db.commit()
            db.refresh(setting)
            cls.record_audit_log(db, company_id, user_id, user_email, "update_system_settings", changes, payload.reason)

        warning = None
        if setting.amount_tolerance > Decimal("1000.00"):
            warning = f"Warning: Amount tolerance (KES {setting.amount_tolerance}) exceeds KES 1,000.00. High variance will auto-match."

        return SystemSettingsResponse(
            id=setting.id,
            company_id=setting.company_id,
            active_connection_id=setting.active_connection_id,
            amount_tolerance=setting.amount_tolerance,
            base_amount_policy=setting.base_amount_policy,
            unmapped_vat_policy=setting.unmapped_vat_policy,
            ignore_missing_cu=setting.ignore_missing_cu,
            include_credit_notes=setting.include_credit_notes,
            include_debit_notes=setting.include_debit_notes,
            skip_cancelled=setting.skip_cancelled,
            sales_cu_source=setting.sales_cu_source or "U_CUINV",
            purchase_cu_source=setting.purchase_cu_source or "U_CUINV",
            kra_parsing_profiles=setting.kra_parsing_profiles or DEFAULT_KRA_PARSING_PROFILES,
            version=setting.version,
            updated_at=setting.updated_at,
            warning=warning,
        )

    # ------------------------------------------------------------------ #
    # VAT mappings (per company connection)
    # ------------------------------------------------------------------ #
    @classmethod
    def save_vat_mappings(
        cls,
        db: Session,
        company_id: int,
        payload: VATMappingsUpdatePayload,
        current_user: Optional[User] = None,
    ) -> List[VATMappingItem]:
        setting = cls.get_or_create_company_settings(db, company_id)
        active_conn = cls.get_active_connection(db, company_id)

        conn_id = payload.connection_id or (active_conn.id if active_conn else None)
        if not conn_id:
            raise ValueError("No active SAP connection exists to associate VAT mappings.")

        existing_db_mappings = {
            (m.module, m.sap_code.strip().upper()): m
            for m in db.query(VATMapping).filter(VATMapping.connection_id == conn_id).all()
        }

        changes: Dict[str, Any] = {}
        user_id = current_user.id if current_user else None
        user_email = current_user.email if current_user else "system"

        submitted_keys = set()
        for item in payload.mappings:
            code = item.sap_code.strip().upper()
            key = (item.module, code)
            if key in submitted_keys:
                raise ValueError(f"Duplicate VAT mapping code '{code}' in module '{item.module}'.")
            submitted_keys.add(key)

            if key in existing_db_mappings:
                db_item = existing_db_mappings[key]
                if db_item.canonical_rate != item.canonical_rate or db_item.description != item.description:
                    changes[f"{item.module}:{code}"] = {
                        "old": f"{db_item.canonical_rate} ({db_item.description})",
                        "new": f"{item.canonical_rate} ({item.description})",
                    }
                    db_item.canonical_rate = item.canonical_rate
                    db_item.description = item.description
            else:
                new_mapping = VATMapping(
                    connection_id=conn_id,
                    module=item.module,
                    sap_code=code,
                    description=item.description,
                    canonical_rate=item.canonical_rate,
                    is_builtin=False,
                    is_system_generated=False,
                )
                db.add(new_mapping)
                changes[f"{item.module}:{code}"] = {
                    "old": None,
                    "new": f"{item.canonical_rate} ({item.description})",
                }

        for key, db_item in existing_db_mappings.items():
            if key not in submitted_keys:
                if db_item.is_builtin:
                    raise ValueError(f"Cannot delete built-in SAP VAT code '{db_item.sap_code}' for {db_item.module}.")
                changes[f"{db_item.module}:{db_item.sap_code}"] = {
                    "old": f"{db_item.canonical_rate} ({db_item.description})",
                    "new": "DELETED",
                }
                db.delete(db_item)

        if changes:
            db.commit()
            cls.record_audit_log(db, company_id, user_id, user_email, "update_vat_mappings", changes, payload.reason)

        updated = db.query(VATMapping).filter(VATMapping.connection_id == conn_id).all()
        return [VATMappingItem.model_validate(m) for m in updated]

    # ------------------------------------------------------------------ #
    # KRA VAT mappings (global reference data, shared across companies)
    # ------------------------------------------------------------------ #
    @classmethod
    def save_kra_vat_mappings(
        cls,
        db: Session,
        payload: KRAVATMappingsUpdatePayload,
        current_user: Optional[User] = None,
    ) -> List[KRAVATMappingItem]:
        existing_db_mappings = {
            m.section_prefix.strip().upper(): m
            for m in db.query(KRAVATMapping).all()
        }

        changes: Dict[str, Any] = {}
        user_id = current_user.id if current_user else None
        user_email = current_user.email if current_user else "system"

        column_fields = ["description"]

        submitted_keys = set()
        for item in payload.mappings:
            prefix = item.section_prefix.strip().upper()
            if prefix in submitted_keys:
                raise ValueError(f"Duplicate KRA VAT section prefix '{prefix}'.")
            submitted_keys.add(prefix)

            field_changes = {}
            if prefix in existing_db_mappings:
                db_item = existing_db_mappings[prefix]
                if db_item.canonical_rate != item.canonical_rate:
                    field_changes["canonical_rate"] = (str(db_item.canonical_rate), str(item.canonical_rate))
                    db_item.canonical_rate = item.canonical_rate
                for cf in column_fields:
                    new_val = getattr(item, cf)
                    if getattr(db_item, cf) != new_val:
                        field_changes[cf] = (str(getattr(db_item, cf)), str(new_val))
                        setattr(db_item, cf, new_val)
                if field_changes:
                    changes[f"KRA_VAT:{prefix}"] = {
                        "old": ", ".join(f"{k}={v[0]}" for k, v in field_changes.items()),
                        "new": ", ".join(f"{k}={v[1]}" for k, v in field_changes.items()),
                    }
            else:
                new_mapping = KRAVATMapping(
                    section_prefix=prefix,
                    canonical_rate=item.canonical_rate,
                    description=item.description,
                )
                db.add(new_mapping)
                changes[f"KRA_VAT:{prefix}"] = {
                    "old": None,
                    "new": f"{item.canonical_rate} ({item.description})",
                }

        for prefix, db_item in existing_db_mappings.items():
            if prefix not in submitted_keys:
                changes[f"KRA_VAT:{db_item.section_prefix}"] = {
                    "old": str(db_item.canonical_rate),
                    "new": "DELETED",
                }
                db.delete(db_item)

        if changes:
            db.commit()
            company_id = current_user.company_id if current_user else None
            cls.record_audit_log(db, company_id, user_id, user_email, "update_kra_vat_mappings", changes, payload.reason)

        updated = db.query(KRAVATMapping).all()
        return [KRAVATMappingItem.model_validate(m) for m in updated]

    # ------------------------------------------------------------------ #
    # Test connection
    # ------------------------------------------------------------------ #
    @classmethod
    def test_sap_connection(
        cls,
        db: Session,
        company_id: int,
        req: TestConnectionRequest,
    ) -> TestConnectionResponse:
        active_conn = cls.get_active_connection(db, company_id)

        base_url = (req.base_url or (active_conn.base_url if active_conn else "")).strip().rstrip("/")
        company_db = (req.company_db or (active_conn.company_db if active_conn else "")).strip()
        username = (req.username or (active_conn.username if active_conn else "")).strip()
        password = req.password or (active_conn.password if active_conn else "")
        verify_ssl = True

        steps: Dict[str, StepResult] = {}
        start_time = time.time()

        if not base_url:
            return TestConnectionResponse(
                connected=False,
                steps={"host_reachable": StepResult(status="fail", message="No SAP Base URL provided or configured.")},
                error_message="Missing SAP Server Base URL.",
            )

        login_url = f"{base_url}/Login"
        client = httpx.Client(verify=verify_ssl, timeout=8.0)

        try:
            ping_resp = client.post(
                login_url,
                json={"CompanyDB": company_db, "UserName": username, "Password": password},
            )
            elapsed_ms = round((time.time() - start_time) * 1000, 1)
            steps["host_reachable"] = StepResult(status="pass", message=f"Host responded in {elapsed_ms}ms.")
        except httpx.ConnectError as e:
            steps["host_reachable"] = StepResult(status="fail", message=f"Failed to connect to host {base_url}: {str(e)}")
            return TestConnectionResponse(connected=False, steps=steps, error_message="Network host unreachable.")
        except httpx.TimeoutException:
            steps["host_reachable"] = StepResult(status="fail", message=f"Connection timed out connecting to {base_url}.")
            return TestConnectionResponse(connected=False, steps=steps, error_message="Connection timeout.")
        except Exception as e:
            steps["host_reachable"] = StepResult(status="fail", message=f"Connection attempt failed: {str(e)}")
            return TestConnectionResponse(connected=False, steps=steps, error_message=str(e))

        if ping_resp.status_code != 200:
            err_data = ping_resp.json() if ping_resp.headers.get("content-type", "").startswith("application/json") else {}
            err_msg = err_data.get("error", {}).get("message", {}).get("value", f"HTTP {ping_resp.status_code}")
            steps["authenticated"] = StepResult(status="fail", message=f"Login failed: {err_msg}")
            return TestConnectionResponse(connected=False, steps=steps, error_message=f"SAP Auth Error: {err_msg}")

        steps["authenticated"] = StepResult(status="pass", message=f"Authenticated as user '{username}'.")
        steps["company_valid"] = StepResult(status="pass", message=f"Database '{company_db}' accessible.")

        metadata = {
            "system_version": "SAP Business One Service Layer",
            "company_name": company_db,
            "connected_user": username,
            "database_name": company_db,
            "latency_ms": elapsed_ms,
        }

        try:
            admin_resp = client.get(f"{base_url}/CompanyService_GetAdminInfo", cookies=ping_resp.cookies)
            if admin_resp.status_code == 200:
                admin_data = admin_resp.json()
                metadata["company_name"] = admin_data.get("CompanyName", company_db)
                metadata["system_version"] = f"SAP Business One {admin_data.get('Version', '10.0')}"
        except Exception:
            pass

        return TestConnectionResponse(connected=True, steps=steps, metadata=metadata)

    # ------------------------------------------------------------------ #
    # Audit log
    # ------------------------------------------------------------------ #
    @staticmethod
    def record_audit_log(
        db: Session,
        company_id: Optional[int],
        user_id: Optional[int],
        user_email: Optional[str],
        action: str,
        changes_json: Dict[str, Any],
        reason: Optional[str] = None,
    ):
        log = SettingAuditLog(
            company_id=company_id,
            user_id=user_id,
            user_email=user_email,
            action=action,
            changes_json=changes_json,
            reason=reason,
        )
        db.add(log)
        db.commit()

    @staticmethod
    def get_audit_logs(db: Session, company_id: Optional[int] = None, limit: int = 50) -> List[SettingAuditLog]:
        query = db.query(SettingAuditLog)
        if company_id is not None:
            query = query.filter(SettingAuditLog.company_id == company_id)
        return query.order_by(SettingAuditLog.created_at.desc()).limit(limit).all()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _connection_to_response(conn: CompanySAPConnection) -> SAPConnectionResponse:
        return SAPConnectionResponse(
            id=conn.id,
            company_id=conn.company_id,
            name=conn.name,
            base_url=conn.base_url,
            company_db=conn.company_db,
            username=conn.username,
            password_set=bool(conn.password),
            verify_ssl=conn.verify_ssl,
            is_active=conn.is_active,
            version=conn.version,
            created_at=conn.created_at,
            updated_at=conn.updated_at,
        )
