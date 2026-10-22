import datetime
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List
from app.core.config import get_settings
from app.core.exceptions import SAPQueryError
from app.services.vat_normalizer import VatNormalizer, vat_normalizer
from app.utils.cu_utils import canonical_cu_number
from app.utils.vat_utils import normalize_vat_rate
from app.domain.document_types import CanonicalReconciliationRow, IngestionProvenance

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PurchaseFieldMapping:
    """
    SAP fields to compare for Purchase Invoices instead of the standard ones.

    Some companies book a supplier's invoice as zero-rated with the VAT-inclusive amount and
    keep the real VAT code and VAT-exclusive amount in UDFs (e.g. U_Taxable, U_ExcVat). A
    field left as None uses the standard field: TaxPercentagePerRow/VatGroup or LineTotal.
    Levels are "line" (read from each DocumentLine) or "header" (read from the document),
    chosen independently. A header-level amount goes to the document's single VAT group;
    documents whose lines carry several VAT groups fall back to the standard fields.
    """

    vat_field: str | None = None
    vat_level: str = "line"
    amount_field: str | None = None
    amount_level: str = "line"

    @property
    def is_custom(self) -> bool:
        return bool(self.vat_field or self.amount_field)

    @property
    def amount_is_header(self) -> bool:
        return bool(self.amount_field) and self.amount_level == "header"

    @property
    def header_fields(self) -> List[str]:
        """Header-level fields, which must be requested in $select explicitly."""
        return [
            field
            for field, level in ((self.vat_field, self.vat_level), (self.amount_field, self.amount_level))
            if field and level == "header"
        ]


def parse_sap_date(date_val: Any) -> datetime.date:
    """
    Parses various date formats from SAP Service Layer into a python date object.
    """
    if isinstance(date_val, datetime.date):
        return date_val
    if isinstance(date_val, datetime.datetime):
        return date_val.date()

    date_str = str(date_val).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    try:
        return datetime.date.fromisoformat(date_str[:10])
    except ValueError:
        raise ValueError(f"Invalid SAP DocDate format: '{date_val}'")


def extract_cu_number(raw_document: Dict[str, Any], cu_field: str) -> str:
    """
    Extracts the CU (Control Unit) number from a raw SAP document using the configured
    SAP field name. Canonicalized the same way the KRA side is, so the two pair up.
    Centralizing this makes future field-specific tweaks a one-function change.
    """
    return canonical_cu_number(raw_document.get(cu_field))


def _handle_unmapped_vat_code(
    code: str,
    source_document_type: str,
    invoice_number: str,
    location: str,
    reconciliation_session_id: str,
    unmapped_vat_policy: str | None,
) -> None:
    """
    Reacts to a SAP VAT code with no configured mapping.

    Such a code cannot be resolved to a canonical rate, so it becomes its own tax
    bucket and will not match the KRA side. Honours the per-company
    `unmapped_vat_policy`: REJECT_INVOICE fails the load loudly, anything else
    (NEEDS_REVIEW, the default) logs a warning and lets the row through for review.
    """
    message = (
        f"[ReconciliationSession: {reconciliation_session_id}] SAP {source_document_type} "
        f"{invoice_number} {location} uses VAT code '{code}', which has no mapping "
        f"configured under Settings > VAT Mappings. It cannot be resolved to a canonical "
        f"rate and will not match the KRA side."
    )
    # Accept either the UnmappedVatPolicy enum or its raw string value: str() on a
    # (str, Enum) member yields "UnmappedVatPolicy.REJECT_INVOICE", not the value.
    policy = getattr(unmapped_vat_policy, "value", unmapped_vat_policy)
    if str(policy or "").lower() == "reject_invoice":
        raise SAPQueryError(message)
    logger.warning(message)


