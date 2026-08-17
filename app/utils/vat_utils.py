from decimal import Decimal, InvalidOperation
from typing import Any

def normalize_vat_rate(value: Any) -> str:
    """
    Parses, normalizes, and validates a VAT rate input into its canonical string representation.
    
    Accepts formats like:
      - "16", "16%", 16, 16.0
      - "EXEMPT", "exempt"
      
    Returns canonical format:
      - "16", "12.5", "0", "EXEMPT"
      
    Raises ValueError for invalid, negative, non-finite, or malformed rates.
    """
    if value is None:
        raise ValueError("VAT rate cannot be None.")
        
    # 1. Parse and fast-path EXEMPT
    str_val = str(value).strip().upper()
    if str_val in ("EXEMPT", "EXEMPTED", "EXEMPTION", "EX", "E") or "EXEMPT" in str_val:
        return "EXEMPT"
        
    # 2. Pre-process numeric formats
    if str_val.endswith("%"):
        str_val = str_val[:-1].strip()
        
    # 3. Normalize using Decimal to avoid float precision issues
    try:
        dec_val = Decimal(str_val)
    except InvalidOperation:
        raise ValueError(f"Invalid VAT rate format: '{value}'")
        
    # 4. Validate business rules
    if not dec_val.is_finite():
        raise ValueError("VAT rate must be a finite number.")
        
    if dec_val < 0:
        raise ValueError("VAT rate cannot be negative.")
        
    # Example upper limit (sanity check)
    if dec_val > 100:
        raise ValueError("VAT rate cannot exceed 100%.")
        
    # 5. Format to canonical string
    # normalize() removes trailing zeros, e.g., 16.0 -> 16
    canonical_dec = dec_val.normalize()
    
    # Decimal.normalize() turns 0.0 into 0E+1 or similar in some versions,
    # so we format it explicitly, or rely on formatting.
    # To be safe, formatting as float/int string:
    if canonical_dec == canonical_dec.to_integral():
        return str(int(canonical_dec))
    return str(canonical_dec)


def canonical_vat_key(value: Any) -> str:
    """
    Lenient canonicalization used to key reconciliation tax breakdowns.

    Canonicalizes anything `normalize_vat_rate` understands ("16.00", "16%", "16.0"
    and "exempt" all collapse onto "16"/"EXEMPT"), so the same economic rate produces
    the same bucket key regardless of which ingest path produced it.

    Unlike `normalize_vat_rate` this never raises: an unrecognized company-specific
    code (e.g. "A16") is passed through uppercased rather than failing the load.
    Blank input yields "".

    NOTE: only ever pass a SINGLE rate here. `normalize_vat_rate` treats any string
    containing "EXEMPT" as exempt, so a joined multi-bucket label like "0, EXEMPT"
    would collapse to "EXEMPT" and lose the zero-rated portion.
    """
    if value is None:
        return ""

    str_val = str(value).strip()
    if not str_val:
        return ""

    try:
        return normalize_vat_rate(str_val)
    except ValueError:
        return str_val.upper()
