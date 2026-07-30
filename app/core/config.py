import subprocess
from decimal import Decimal
from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.exceptions import SAPConfigurationError


def _current_branch() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=Path(__file__).resolve().parent.parent.parent,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return ""


_branch = _current_branch()
_env_files: list[Path] = [Path(".env")]
if _branch:
    _branch_env = Path(f".env.{_branch}")
    if _branch_env.exists():
        _env_files.append(_branch_env)


class BaseAmountPolicy(str, Enum):
    SKIP = "skip"
    REJECT = "reject"
    ALLOW = "allow"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_files,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    app_name: str = Field(default="KRA Reconciliation API", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    database_url: str = Field(default="sqlite:///./data/kra_reconciliation.db", alias="DATABASE_URL")
    secret_key: SecretStr = Field(default=SecretStr("default_secret_key_change_me_in_production_32bytes_min"), alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    frontend_url: str = Field(default="http://localhost:3000", alias="FRONTEND_URL")

    # Mail SMTP Settings (SendGrid)
    mail_mailer: str = Field(default="smtp", alias="MAIL_MAILER")
    mail_host: str = Field(default="smtp.sendgrid.net", alias="MAIL_HOST")
    mail_port: int = Field(default=587, alias="MAIL_PORT")
    mail_username: str = Field(default="apikey", alias="MAIL_USERNAME")
    mail_password: SecretStr = Field(default=SecretStr(""), alias="MAIL_PASSWORD")
    mail_from_address: str = Field(default="47CRM@techbizafrica.com", alias="MAIL_FROM_ADDRESS")
    mail_from_name: str = Field(default="Techbiz Group", alias="MAIL_FROM_NAME")
    mail_encryption: str = Field(default="tls", alias="MAIL_ENCRYPTION")
    password_reset_token_expire_minutes: int = Field(default=30, alias="PASSWORD_RESET_TOKEN_EXPIRE_MINUTES")

    sap_base_url: AnyHttpUrl | None = Field(default=None, alias="SAP_BASE_URL")
    sap_username: str = Field(default="", alias="SAP_USERNAME")
    sap_password: SecretStr = Field(default=SecretStr(""), alias="SAP_PASSWORD")
    sap_company_db: str = Field(default="", alias="SAP_COMPANY_DB")
    sap_verify_ssl: bool = Field(default=True, alias="SAP_VERIFY_SSL")
    sap_base_amount_policy: BaseAmountPolicy = Field(default=BaseAmountPolicy.SKIP, alias="SAP_BASE_AMOUNT_POLICY")

    amount_tolerance: Decimal = Field(default=Decimal("10.00"), alias="AMOUNT_TOLERANCE")

    max_upload_size_mb: int = Field(default=5, alias="MAX_UPLOAD_SIZE_MB")
    kra_header_mapping: dict[str, str] = Field(
        default={
            "pin number": "pin",
            "pin": "pin",
            "customer name": "customer_name",
            "invoice number": "invoice_number",
            "invoice date": "invoice_date",
            "cu number": "cu_number",
            "vat group": "vat_group",
            "base amount": "base_amount"
        },
        alias="KRA_HEADER_MAPPING"
    )

    cors_origins: list[str] | str = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001"],
        alias="CORS_ORIGINS",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        if isinstance(v, str):
            import json
            v_trimmed = v.strip()
            if v_trimmed == "*" or v_trimmed == '"*"':
                return ["*"]
            if v_trimmed.startswith("["):
                try:
                    return json.loads(v_trimmed)
                except Exception:
                    pass
            return [origin.strip() for origin in v_trimmed.split(",") if origin.strip()]
        if isinstance(v, list):
            return v
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("sap_base_url", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if v == "":
            return None
        return v

    @model_validator(mode="after")
    def validate_sap_config(self) -> "Settings":
        if self.sap_base_url:
            missing = []
            if not self.sap_username:
                missing.append("SAP_USERNAME")
            if not self.sap_password.get_secret_value():
                missing.append("SAP_PASSWORD")
            if not self.sap_company_db:
                missing.append("SAP_COMPANY_DB")
            if missing:
                raise SAPConfigurationError(
                    f"Invalid SAP Service Layer configuration. Missing required fields: {', '.join(missing)}"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