def _standard_line_vat_group(
    line: Dict[str, Any],
    line_idx: int,
    source_document_type: str,
    invoice_number: str,
    reconciliation_type: str,
    reconciliation_session_id: str,
    normalizer: VatNormalizer,
    unmapped_vat_policy: str | None,
) -> str:
    """Resolves a line's VAT group from the standard TaxPercentagePerRow/VatGroup fields."""
    tax_pct_raw = line.get("TaxPercentagePerRow")
    vat_group_raw = line.get("VatGroup")

    if tax_pct_raw is not None:
        try:
            tax_pct = Decimal(str(tax_pct_raw).strip())
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise SAPQueryError(
                f"SAP {source_document_type} {invoice_number} line {line_idx} has invalid TaxPercentagePerRow: {exc}"
            )

        if tax_pct > 0:
            vat_group_str = normalize_vat_rate(tax_pct)
        else:
            # Rate is 0.0: only the VatGroup code can tell exempt apart from
            # zero-rated. If the code is unmapped we cannot make that call, so
            # surface it rather than silently collapsing to "0".
            vat_group_raw_str = str(vat_group_raw).strip() if vat_group_raw is not None else ""
            if vat_group_raw_str and normalizer.normalize("sap", reconciliation_type, vat_group_raw_str) == "EXEMPT":
                vat_group_str = "EXEMPT"
            else:
                if vat_group_raw_str and not normalizer.is_mapped("sap", reconciliation_type, vat_group_raw_str):
                    _handle_unmapped_vat_code(
                        vat_group_raw_str, source_document_type, invoice_number,
                        f"line {line_idx}", reconciliation_session_id, unmapped_vat_policy,
                    )
                vat_group_str = "0"
    elif vat_group_raw is not None:
        vat_group_str = str(vat_group_raw).strip()
        if not vat_group_str:
            raise SAPQueryError(
                f"SAP {source_document_type} {invoice_number} line {line_idx} has empty VatGroup"
            )
        if not normalizer.is_mapped("sap", reconciliation_type, vat_group_str):
            _handle_unmapped_vat_code(
                vat_group_str, source_document_type, invoice_number,
                f"line {line_idx}", reconciliation_session_id, unmapped_vat_policy,
            )
        vat_group_str = normalizer.normalize("sap", reconciliation_type, vat_group_str)
    else:
        raise SAPQueryError(
            f"SAP {source_document_type} {invoice_number} line {line_idx} has missing tax fields (neither TaxPercentagePerRow nor VatGroup present)"
        )
    return vat_group_str


def _resolve_custom_vat_code(
    raw_value: Any,
    location: str,
    source_document_type: str,
    invoice_number: str,
    reconciliation_type: str,
    reconciliation_session_id: str,
    normalizer: VatNormalizer,
    unmapped_vat_policy: str | None,
) -> str:
    """
    Resolves a VAT code read from a configured field (e.g. U_Taxable).

    Configured VAT Mappings win; otherwise a rate written directly ("16", "16%", "EXEMPT")
    is accepted as-is. Anything else is an unmapped code, handled per unmapped_vat_policy.
    """
    code = str(raw_value).strip()
    if normalizer.is_mapped("sap", reconciliation_type, code):
        return normalizer.normalize("sap", reconciliation_type, code)
    try:
        return normalize_vat_rate(code)
    except ValueError:
        _handle_unmapped_vat_code(
            code, source_document_type, invoice_number,
            location, reconciliation_session_id, unmapped_vat_policy,
        )
        return normalizer.normalize("sap", reconciliation_type, code)


def _parse_amount(raw_value: Any, field_name: str, location: str, source_document_type: str, invoice_number: str) -> Decimal:
    try:
        return Decimal(str(raw_value).strip())
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise SAPQueryError(
            f"SAP {source_document_type} {invoice_number} {location} has invalid {field_name}: {exc}"
        )


