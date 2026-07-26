import io
import pandas as pd
from datetime import date
from decimal import Decimal

from app.models.import_profile import SourceFormat
from app.schemas.import_profile import (
    CanonicalColumnMappingSchema,
    ImportProfileSnapshot,
    ParsingHintsSchema,
    SalesValidationRulesSchema,
)
from app.schemas.invoice import InvoiceSource, ReconciliationType
from app.services.erp_import_service import ERPImportService


def test_parse_csv_file_with_snapshot():
    snapshot = ImportProfileSnapshot(
        profile_id=1,
        profile_name="Zoho Books - Sales",
        profile_version=1,
        module=ReconciliationType.SALES,
        provider="ZOHO",
        source_format=SourceFormat.CSV,
        parsing_hints=ParsingHintsSchema(has_header=True, header_row=1, data_start_row=2, delimiter=","),
        column_mapping=CanonicalColumnMappingSchema(
            pin=["Customer PIN", "PIN"],
            partner_name=["Customer Name", "Customer"],
            invoice_number=["Invoice Number", "Invoice No"],
            invoice_date=["Invoice Date", "Date"],
            cu_number=["CU Number", "ETR Number"],
            vat_group=["Tax Rate", "VAT Code"],
            base_amount=["SubTotal", "Taxable Amount"],
        ),
        validation_rules=SalesValidationRulesSchema(),
    )

    csv_content = (
        "Customer PIN,Customer Name,Invoice Number,Invoice Date,CU Number,Tax Rate,SubTotal\n"
        "P051234567A,Acme Corp,INV-001,2026-01-15,CU001,16,10000.50\n"
        "P059876543Z,Beta Ltd,INV-002,2026-01-20,CU002,EXEMPT,25000.00\n"
    )

    invoices, errors = ERPImportService.parse_erp_file(csv_content.encode("utf-8"), "sales.csv", snapshot)
    assert len(errors) == 0
    assert len(invoices) == 2

    assert invoices[0].pin == "P051234567A"
    assert invoices[0].partner_name == "Acme Corp"
    assert invoices[0].invoice_number == "INV-001"
    assert invoices[0].invoice_date == date(2026, 1, 15)
    assert invoices[0].cu_number == "CU001"
    assert invoices[0].base_amount == Decimal("10000.50")
    assert invoices[0].source == InvoiceSource.ERP
    assert invoices[0].provider == "ZOHO"


def test_preview_mapping_dry_run():
    snapshot = ImportProfileSnapshot(
        profile_id=1,
        profile_name="QuickBooks - Sales",
        profile_version=1,
        module=ReconciliationType.SALES,
        provider="QUICKBOOKS",
        source_format=SourceFormat.CSV,
        parsing_hints=ParsingHintsSchema(),
        column_mapping=CanonicalColumnMappingSchema(
            pin=["Tax Reg No", "PIN"],
            partner_name=["Customer"],
            invoice_number=["No.", "Invoice No"],
            invoice_date=["Date"],
            cu_number=["CU Number"],
            vat_group=["Tax Code"],
            base_amount=["Amount"],
        ),
        validation_rules=SalesValidationRulesSchema(),
    )

    csv_content = (
        "Tax Reg No,Customer,No.,Date,CU Number,Tax Code,Amount\n"
        "P051111111A,Global Tech,QB-101,2026-02-01,CU99,16,5000.00\n"
    )

    preview = ERPImportService.preview_mapping(csv_content.encode("utf-8"), "qb.csv", snapshot)
    assert preview.is_valid is True
    assert preview.total_rows_detected == 1
    assert len(preview.preview_samples) == 1
    assert preview.preview_samples[0].mapped_invoice["invoice_number"] == "QB-101"
    assert preview.preview_samples[0].mapped_invoice["base_amount"] == 5000.0
