import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from fastapi import UploadFile

from app.models.import_profile import SourceFormat
from app.schemas.import_profile import (
    ImportProfileSnapshot,
    MappingPreviewResponse,
    PreviewRowSample,
)
from app.schemas.invoice import CSVValidationErrorDetail, Invoice, InvoiceSource, ReconciliationType


def normalize_header(header_str: str) -> str:
    """Cleans header string by removing special chars, extra whitespace, and converting to uppercase."""
    if not header_str:
        return ""
    return re.sub(r"\s+", " ", str(header_str).strip().upper())


def match_column_name(headers: List[str], target_aliases: List[str]) -> Optional[str]:
    """Matches raw file headers against a target field's alias list (case-insensitive)."""
    normalized_headers = {normalize_header(h): h for h in headers if h}
    for alias in target_aliases:
        norm_alias = normalize_header(alias)
        if norm_alias in normalized_headers:
            return normalized_headers[norm_alias]
    return None


def parse_date_value(val: Any, date_format_hint: str) -> Optional[date]:
    """Parses date value handling datetime objects, pandas Timestamps, and strings."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (datetime, date)):
        return val.date() if isinstance(val, datetime) else val

    str_val = str(val).strip()
    if not str_val:
        return None

    # Try date format hint first
    fmt_map = {
        "YYYY-MM-DD": "%Y-%m-%d",
        "DD/MM/YYYY": "%d/%m/%Y",
        "MM/DD/YYYY": "%m/%d/%Y",
        "DD-MM-YYYY": "%d-%m-%Y",
        "YYYY/MM/DD": "%Y/%m/%d",
        "DD Mon YYYY": "%d %b %Y",
        "DD-Mon-YYYY": "%d-%b-%Y",
    }
    primary_fmt = fmt_map.get(date_format_hint)
    if primary_fmt:
        try:
            return datetime.strptime(str_val, primary_fmt).date()
        except ValueError:
            pass

    # Fallback auto-parser
    fallback_formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y", "%d.%m.%Y", "%Y.%m.%d", "%d %b %Y", "%d-%b-%Y"]
    for fmt in fallback_formats:
        try:
            return datetime.strptime(str_val, fmt).date()
        except ValueError:
            continue

    try:
        dt = pd.to_datetime(str_val, errors="coerce")
        if not pd.isna(dt):
            return dt.date()
    except Exception:
        pass

    return None


def parse_numeric_amount(val: Any, decimal_sep: str = ".", thousand_sep: str = ",") -> Optional[Decimal]:
    """Parses numeric base amount handling string currency symbols, separators, and decimals."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(val))

    str_val = str(val).strip()
    if not str_val:
        return None

    # Clean currency symbols & extra characters
    cleaned = re.sub(r"[^\d.,\-]", "", str_val)
    if not cleaned:
        return None

    if decimal_sep == ",":
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(thousand_sep, "")

    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