def _present(value: Any) -> Any:
    """The value, or None when it is missing or blank."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return value


def _custom_line_values(
    raw_document: Dict[str, Any], line: Dict[str, Any], mapping: "PurchaseFieldMapping"
) -> tuple[Any, Any] | None:
    """
    Reads the configured VAT/amount values for one line, from the line or the header per
    the configured level. Returns None when any configured field is empty, so the caller
    falls back to the standard fields for both: mixing a custom VAT code with a standard
    VAT-inclusive amount (or vice versa) would produce a figure matching neither side.
    """
    values = []
    for field, level in ((mapping.vat_field, mapping.vat_level), (mapping.amount_field, mapping.amount_level)):
        if not field:
            values.append(None)
            continue
        value = _present((raw_document if level == "header" else line).get(field))
        if value is None:
            return None
        values.append(value)
    return values[0], values[1]


def _document_vat_group(
    raw_document: Dict[str, Any],
    document_lines: List[Dict[str, Any]],
    mapping: "PurchaseFieldMapping",
    vat_args: tuple,
) -> str | None:
    """
    The single VAT group a header-level amount belongs to, or None to fall back to the
    standard fields.

    From the header field when the VAT code is header-level; otherwise from the lines
    (configured field or standard tax fields), which must all resolve to the same group.
    A document total cannot be split across several VAT groups without inventing figures.
    """
    source_document_type, invoice_number, _, reconciliation_session_id = vat_args[:4]
    if mapping.vat_field and mapping.vat_level == "header":
        raw = _present(raw_document.get(mapping.vat_field))
        return _resolve_custom_vat_code(raw, "header", *vat_args) if raw is not None else None

    groups = set()
    for line_idx, line in enumerate(document_lines):
        if mapping.vat_field:
            raw = _present(line.get(mapping.vat_field))
            if raw is None:
                return None
            groups.add(_resolve_custom_vat_code(raw, f"line {line_idx}", *vat_args))
        else:
            groups.add(_standard_line_vat_group(line, line_idx, *vat_args))

    if len(groups) == 1:
        return groups.pop()
    logger.warning(
        f"[ReconciliationSession: {reconciliation_session_id}] SAP {source_document_type} {invoice_number} "
        f"has lines with different VAT codes ({', '.join(sorted(groups))}), so its header-level amount "
        f"'{mapping.amount_field}' cannot be assigned to one VAT group. Using the standard fields for this document."
    )
    return None

def map_sap_document_to_canonical_rows(
    raw_document: Dict[str, Any],
    source_document_type: str,
    endpoint_name: str,
    reconciliation_type: str = "sales",
    reconciliation_session_id: str = "N/A",
    purchase_cu_source: str = "U_CUINV",
    base_amount_policy: str | None = None,
    vat_normalizer_override: "VatNormalizer | None" = None,
    unmapped_vat_policy: str | None = None,
    field_mapping: PurchaseFieldMapping | None = None,
    stats: Dict[str, int] | None = None,
) -> List[CanonicalReconciliationRow]:
    """
    Flattens a raw SAP document and maps it to a list of CanonicalReconciliationRow objects.
    Applies configurable base amount policies, aggregates by VAT group, applies sign normalization,
    and warns on missing/invalid fields.

    ``field_mapping`` swaps in configured VAT code / amount fields (purchases only). Where a
    configured field is empty the standard fields are used, and ``stats`` (if given) counts
    documents under "custom" and "fallback".
    """
    settings = get_settings()
    # Per-company policy from system_settings takes precedence; falls back to the
    # global env setting (SAP_BASE_AMOUNT_POLICY) when no explicit policy is passed.
    # Unwrap the enum before comparing: str() on a (str, Enum) member yields
    # "BaseAmountPolicy.SKIP", so comparing str(policy) against "skip" never matched
    # and every company silently fell through to the permissive ALLOW branch.
    policy = (
        str(getattr(base_amount_policy, "value", base_amount_policy)).lower()
        if base_amount_policy is not None
        else settings.sap_base_amount_policy.value
    )

    # Request-local normalizer carrying this company's configured VAT mappings;
    # falls back to the built-in defaults when none was resolved.
    normalizer = vat_normalizer_override or vat_normalizer

    # Extract header fields
    invoice_number_raw = raw_document.get("DocNum")
    if invoice_number_raw is None:
        raise SAPQueryError(f"SAP {source_document_type} is missing required field: DocNum")
    invoice_number = str(invoice_number_raw).strip()

    partner_name_raw = raw_document.get("CardName")
    partner_name = str(partner_name_raw).strip() if partner_name_raw is not None else ""

    doc_date_raw = raw_document.get("DocDate")
    if doc_date_raw is None:
        raise SAPQueryError(f"SAP {source_document_type} {invoice_number} is missing required field: DocDate")

    try:
        invoice_date = parse_sap_date(doc_date_raw)
    except ValueError as exc:
        raise SAPQueryError(f"SAP {source_document_type} {invoice_number} has invalid DocDate: {exc}")

    # Fallbacks and warnings for PIN
    raw_pin = raw_document.get("FederalTaxID")
    if not raw_pin:
        pin = ""
        logger.warning(
            f"[ReconciliationSession: {reconciliation_session_id}] {source_document_type} {invoice_number} has missing FederalTaxID; using empty string."
        )
    else:
        pin = str(raw_pin).strip()

    # CU Number (Relaxed validation, allows empty/missing)
    # For purchases, the source SAP field is configurable (purchase_cu_source);
    # for sales the caller passes "U_CUINV" (the standard field).
    cu_number = extract_cu_number(raw_document, purchase_cu_source)

    document_lines = raw_document.get("DocumentLines", [])
    if not document_lines:
        logger.warning(
            f"[ReconciliationSession: {reconciliation_session_id}] {source_document_type} {invoice_number} has no DocumentLines."
        )
        return []

    # Determine exact document type (differentiate Debit Memos from standard Invoices)
    actual_document_type = source_document_type
    subtype = raw_document.get("DocumentSubType")
    if source_document_type == "Invoice" and subtype == "bod_DebitMemo":
        actual_document_type = "DebitNote"

    mapping = field_mapping if field_mapping and field_mapping.is_custom else None
    vat_args = (source_document_type, invoice_number, reconciliation_type, reconciliation_session_id, normalizer, unmapped_vat_policy)

    # (location label, vat group, base amount) per line, or a single header entry.
    line_values: List[tuple[str, str, Decimal]] = []
    used_fallback = False
    header_entry = None
    if mapping and mapping.amount_is_header:
        # Header-level amount: one row per document, under the document's single VAT group.
        amount_raw = _present(raw_document.get(mapping.amount_field))
        vat_group = _document_vat_group(raw_document, document_lines, mapping, vat_args) if amount_raw is not None else None
        if vat_group is not None:
            header_entry = (
                "header",
                vat_group,
                _parse_amount(amount_raw, mapping.amount_field, "header", source_document_type, invoice_number),
            )
        used_fallback = header_entry is None

    if header_entry is not None:
        line_values.append(header_entry)
    else:
        # A header-level mapping that fell back uses the standard fields on every line.
        line_mapping = mapping if mapping and not mapping.amount_is_header else None
        for line_idx, line in enumerate(document_lines):
            custom = _custom_line_values(raw_document, line, line_mapping) if line_mapping else None
            if line_mapping and custom is None:
                used_fallback = True
            vat_raw, amount_raw = custom if custom is not None else (None, None)

            # 1. VAT group: configured field, else the standard tax fields
            if vat_raw is not None:
                vat_group_str = _resolve_custom_vat_code(vat_raw, f"line {line_idx}", *vat_args)
            else:
                vat_group_str = _standard_line_vat_group(line, line_idx, *vat_args)

            # 2. Base Amount: configured field, else LineTotal
            if amount_raw is not None:
                base_amount = _parse_amount(
                    amount_raw, line_mapping.amount_field, f"line {line_idx}", source_document_type, invoice_number
                )
            else:
                line_total_raw = line.get("LineTotal")
                if line_total_raw is None:
                    raise SAPQueryError(
                        f"SAP {source_document_type} {invoice_number} line {line_idx} is missing required field: LineTotal"
                    )
                base_amount = _parse_amount(line_total_raw, "LineTotal", f"line {line_idx}", source_document_type, invoice_number)

            line_values.append((f"line {line_idx}", vat_group_str, base_amount))

    if stats is not None and mapping:
        key = "fallback" if used_fallback else "custom"
        stats[key] = stats.get(key, 0) + 1

    valid_lines = []
    for location, vat_group_str, base_amount in line_values:
        # 3. Base Amount Policy Check
        # Negative base amounts (e.g. Credit Notes, adjustments) are explicitly allowed.
        # Zero base amounts are filtered or rejected based on policy.
        if base_amount == 0:
            if policy == "skip":
                logger.warning(
                    f"[ReconciliationSession: {reconciliation_session_id}] {source_document_type} {invoice_number} {location} skipped because base_amount is 0.00 under policy 'skip'."
                )
                continue
            elif policy in ("reject", "reject_session"):
                logger.error(
                    f"[ReconciliationSession: {reconciliation_session_id}] {source_document_type} {invoice_number} {location} rejected because base_amount is 0.00 under policy 'reject'."
                )
                raise SAPQueryError(
                    f"SAP {source_document_type} {invoice_number} {location} rejected: Base Amount is zero."
                )
            # Under ALLOW ("allow") or TREAT_AS_ZERO, zero amount lines are kept and processed

        valid_lines.append((vat_group_str, base_amount))

    # Group by normalized VAT Group and sum LineTotal
    grouped_totals = {}
    for vat_group_str, base_amount in valid_lines:
        grouped_totals[vat_group_str] = grouped_totals.get(vat_group_str, Decimal("0.00")) + base_amount

    # Create canonical reconciliation rows
    canonical_rows = []
    for vat_group_str, total_amount in grouped_totals.items():
        # Sign normalization: +abs for Invoices/DebitNotes, -abs for CreditNotes
        if actual_document_type in ("Invoice", "DebitNote"):
            normalized_amount = abs(total_amount)
        elif actual_document_type == "CreditNote":
            normalized_amount = -abs(total_amount)
        else:
            normalized_amount = abs(total_amount)

        provenance = IngestionProvenance(
            session_source=f"SAP {reconciliation_type.capitalize()}",
            source_endpoint=endpoint_name,
            source_table=None,
            sap_object_type=None,
            source_document_type=actual_document_type,
            doc_entry=raw_document.get("DocEntry"),
            doc_num=invoice_number,
            base_doc_entry=None,
            base_doc_num=None,
            doc_object_code=None,
            raw_amount=total_amount,
            normalized_amount=normalized_amount
        )

        row = CanonicalReconciliationRow(
            pin=pin,
            partner_name=partner_name,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            cu_number=cu_number,
            vat_group=vat_group_str,
            base_amount=normalized_amount.quantize(Decimal("0.01")),
            provenance=provenance
        )
        canonical_rows.append(row)

    return canonical_rows


