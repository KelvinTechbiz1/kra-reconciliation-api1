from typing import Any


def canonical_cu_number(value: Any) -> str:
    """
    Canonicalizes a CU (Control Unit) invoice number so the SAP and KRA sides key the
    same reconciliation group regardless of which format the source rendered.

    Two shapes reach us from the KRA iTax portal:
      - TIMS:  "|0040073470000188183"            -> "0040073470000188183"
      - eTIMS: "|KRACU0300007406/56775"          -> "56775"

    The eTIMS form prefixes the CU invoice number with the *device* serial. SAP records
    only the number itself, so leaving the prefix on made every eTIMS row either pair by
    the amount/partner fallback and report CU Mismatch, or fail to pair at all. Anything
    before the final "/" is therefore dropped.

    Also strips the leading "|" that both the portal CSVs and the SAP UDF convention put
    in front of the value.

    Note: an eTIMS sequence is unique per device, not globally, so two suppliers can in
    principle share one. Because this is applied to both sides identically, such a
    collision groups the same rows on both sides and still reconciles.
    """
    if value is None:
        return ""

    text = str(value).strip().lstrip("|").strip()
    if not text:
        return ""

    if "/" in text:
        head, _, tail = text.rpartition("/")
        # A trailing slash carries no number after it; fall back to the prefix rather
        # than turn the row into a "Missing CU Number" exception.
        return tail.strip() or head.strip()

    return text
