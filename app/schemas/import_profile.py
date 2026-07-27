from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


from app.schemas.invoice import ReconciliationType
from app.models.import_profile import ProfileScope, SourceFormat


class ParsingHintsSchema(BaseModel):
    has_header: bool = True
    header_row: int = Field(default=1, ge=1)
    data_start_row: int = Field(default=2, ge=1)
    sheet_name: Optional[str] = None
    delimiter: str = Field(default=",", max_length=5)
    date_format: str = "YYYY-MM-DD"
    decimal_separator: str = "."
    thousands_separator: str = ","


class CanonicalColumnMappingSchema(BaseModel):
    pin: List[str] = Field(default_factory=lambda: ["Customer PIN", "Supplier PIN", "PIN", "Tax Number", "KRA PIN"])
    partner_name: List[str] = Field(default_factory=lambda: ["Customer Name", "Supplier Name", "Client Name", "Vendor Name", "Name"])
    invoice_number: List[str] = Field(default_factory=lambda: ["Invoice Number", "Invoice No", "Invoice #", "DocNum", "Receipt No"])
    invoice_date: List[str] = Field(default_factory=lambda: ["Invoice Date", "Doc Date", "Date"])
    cu_number: List[str] = Field(default_factory=lambda: ["CU Number", "ETR Number", "Control Unit No", "CU Serial"])
    vat_group: List[str] = Field(default_factory=lambda: ["VAT Group", "Tax Rate", "VAT Code", "Tax Type"])
    base_amount: List[str] = Field(default_factory=lambda: ["Base Amount", "Taxable Amount", "SubTotal", "Amount", "Total Amount"])
    tax_amount: List[str] = Field(default_factory=lambda: ["Tax Amount", "VAT Amount", "Tax"])


class SalesValidationRulesSchema(BaseModel):
    module: Literal[ReconciliationType.SALES] = ReconciliationType.SALES
    required_fields: List[str] = Field(default_factory=lambda: ["cu_number", "vat_group", "base_amount"])
    allowed_vat_codes: List[str] = Field(default_factory=lambda: ["16", "8", "0", "EXEMPT"])
    date_strictness: Literal["STRICT", "LENIENT"] = "LENIENT"
    row_skip_policy: Literal["SKIP_EMPTY_AND_TOTALS", "FAIL_ON_EMPTY"] = "SKIP_EMPTY_AND_TOTALS"
    default_vat_group: str = "16"
    require_valid_pin_format: bool = True
    vat_derivation_enabled: bool = False


class PurchasesValidationRulesSchema(BaseModel):
    module: Literal[ReconciliationType.PURCHASES] = ReconciliationType.PURCHASES
    required_fields: List[str] = Field(default_factory=lambda: ["cu_number", "vat_group", "base_amount"])
    allowed_vat_codes: List[str] = Field(default_factory=lambda: ["16", "8", "0", "EXEMPT"])
    date_strictness: Literal["STRICT", "LENIENT"] = "LENIENT"
    row_skip_policy: Literal["SKIP_EMPTY_AND_TOTALS", "FAIL_ON_EMPTY"] = "SKIP_EMPTY_AND_TOTALS"
    default_vat_group: str = "16"
    purchase_cu_fallback_field: Optional[str] = None
    vat_derivation_enabled: bool = False


TypedValidationRules = Union[SalesValidationRulesSchema, PurchasesValidationRulesSchema]


class ImportProfileSnapshot(BaseModel):
    profile_id: Optional[int] = None
    profile_name: str
    profile_version: int = 1
    module: ReconciliationType
    provider: str
    source_format: SourceFormat
    parsing_hints: ParsingHintsSchema
    column_mapping: CanonicalColumnMappingSchema
    validation_rules: TypedValidationRules
    snapshot_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ImportProfileCreate(BaseModel):
    name: str = Field(..., max_length=100)
    module: ReconciliationType
    provider: str = Field(default="CUSTOM", max_length=50)
    description: Optional[str] = None
    source_format: SourceFormat = SourceFormat.CSV
    parsing_hints: ParsingHintsSchema = Field(default_factory=ParsingHintsSchema)
    column_mapping: CanonicalColumnMappingSchema = Field(default_factory=CanonicalColumnMappingSchema)
    validation_rules: TypedValidationRules
    is_default: bool = False


class ImportProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    provider: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = None
    source_format: Optional[SourceFormat] = None
    parsing_hints: Optional[ParsingHintsSchema] = None
    column_mapping: Optional[CanonicalColumnMappingSchema] = None
    validation_rules: Optional[TypedValidationRules] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class ImportProfileResponse(BaseModel):
    id: int
    company_id: Optional[int] = None
    scope: ProfileScope
    name: str
    module: ReconciliationType
    provider: str
    description: Optional[str] = None
    source_format: SourceFormat
    parsing_hints: ParsingHintsSchema
    column_mapping: CanonicalColumnMappingSchema
    validation_rules: TypedValidationRules
    is_builtin: bool
    is_default: bool
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MappingPreviewRequest(BaseModel):
    module: ReconciliationType
    source_format: SourceFormat = SourceFormat.CSV
    parsing_hints: ParsingHintsSchema = Field(default_factory=ParsingHintsSchema)
    column_mapping: CanonicalColumnMappingSchema = Field(default_factory=CanonicalColumnMappingSchema)
    validation_rules: TypedValidationRules


class PreviewRowSample(BaseModel):
    row_index: int
    raw_values: Dict[str, Any]
    mapped_invoice: Dict[str, Any]
    validation_errors: List[str] = Field(default_factory=list)


class MappingPreviewResponse(BaseModel):
    filename: str
    detected_headers: List[str]
    total_rows_detected: int
    preview_samples: List[PreviewRowSample]
    is_valid: bool
    general_errors: List[str] = Field(default_factory=list)


class HeaderDetectionResponse(BaseModel):
    filename: str
    detected_headers: List[str]
    header_row: int
    data_start_row: int
    scanned_rows: int
    confidence: str  # "high" | "medium" | "low"
