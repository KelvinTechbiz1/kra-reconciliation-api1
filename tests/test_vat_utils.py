import pytest
from app.utils.vat_utils import canonical_vat_key, normalize_vat_rate

def test_normalize_vat_rate_valid():
    # Valid exact strings
    assert normalize_vat_rate("16") == "16"
    assert normalize_vat_rate("8") == "8"
    assert normalize_vat_rate("0") == "0"
    
    # Decimals
    assert normalize_vat_rate("12.5") == "12.5"
    assert normalize_vat_rate("12.50") == "12.5"
    assert normalize_vat_rate("12.0") == "12"
    
    # Percentages
    assert normalize_vat_rate("16%") == "16"
    assert normalize_vat_rate(" 12.5% ") == "12.5"
    assert normalize_vat_rate("0%") == "0"
    
    # Exempt
    assert normalize_vat_rate("EXEMPT") == "EXEMPT"
    assert normalize_vat_rate("exempt") == "EXEMPT"
    assert normalize_vat_rate(" Exempt ") == "EXEMPT"

def test_normalize_vat_rate_idempotency():
    inputs = ["16", "16%", "16.0", "12.5", "12.50%", "0", "0%", "EXEMPT", "exempt"]
    for val in inputs:
        first = normalize_vat_rate(val)
        second = normalize_vat_rate(first)
        assert first == second

def test_normalize_vat_rate_invalid():
    # Negatives
    with pytest.raises(ValueError, match="cannot be negative"):
        normalize_vat_rate("-16")
        
    # Greater than 100%
    with pytest.raises(ValueError, match="cannot exceed 100"):
        normalize_vat_rate("105")
        
    # Malformed strings
    with pytest.raises(ValueError, match="Invalid VAT rate format"):
        normalize_vat_rate("VAT16")
    
    with pytest.raises(ValueError, match="Invalid VAT rate format"):
        normalize_vat_rate("abc")
        
    with pytest.raises(ValueError, match="Invalid VAT rate format"):
        normalize_vat_rate("16 percent")
        
    # Non-finite values
    with pytest.raises(ValueError, match="finite number"):
        normalize_vat_rate("Infinity")
        
    with pytest.raises(ValueError, match="finite number"):
        normalize_vat_rate("NaN")


# --- canonical_vat_key: lenient canonicalization for reconciliation bucket keys ---

@pytest.mark.parametrize("raw,expected", [
    # Numeric format variants all collapse onto the same key
    ("16", "16"),
    ("16.0", "16"),
    ("16.00", "16"),
    ("16%", "16"),
    (" 16 ", "16"),
    (16, "16"),
    (16.0, "16"),
    ("12.5", "12.5"),
    ("12.50", "12.5"),
    ("0", "0"),
    ("0.0", "0"),
    # Exempt normalizes independently of case
    ("EXEMPT", "EXEMPT"),
    ("exempt", "EXEMPT"),
    ("Exempted", "EXEMPT"),
    # Blank input yields an empty key rather than raising
    ("", ""),
    ("   ", ""),
    (None, ""),
])
def test_canonical_vat_key_canonicalizes(raw, expected):
    assert canonical_vat_key(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("A16", "A16"),
    ("a16", "A16"),
    ("I1", "I1"),
    ("O1", "O1"),
    ("ZERO_RATED", "ZERO_RATED"),
    ("VAT16", "VAT16"),
    # Out-of-range and malformed values that normalize_vat_rate rejects must not raise here
    ("-16", "-16"),
    ("105", "105"),
    ("NaN", "NAN"),
])
def test_canonical_vat_key_is_lenient_for_unknown_codes(raw, expected):
    """Unknown company-specific codes pass through uppercased instead of raising.

    normalize_vat_rate raises on these; canonical_vat_key must not, otherwise an
    unmapped SAP VAT code would fail an entire invoice load.
    """
    assert canonical_vat_key(raw) == expected


def test_canonical_vat_key_must_not_receive_joined_multi_rate_labels():
    """Documents the substring trap: never pass a joined multi-bucket label.

    normalize_vat_rate treats any string containing "EXEMPT" as exempt, so a joined
    label collapses and silently loses the zero-rated portion. Callers must pass one
    rate at a time.
    """
    assert canonical_vat_key("0, EXEMPT") == "EXEMPT"
