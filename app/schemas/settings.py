from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator
import re

from app.models.settings import (
    BaseAmountPolicy,
    PurchaseCUField,
    UnmappedVatPolicy,
    VatModule,
)
from app.utils.vat_utils import normalize_vat_rate


class SAPConnectionBase(BaseModel):
    name: str = Field(default="Primary SAP Connection", max_length=100)
    base_url: str = Field(..., description="Base URL of SAP Service Layer (e.g. https://sap.example.com:50000/b1s/v1)")
    company_db: str = Field(..., max_length=100)
    username: str = Field(..., max_length=100)
    verify_ssl: bool = Field(default=True)

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class SAPConnectionCreate(SAPConnectionBase):
    password: str = Field(..., min_length=1)


class SAPConnectionUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    company_db: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    verify_ssl: Optional[bool] = None
    version: int = Field(..., description="Current connection version for optimistic locking")


class SAPConnectionResponse(SAPConnectionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    password_set: bool = True
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class SystemSettingsBase(BaseModel):
    amount_tolerance: Decimal = Field(default=Decimal("10.00"), ge=Decimal("0.00"), description="Amount tolerance in KES")
    base_amount_policy: BaseAmountPolicy = Field(default=BaseAmountPolicy.ALLOW)
    unmapped_vat_policy: UnmappedVatPolicy = Field(default=UnmappedVatPolicy.NEEDS_REVIEW)
    ignore_missing_cu: bool = Field(default=False)
    include_credit_notes: bool = Field(default=True)
    include_debit_notes: bool = Field(default=True)
    skip_cancelled: bool = Field(default=True)
    sales_cu_source: str = Field(default="U_CUINV", min_length=1, max_length=50, description="SAP field holding the CU number on Sales Invoices")
    purchase_cu_source: str = Field(default="U_CUINV", min_length=1, max_length=50, description="SAP field holding the CU number on Purchase Invoices")
    kra_parsing_profiles: Optional["KRAParsingProfilesConfig"] = Field(None, description="Internal JSON representation of profiles")


class SystemSettingsUpdate(SystemSettingsBase):
    version: int = Field(..., description="Current system settings version for optimistic locking")
    reason: Optional[str] = Field(None, description="Reason for updating operational settings")


class SystemSettingsResponse(SystemSettingsBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    active_connection_id: Optional[int] = None
    version: int
    updated_at: datetime
    warning: Optional[str] = None


class VATMappingItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    module: VatModule
    sap_code: str = Field(..., min_length=1, max_length=50)
    description: str = Field(default="", max_length=200)
    canonical_rate: str = Field(..., max_length=20)
    is_builtin: bool = False
    is_system_generated: bool = False
    created_at: Optional[datetime] = None

    @field_validator("canonical_rate", mode="before")
    @classmethod
    def validate_rate(cls, v: Any) -> str:
        return normalize_vat_rate(v)


class VATMappingsUpdatePayload(BaseModel):
    connection_id: Optional[int] = None
    mappings: List[VATMappingItem]
    reason: Optional[str] = None


class KRAParsingProfileItem(BaseModel):
    pin_column: int = Field(ge=0)
    partner_name_column: int = Field(ge=0)
    invoice_number_column: Optional[int] = Field(default=None, ge=0)
    invoice_date_column: int = Field(ge=0)
    cu_number_column: int = Field(ge=0)
    base_amount_column: int = Field(ge=0)

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if v == "":
            return None
        return v

    @model_validator(mode="after")
    def validate_unique_indexes(self) -> "KRAParsingProfileItem":
        indexes = []
        for field_name in ["pin_column", "partner_name_column", "invoice_number_column", "invoice_date_column", "cu_number_column", "base_amount_column"]:
            val = getattr(self, field_name, None)
            if val is not None:
                indexes.append(val)
        if len(indexes) != len(set(indexes)):
            raise ValueError("Duplicate column indexes are not allowed in a parsing profile")
        return self


class KRAParsingProfilesConfig(BaseModel):
    schema_version: Literal[1] = 1
    profiles: Dict[str, KRAParsingProfileItem]

    @field_validator("profiles")
    @classmethod
    def validate_section_keys(cls, v: Dict[str, KRAParsingProfileItem]) -> Dict[str, KRAParsingProfileItem]:
        for k in v.keys():
            if not re.match(r"^SEC_[A-Z]$", k):
                raise ValueError(f"Invalid section identifier: {k}. Must match ^SEC_[A-Z]$")
        return v


class KRAVATMappingItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    section_prefix: str = Field(..., min_length=1, max_length=50)
    canonical_rate: str = Field(..., max_length=20)
    description: str = ""

    @field_validator("canonical_rate", mode="before")
    @classmethod
    def validate_rate(cls, v: Any) -> str:
        return normalize_vat_rate(v)


class KRAVATMappingsUpdatePayload(BaseModel):
    mappings: List[KRAVATMappingItem]
    reason: Optional[str] = None


class SettingsCompositeResponse(BaseModel):
    sap_connection: Optional[SAPConnectionResponse] = None
    system_settings: SystemSettingsResponse
    vat_mappings: List[VATMappingItem]
    kra_vat_mappings: List[KRAVATMappingItem] = Field(default_factory=list)
    is_using_env_fallback: bool = False


class TestConnectionRequest(BaseModel):
    base_url: Optional[str] = None
    company_db: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    verify_ssl: Optional[bool] = None
    connection_id: Optional[int] = None


class StepResult(BaseModel):
    status: str  # "pass" | "fail"
    message: str


class TestConnectionResponse(BaseModel):
    connected: bool
    steps: Dict[str, StepResult]
    metadata: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class SettingAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int]
    user_email: Optional[str]
    action: str
    changes_json: Dict[str, Any]
    reason: Optional[str]
    created_at: datetime
