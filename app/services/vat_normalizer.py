from enum import Enum
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.settings import VATMapping, VatModule
from app.utils.vat_utils import canonical_vat_key


class DocumentType(str, Enum):
    SALES = "sales"
    PURCHASES = "purchases"


class VatNormalizer:
    """
    Normalizes SAP company-specific VAT group codes to canonical percentage strings
    or "EXEMPT". Keeps reconciliation logic ERP-agnostic. Supports dynamic database mappings.
    """

    _DEFAULT_INPUT_MAP: Dict[str, str] = {
        "I1": "16",
        "I2": "0",
        "I3": "8",
        "X1": "EXEMPT",
        "N2": "16",
    }

    _DEFAULT_OUTPUT_MAP: Dict[str, str] = {
        "O1": "16",
        "O2": "0",
        "X0": "EXEMPT",
    }

    def __init__(self, input_map: Optional[Dict[str, str]] = None, output_map: Optional[Dict[str, str]] = None):
        self._input = {k.upper(): v for k, v in (input_map or self._DEFAULT_INPUT_MAP).items()}
        self._output = {k.upper(): v for k, v in (output_map or self._DEFAULT_OUTPUT_MAP).items()}

    def load_from_db(self, db: Session, connection_id: int) -> None:
        """
        Load this instance's mapping tables from the vat_mappings rows belonging to
        one SAP connection.

        `connection_id` is REQUIRED: VATMapping.connection_id is scoped to a company's
        SAP connection, so an unfiltered query would blend VAT codes across tenants.

        Falls back to the built-in defaults for whichever module has no configured
        rows, so a partially-configured company still resolves standard codes.
        """
        mappings = (
            db.query(VATMapping)
            .filter(VATMapping.connection_id == connection_id)
            .all()
        )
        if not mappings:
            return

        db_input = {}
        db_output = {}
        for m in mappings:
            display_val = m.canonical_rate
            if m.module == VatModule.PURCHASES or m.module == "purchases":
                db_input[m.sap_code.strip().upper()] = display_val
            else:
                db_output[m.sap_code.strip().upper()] = display_val

        if db_input:
            self._input = db_input
        if db_output:
            self._output = db_output

    @staticmethod
    def _normalize_raw_value(val: str) -> str:
        """
        Normalize raw VAT strings, percentages, decimals, and exempt terms.
        Distinguishes Zero Rated ('0') from Exempt ('EXEMPT').
        """
        return canonical_vat_key(val)

    def is_mapped(self, source: str, document_type: str, value: str) -> bool:
        """Whether this code resolves through a configured/built-in mapping rather than falling back."""
        if source.lower() != "sap":
            return False
        code = value.strip().upper()
        mapping = self._input if document_type == "purchases" else self._output
        return bool(code) and code in mapping

    def normalize(self, source: str, document_type: str, value: str) -> str:
        """
        Normalize a VAT code string.

        Args:
            source: ERP source identifier (e.g. "sap", "kra").
            document_type: "sales" or "purchases".
            value: Raw VAT code string (e.g. "I1", "O1", "16.0", "16%", "EXEMPT").

        Returns:
            Normalized VAT string (e.g. "16", "8", "0", "EXEMPT").

        Mappings are loaded once per request via `load_from_db` on a request-local
        instance; this method never mutates state.
        """
        code = value.strip().upper()
        if not code:
            return ""

        if source.lower() == "sap":
            mapping = self._input if document_type == "purchases" else self._output
            if code in mapping:
                return mapping[code]

        return self._normalize_raw_value(value)


# Module-level singleton holding only the built-in defaults.
# Used as the zero-config fallback. Never call load_from_db on it — per-company
# mappings belong on a request-local instance (see api/v1/_session_helpers.py).
vat_normalizer = VatNormalizer()
