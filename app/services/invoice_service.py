from datetime import date
import logging
from app.schemas.invoice import Invoice, InvoiceSource, ReconciliationType
from app.core.sap_client import SAPClient
from app.services.sap_mapper import map_sap_document_to_canonical_rows
from app.services.normalization import normalize_invoice_data

logger = logging.getLogger(__name__)


def get_invoices(
    from_date: date,
    to_date: date,
    reconciliation_type: ReconciliationType = ReconciliationType.SALES,
    sap_client: SAPClient = None,
    reconciliation_session_id: str = "N/A",
    sales_cu_source: str = "U_CUINV",
    purchase_cu_source: str = "U_CUINV",
) -> list[Invoice]:
    """
    Fetches Invoices and Credit Notes (Sales or Purchases) page-by-page from SAP Service Layer, maps them
    to CanonicalReconciliationRows, and returns a flattened list of Invoice objects.
    """
    if sap_client is None:
        sap_client = SAPClient()

    logger.info(f"[ReconciliationSession: {reconciliation_session_id}] Login to SAP Service Layer...")

    invoices = []
    total_raw_documents = 0
    total_flattened_lines = 0

    endpoints = []
    if reconciliation_type == ReconciliationType.SALES:
        endpoints = [("Invoices", "Invoice"), ("CreditNotes", "CreditNote")]
    else:
        endpoints = [("PurchaseInvoices", "Invoice"), ("PurchaseCreditNotes", "CreditNote")]

    # The CU source is configurable for both sales and purchases.
    cu_field = sales_cu_source if reconciliation_type == ReconciliationType.SALES else purchase_cu_source

    for endpoint_name, source_doc_type in endpoints:
        raw_pages = sap_client.get_documents_pages(
            from_date.isoformat(),
            to_date.isoformat(),
            endpoint_name=endpoint_name,
            reconciliation_session_id=reconciliation_session_id,
            cu_field=cu_field,
        )

        for raw_page in raw_pages:
            total_raw_documents += len(raw_page)
            for raw_doc in raw_page:
                try:
                    # 1. Map/Flatten raw SAP document to CanonicalReconciliationRow objects
                    canonical_rows = map_sap_document_to_canonical_rows(
                        raw_doc,
                        source_document_type=source_doc_type,
                        endpoint_name=endpoint_name,
                        reconciliation_type=reconciliation_type.value,
                        reconciliation_session_id=reconciliation_session_id,
                        purchase_cu_source=cu_field,
                    )

                    # 2. Construct Invoice objects
                    for row in canonical_rows:
                        # Normalize string fields using normalize_invoice_data for validation/formatting
                        normalized = normalize_invoice_data(
                            pin=row.pin,
                            partner_name=row.partner_name,
                            invoice_number=row.invoice_number,
                            invoice_date=row.invoice_date,
                            cu_number=row.cu_number,
                            vat_group=row.vat_group,
                            base_amount=row.base_amount,
                            allow_negative=True # We now explicitly allow negative amounts
                        )
                        # Build internal schema
                        invoice = Invoice(**normalized, source=InvoiceSource.SAP)

                        # Double-safeguard date filtering
                        if from_date <= invoice.invoice_date <= to_date:
                            invoices.append(invoice)
                            total_flattened_lines += 1
                except ValueError as ve:
                    logger.error(
                        f"[ReconciliationSession: {reconciliation_session_id}] Normalization failed for SAP record from document {raw_doc.get('DocNum')}: {ve}"
                    )
                    raise
                except Exception as e:
                    logger.error(
                        f"[ReconciliationSession: {reconciliation_session_id}] Error processing SAP document from {endpoint_name}: {e}"
                    )
                    raise

    logger.info(f"[ReconciliationSession: {reconciliation_session_id}] Fetched {total_raw_documents} documents from SAP")
    logger.info(f"[ReconciliationSession: {reconciliation_session_id}] Flattened into {total_flattened_lines} reconciliation rows")
    logger.info(f"[ReconciliationSession: {reconciliation_session_id}] Returned {len(invoices)} normalized records to caller")

    return invoices