class ERPImportService:
    @classmethod
    def read_file_dataframe(
        cls, file_bytes: bytes, filename: str, snapshot: ImportProfileSnapshot
    ) -> Tuple[pd.DataFrame, List[str]]:
        """Reads raw bytes into a pandas DataFrame based on snapshot parsing hints."""
        hints = snapshot.parsing_hints
        is_xlsx = filename.endswith(".xlsx") or snapshot.source_format == SourceFormat.XLSX

        if is_xlsx:
            excel_file = pd.ExcelFile(io.BytesIO(file_bytes))
            sheet = hints.sheet_name if hints.sheet_name and hints.sheet_name in excel_file.sheet_names else 0
            df_raw = pd.read_excel(excel_file, sheet_name=sheet, header=None)
        else:
            # CSV file parsing with encoding detection
            for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
                try:
                    content = file_bytes.decode(enc)
                    output = io.StringIO(content)
                    delimiter = hints.delimiter or ","
                    df_raw = pd.read_csv(output, header=None, sep=delimiter, dtype=str, skipinitialspace=True)
                    break
                except Exception:
                    continue
            else:
                raise ValueError(f"Unable to parse CSV file '{filename}'. Ensure it is valid UTF-8 or Latin-1 CSV.")

        if df_raw.empty:
            raise ValueError(f"Uploaded file '{filename}' contains no data rows.")

        header_idx = max(0, hints.header_row - 1)
        if header_idx >= len(df_raw):
            raise ValueError(f"Header row index {hints.header_row} exceeds file row count ({len(df_raw)}).")

        headers = [str(val).strip() if pd.notna(val) else f"Column_{i+1}" for i, val in enumerate(df_raw.iloc[header_idx])]
        data_start_idx = max(header_idx + 1, hints.data_start_row - 1)

        df_data = df_raw.iloc[data_start_idx:].copy()
        df_data.columns = headers

        return df_data, headers

    @classmethod
    def parse_erp_file(
        cls, file_bytes: bytes, filename: str, snapshot: ImportProfileSnapshot
    ) -> Tuple[List[Invoice], List[CSVValidationErrorDetail]]:
        """Parses CSV/XLSX raw file bytes into normalized Invoice models using immutable snapshot rules."""
        df_data, headers = cls.read_file_dataframe(file_bytes, filename, snapshot)
        mapping = snapshot.column_mapping
        hints = snapshot.parsing_hints
        rules = snapshot.validation_rules

        # Match columns to target aliases
        col_pin = match_column_name(headers, mapping.pin)
        col_partner = match_column_name(headers, mapping.partner_name)
        col_inv_num = match_column_name(headers, mapping.invoice_number)
        col_inv_date = match_column_name(headers, mapping.invoice_date)
        col_cu_num = match_column_name(headers, mapping.cu_number)
        col_vat_group = match_column_name(headers, mapping.vat_group)
        col_base_amt = match_column_name(headers, mapping.base_amount)

        invoices: List[Invoice] = []
        errors: List[CSVValidationErrorDetail] = []

        for row_idx, row in df_data.iterrows():
            excel_row_num = int(row_idx) + 1

            raw_pin = str(row[col_pin]).strip() if col_pin and pd.notna(row[col_pin]) else ""
            raw_partner = str(row[col_partner]).strip() if col_partner and pd.notna(row[col_partner]) else ""
            raw_inv_num = str(row[col_inv_num]).strip() if col_inv_num and pd.notna(row[col_inv_num]) else ""
            raw_cu_num = str(row[col_cu_num]).strip() if col_cu_num and pd.notna(row[col_cu_num]) else ""
            raw_vat_group = str(row[col_vat_group]).strip() if col_vat_group and pd.notna(row[col_vat_group]) else rules.default_vat_group
            
            raw_date_val = row[col_inv_date] if col_inv_date and pd.notna(row[col_inv_date]) else None
            parsed_date = parse_date_value(raw_date_val, hints.date_format)

            raw_base_val = row[col_base_amt] if col_base_amt and pd.notna(row[col_base_amt]) else None
            parsed_amount = parse_numeric_amount(raw_base_val, hints.decimal_separator, hints.thousands_separator)

            # Skip empty rows policy
            if rules.row_skip_policy == "SKIP_EMPTY_AND_TOTALS":
                if not raw_pin and not raw_inv_num and parsed_amount is None:
                    continue
                if "TOTAL" in raw_partner.upper() or "TOTAL" in raw_inv_num.upper():
                    continue
                raw_date_str = str(raw_date_val).strip().upper() if raw_date_val is not None else ""
                if "TOTAL" in raw_date_str:
                    continue

            # Validation checks
            row_has_errors = False
            if "pin" in rules.required_fields and not raw_pin:
                errors.append(CSVValidationErrorDetail(row=excel_row_num, column=col_pin or "PIN", message="PIN is required."))
                row_has_errors = True
            if "invoice_number" in rules.required_fields and not raw_inv_num:
                errors.append(CSVValidationErrorDetail(row=excel_row_num, column=col_inv_num or "Invoice Number", message="Invoice Number is required."))
                row_has_errors = True
            if "base_amount" in rules.required_fields and parsed_amount is None:
                errors.append(CSVValidationErrorDetail(row=excel_row_num, column=col_base_amt or "Base Amount", message="Base Amount is missing or unparseable."))
                row_has_errors = True

            if not row_has_errors and parsed_amount is not None:
                inv = Invoice(
                    pin=raw_pin or "N/A",
                    partner_name=raw_partner or "N/A",
                    invoice_number=raw_inv_num or f"ROW-{excel_row_num}",
                    invoice_date=parsed_date or date.today(),
                    cu_number=raw_cu_num or "",
                    vat_group=raw_vat_group or rules.default_vat_group,
                    base_amount=parsed_amount,
                    source=InvoiceSource.ERP,
                    provider=snapshot.provider,
                )
                invoices.append(inv)

        return invoices, errors

    @classmethod
    def preview_mapping(
        cls, file_bytes: bytes, filename: str, snapshot: ImportProfileSnapshot, max_rows: int = 5
    ) -> MappingPreviewResponse:
        """Dry-run preview of parsing a sample file against candidate profile rules."""
        general_errors: List[str] = []
        try:
            df_data, headers = cls.read_file_dataframe(file_bytes, filename, snapshot)
        except Exception as e:
            return MappingPreviewResponse(
                filename=filename,
                detected_headers=[],
                total_rows_detected=0,
                preview_samples=[],
                is_valid=False,
                general_errors=[f"Failed to read file structure: {str(e)}"],
            )

        mapping = snapshot.column_mapping
        hints = snapshot.parsing_hints
        rules = snapshot.validation_rules

        col_pin = match_column_name(headers, mapping.pin)
        col_partner = match_column_name(headers, mapping.partner_name)
        col_inv_num = match_column_name(headers, mapping.invoice_number)
        col_inv_date = match_column_name(headers, mapping.invoice_date)
        col_cu_num = match_column_name(headers, mapping.cu_number)
        col_vat_group = match_column_name(headers, mapping.vat_group)
        col_base_amt = match_column_name(headers, mapping.base_amount)

        if not col_pin:
            general_errors.append("Could not auto-match PIN column header.")
        if not col_inv_num:
            general_errors.append("Could not auto-match Invoice Number column header.")
        if not col_base_amt:
            general_errors.append("Could not auto-match Base Amount column header.")

        preview_samples: List[PreviewRowSample] = []
        for i, (row_idx, row) in enumerate(df_data.head(max_rows).iterrows()):
            excel_row_num = int(row_idx) + 1
            raw_vals = {col: str(val) if pd.notna(val) else "" for col, val in row.items()}

            raw_pin = str(row[col_pin]).strip() if col_pin and pd.notna(row[col_pin]) else ""
            raw_partner = str(row[col_partner]).strip() if col_partner and pd.notna(row[col_partner]) else ""
            raw_inv_num = str(row[col_inv_num]).strip() if col_inv_num and pd.notna(row[col_inv_num]) else ""
            raw_cu_num = str(row[col_cu_num]).strip() if col_cu_num and pd.notna(row[col_cu_num]) else ""
            raw_vat_group = str(row[col_vat_group]).strip() if col_vat_group and pd.notna(row[col_vat_group]) else rules.default_vat_group

            raw_date_val = row[col_inv_date] if col_inv_date and pd.notna(row[col_inv_date]) else None
            parsed_date = parse_date_value(raw_date_val, hints.date_format)

            raw_base_val = row[col_base_amt] if col_base_amt and pd.notna(row[col_base_amt]) else None
            parsed_amount = parse_numeric_amount(raw_base_val, hints.decimal_separator, hints.thousands_separator)

            row_errors: List[str] = []
            if "pin" in rules.required_fields and not raw_pin:
                row_errors.append("PIN is missing.")
            if "invoice_number" in rules.required_fields and not raw_inv_num:
                row_errors.append("Invoice Number is missing.")
            if "base_amount" in rules.required_fields and parsed_amount is None:
                row_errors.append("Base Amount is missing or unparseable.")

            sample = PreviewRowSample(
                row_index=excel_row_num,
                raw_values=raw_vals,
                mapped_invoice={
                    "pin": raw_pin,
                    "partner_name": raw_partner,
                    "invoice_number": raw_inv_num,
                    "invoice_date": str(parsed_date) if parsed_date else None,
                    "cu_number": raw_cu_num,
                    "vat_group": raw_vat_group,
                    "base_amount": float(parsed_amount) if parsed_amount is not None else None,
                },
                validation_errors=row_errors,
            )
            preview_samples.append(sample)

        is_valid = len(general_errors) == 0 and all(len(s.validation_errors) == 0 for s in preview_samples)

        return MappingPreviewResponse(
            filename=filename,
            detected_headers=headers,
            total_rows_detected=len(df_data),
            preview_samples=preview_samples,
            is_valid=is_valid,
            general_errors=general_errors,
        )
