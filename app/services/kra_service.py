import csv
import io
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.models.settings import KRAVATMapping
from app.schemas.invoice import (
    Invoice,
    CSVValidationErrorDetail,
    FileUploadStatus,
    InvoiceUploadResponse,
    InvoiceSource,
)
from app.services.normalization import normalize_invoice_data
from app.services.settings_service import SettingsService


def _cell_lower(cell: str) -> str:
    return (cell or "").strip().lower()


def _kw_in_cell(keyword: str, cell: str) -> bool:
    return keyword in _cell_lower(cell)


def parse_kra_csv(file: UploadFile, db: Session, company_id: int | None = None) -> InvoiceUploadResponse:
    """
    Parses a KRA CSV file, performs schema and type normalization,
    and returns a response detailing successful parses and aggregated validation errors.
    """
    settings = get_settings()

    # 1. Validate file extension
    filename = file.filename or "unknown.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are allowed."
        )

    # 2. Read content to check size and validate encoding
    try:
        content_bytes = file.file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read upload file: {str(e)}"
        )
    finally:
        file.file.seek(0)

    size_mb = len(content_bytes) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds the limit of {settings.max_upload_size_mb}MB."
        )

    if len(content_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty."
        )

    # 3. Validate UTF-8 encoding
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File encoding must be UTF-8."
        )

    # 4. Parse CSV
    f = io.StringIO(content)
    reader = csv.reader(f)
    rows = list(reader)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file contains no data."
        )

    # KRA exports are typically headerless. Tolerate an optional header row when the
    # first row's cells match known header keywords (deterministic, bounded check).
    HEADER_KEYWORDS = ("pin", "invoice", "date", "vat", "amount", "customer", "partner", "supplier", "cu")
    if any(_kw_in_cell(kw, cell) for cell in (rows[0] or []) for kw in HEADER_KEYWORDS):
        data_rows = rows[1:]
    else:
        data_rows = rows

    headers = [h.strip() for h in (rows[0] or [])]

    import re
    match = re.match(r"^(SEC_[A-Z0-9]+)(?:[_.]|$)", filename.upper())
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Filename '{filename}' must start with a valid KRA section prefix (e.g. SEC_B_... or SEC_J_...). Please rename the file correctly."
        )
    section_prefix = match.group(1)

    from app.services.parsing_profile_service import ParsingProfileService, ParsingProfileError
    try:
        profile = ParsingProfileService.get_required_profile(db, section_prefix, company_id=company_id)
    except ParsingProfileError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Lookup VAT mapping independently
    vat_mapping = db.query(KRAVATMapping).filter(KRAVATMapping.section_prefix == section_prefix).first()
    if not vat_mapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No VAT mapping configured for KRA section '{section_prefix}'. Please configure it in settings."
        )

    # VAT Group must match the SAP representation (e.g. "16", "0", "8"), since
    # reconciliation joins on cu_number + vat_group. 
    file_vat_rate = vat_mapping.canonical_rate

    # Build the logical-field -> column-index map from the matched profile.
    # VAT Group is not read from a column (the KRA column is unreliable across
    # sections); it is always derived from the section prefix (file_vat_rate).
    field_to_index = {
        "pin": profile.pin_column,
        "partner_name": profile.partner_name_column,
        "invoice_number": profile.invoice_number_column,
        "invoice_date": profile.invoice_date_column,
        "cu_number": profile.cu_number_column,
        "base_amount": profile.base_amount_column,
    }
    # logical field -> profile column attribute (for human-readable error headers)
    field_to_attr = {
        "pin": "pin_column",
        "partner_name": "partner_name_column",
        "invoice_number": "invoice_number_column",
        "invoice_date": "invoice_date_column",
        "cu_number": "cu_number_column",
        "base_amount": "base_amount_column",
    }

    invoices: list[Invoice] = []
    errors: list[CSVValidationErrorDetail] = []
    total_rows = 0

    for row_idx, row in enumerate(data_rows, start=2):
        if not row or not any(cell.strip() for cell in row):
            continue

        total_rows += 1
        row_values = {}

        for field, idx in field_to_index.items():
            if idx is None or idx < 0:
                # Section has no such column (e.g. purchases without invoice number)
                row_values[field] = ""
            elif idx < len(row):
                row_values[field] = row[idx]
            else:
                # Missing column index in the row
                row_values[field] = ""

        # VAT Group is always derived from the section profile (filename prefix) —
        # the KRA column is unreliable across sections (rate, label, or empty), so the
        # deterministic prefix mapping is the single source of truth.
        row_values["vat_group"] = file_vat_rate

        try:
            normalized = normalize_invoice_data(
                pin=row_values["pin"],
                partner_name=row_values["partner_name"],
                invoice_number=row_values["invoice_number"],
                invoice_date=row_values["invoice_date"],
                cu_number=row_values["cu_number"],
                vat_group=row_values["vat_group"],
                base_amount=row_values["base_amount"],
                allow_negative=True,
                invoice_number_optional=True,
            )
            invoice = Invoice(**normalized, source=InvoiceSource.KRA)
            invoices.append(invoice)
        except ValueError as ve:
            msg = str(ve)
            msg_lower = msg.lower()
            col_name = None

            def safe_header(field_key):
                idx = field_to_index.get(field_key)
                attr = field_to_attr.get(field_key)
                label = attr or field_key
                if idx is not None and idx < len(headers):
                    return f"{headers[idx]} (col {idx})"
                return label

            if "pin" in msg_lower:
                col_name = safe_header("pin")
            elif "customer name" in msg_lower or "partner name" in msg_lower:
                col_name = safe_header("partner_name")
            elif "invoice number" in msg_lower:
                col_name = safe_header("invoice_number")
            elif "date" in msg_lower:
                col_name = safe_header("invoice_date")
            elif "cu number" in msg_lower:
                col_name = safe_header("cu_number")
            elif "vat group" in msg_lower:
                col_name = "VAT Group (Filename prefix)"
            elif "base amount" in msg_lower:
                col_name = safe_header("base_amount")

            errors.append(CSVValidationErrorDetail(
                row=row_idx,
                column=col_name,
                message=msg
            ))

    return InvoiceUploadResponse(
        filename=filename,
        rows=total_rows,
        parsed=len(invoices),
        errors_count=len(errors),
        errors=errors,
        invoices=invoices
    )


def parse_multiple_kra_csvs(
    files: list[UploadFile], db: Session, company_id: int | None = None
) -> tuple[list[Invoice], list[FileUploadStatus]]:
    """Parse multiple KRA CSV uploads, returning the combined invoices and per-file status."""
    all_invoices: list[Invoice] = []
    file_statuses: list[FileUploadStatus] = []
    for file in files:
        upload_res = parse_kra_csv(file, db, company_id=company_id)
        all_invoices.extend(upload_res.invoices)
        file_statuses.append(
            FileUploadStatus(
                filename=upload_res.filename,
                rows=upload_res.rows,
                parsed=upload_res.parsed,
                errors_count=upload_res.errors_count,
                errors=upload_res.errors,
            )
        )
    return all_invoices, file_statuses
