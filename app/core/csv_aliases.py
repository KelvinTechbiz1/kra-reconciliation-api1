# Configuration of aliases for mapping KRA CSV headers to Invoice fields.
# Keys are the Pydantic Invoice model attributes.
# Values are lists of case-insensitive alias strings matching various KRA header versions.

FIELD_ALIASES = {
    "pin": ["Pin Number", "Supplier PIN", "Seller PIN", "Customer PIN", "PinNumber", "PIN"],
    "partner_name": ["Customer Name", "Supplier Name", "Seller Name", "Vendor Name", "CustomerName", "SupplierName"],
    "invoice_number": ["Invoice Number", "Document Number", "InvoiceNumber", "DocNum", "DocumentNumber"],
    "invoice_date": ["Invoice Date", "Document Date", "InvoiceDate", "DocDate", "DocumentDate"],
    "cu_number": ["CU Number", "Control Unit Number", "CUNumber", "ControlUnitNumber"],
    "vat_group": ["VAT Group", "Tax Group", "VATGroup", "TaxGroup", "TaxPercentagePerRow", "Tax Percentage Per Row"],
    "base_amount": ["Base Amount", "Line Total", "Amount", "BaseAmount", "LineTotal"]
}
