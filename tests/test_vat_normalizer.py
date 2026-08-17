import pytest
from app.services.vat_normalizer import VatNormalizer, DocumentType


class TestVatNormalizer:
    def setup_method(self):
        self.normalizer = VatNormalizer()

    def test_input_vat_purchase_i1(self):
        assert self.normalizer.normalize("sap", "purchases", "I1") == "16"

    def test_input_vat_purchase_i2(self):
        assert self.normalizer.normalize("sap", "purchases", "I2") == "0"

    def test_input_vat_purchase_i3(self):
        assert self.normalizer.normalize("sap", "purchases", "I3") == "8"

    def test_input_vat_purchase_x1(self):
        assert self.normalizer.normalize("sap", "purchases", "X1") == "EXEMPT"

    def test_output_vat_sales_o1(self):
        assert self.normalizer.normalize("sap", "sales", "O1") == "16"

    def test_output_vat_sales_o2(self):
        assert self.normalizer.normalize("sap", "sales", "O2") == "0"

    def test_output_vat_sales_x0(self):
        assert self.normalizer.normalize("sap", "sales", "X0") == "EXEMPT"

    def test_case_insensitive(self):
        assert self.normalizer.normalize("sap", "purchases", "i1") == "16"
        assert self.normalizer.normalize("sap", "sales", "o1") == "16"

    def test_unknown_code_passthrough(self):
        assert self.normalizer.normalize("sap", "purchases", "A16") == "A16"

    def test_already_normalized_value_passthrough(self):
        assert self.normalizer.normalize("sap", "purchases", "16") == "16"

    def test_percent_sign_normalization(self):
        assert self.normalizer.normalize("sap", "purchases", "16%") == "16"
        assert self.normalizer.normalize("sap", "purchases", "8%") == "8"
        assert self.normalizer.normalize("sap", "purchases", "0%") == "0"

    def test_decimal_float_normalization(self):
        assert self.normalizer.normalize("sap", "purchases", "16.0") == "16"
        assert self.normalizer.normalize("sap", "purchases", "16.00") == "16"
        assert self.normalizer.normalize("sap", "purchases", "8.0") == "8"
        assert self.normalizer.normalize("sap", "purchases", "0.0") == "0"

    def test_exempt_keyword_normalization(self):
        assert self.normalizer.normalize("sap", "purchases", "EXEMPT") == "EXEMPT"
        assert self.normalizer.normalize("sap", "purchases", "Exempted") == "EXEMPT"
        assert self.normalizer.normalize("sap", "purchases", "EX") == "EXEMPT"
        assert self.normalizer.normalize("sap", "purchases", "E") == "EXEMPT"

    def test_distinction_between_zero_and_exempt(self):
        assert self.normalizer.normalize("sap", "purchases", "0") == "0"
        assert self.normalizer.normalize("sap", "purchases", "0.0") == "0"
        assert self.normalizer.normalize("sap", "purchases", "0%") == "0"
        assert self.normalizer.normalize("sap", "purchases", "EXEMPT") == "EXEMPT"
        assert self.normalizer.normalize("sap", "purchases", "I2") == "0"
        assert self.normalizer.normalize("sap", "purchases", "X1") == "EXEMPT"

    def test_empty_string(self):
        assert self.normalizer.normalize("sap", "purchases", "") == ""

    def test_whitespace_stripped(self):
        assert self.normalizer.normalize("sap", "purchases", " I1 ") == "16"

    def test_unknown_source_passthrough_normalized(self):
        assert self.normalizer.normalize("kra", "purchases", "16.0%") == "16"
        assert self.normalizer.normalize("kra", "purchases", "EXEMPT") == "EXEMPT"

    def test_custom_maps(self):
        custom = VatNormalizer(
            input_map={"I1": "VAT16", "I2": "VAT0"},
            output_map={"O1": "VAT16"},
        )
        assert custom.normalize("sap", "purchases", "I1") == "VAT16"
        assert custom.normalize("sap", "sales", "O1") == "VAT16"


class TestVatNormalizerDatabaseMappings:
    """Company-configured VAT mappings must actually reach the reconciliation engine.

    Regression guard: sap_mapper previously called normalize() without ever loading
    from the DB, so every custom code fell through to a passthrough and became its
    own tax bucket, producing false VAT mismatches.
    """

    @staticmethod
    def _make_db(tmp_path, mappings):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.database.base import Base
        from app.models.settings import VATMapping

        engine = create_engine(f"sqlite:///{tmp_path}/vat_map.db")
        Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine)()
        for module, sap_code, rate in mappings:
            db.add(VATMapping(connection_id=1, module=module, sap_code=sap_code,
                              description="", canonical_rate=rate))
        db.commit()
        return db

    def test_custom_code_resolves_after_load_from_db(self, tmp_path):
        from app.models.settings import VatModule

        normalizer = VatNormalizer()
        # Before loading, a company-specific code is unrecognized
        assert normalizer.normalize("sap", "purchases", "A16") == "A16"
        assert normalizer.is_mapped("sap", "purchases", "A16") is False

        db = self._make_db(tmp_path, [(VatModule.PURCHASES, "A16", "16")])
        normalizer.load_from_db(db, connection_id=1)

        assert normalizer.normalize("sap", "purchases", "A16") == "16"
        assert normalizer.is_mapped("sap", "purchases", "A16") is True
        db.close()

    def test_custom_exempt_code_resolves_to_exempt(self, tmp_path):
        from app.models.settings import VatModule

        db = self._make_db(tmp_path, [(VatModule.PURCHASES, "ZX", "EXEMPT")])
        normalizer = VatNormalizer()
        normalizer.load_from_db(db, connection_id=1)

        assert normalizer.normalize("sap", "purchases", "ZX") == "EXEMPT"
        db.close()

    def test_mappings_are_scoped_to_one_connection(self, tmp_path):
        """A company must never see another company's VAT codes."""
        from app.models.settings import VATMapping, VatModule

        db = self._make_db(tmp_path, [(VatModule.PURCHASES, "A16", "16")])
        # Another tenant's connection with a conflicting code
        db.add(VATMapping(connection_id=2, module=VatModule.PURCHASES,
                          sap_code="B8", description="", canonical_rate="8"))
        db.commit()

        normalizer = VatNormalizer()
        normalizer.load_from_db(db, connection_id=1)

        assert normalizer.normalize("sap", "purchases", "A16") == "16"
        # Connection 2's code must not leak into connection 1's normalizer
        assert normalizer.is_mapped("sap", "purchases", "B8") is False
        db.close()

    def test_load_from_db_does_not_mutate_the_shared_singleton(self, tmp_path):
        from app.models.settings import VatModule
        from app.services.vat_normalizer import vat_normalizer as shared

        db = self._make_db(tmp_path, [(VatModule.PURCHASES, "A16", "16")])
        local = VatNormalizer()
        local.load_from_db(db, connection_id=1)

        assert local.normalize("sap", "purchases", "A16") == "16"
        # The process-global singleton must be untouched by a per-request load
        assert shared.normalize("sap", "purchases", "A16") == "A16"
        db.close()
