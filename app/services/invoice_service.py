from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
import logging
import time

from app.core.config import get_settings
from app.schemas.invoice import Invoice, InvoiceSource, ReconciliationType
from app.core.sap_client import SAPClient
from app.services.sap_mapper import map_sap_document_to_canonical_rows
from app.services.normalization import normalize_invoice_data

logger = logging.getLogger(__name__)


def _fetch_endpoint_invoices(
    sap_client_clone: SAPClient,
    endpoint_name: str,
    source_doc_type: str,
    from_date: date,
    to_date: date,
    reconciliation_type: ReconciliationType,
    reconciliation_session_id: str,
    cu_field: str,
    page_size: int,
) -> tuple[list[Invoice], int, int, int, float]:
    start_time = time.perf_counter()
    endpoint_invoices = []
    raw_doc_count = 0
    flattened_line_count = 0
    page_count = 0

    raw_pages = sap_client_clone.get_documents_pages(
        from_date.isoformat(),
        to_date.isoformat(),
        endpoint_name=endpoint_name,
        page_size=page_size,
        reconciliation_session_id=reconciliation_session_id,
        cu_field=cu_field,
    )

    for raw_page in raw_pages:
        page_count += 1
        raw_doc_count += len(raw_page)
        for raw_doc in raw_page:
            try:
                canonical_rows = map_sap_document_to_canonical_rows(
                    raw_doc,
                    source_document_type=source_doc_type,
                    endpoint_name=endpoint_name,
                    reconciliation_type=reconciliation_type.value,
                    reconciliation_session_id=reconciliation_session_id,
                    purchase_cu_source=cu_field,
                )
                for row in canonical_rows:
                    normalized = normalize_invoice_data(
                        pin=row.pin,
                        partner_name=row.partner_name,
                        invoice_number=row.invoice_number,
                        invoice_date=row.invoice_date,
                        cu_number=row.cu_number,
                        vat_group=row.vat_group,
                        base_amount=row.base_amount,
                        allow_negative=True,
                    )
                    invoice = Invoice(**normalized, source=InvoiceSource.SAP)
                    if from_date <= invoice.invoice_date <= to_date:
                        endpoint_invoices.append(invoice)
                        flattened_line_count += 1
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

    elapsed = time.perf_counter() - start_time
    avg_page_time = (elapsed / page_count) if page_count > 0 else 0.0
    logger.info(
        f"[ReconciliationSession: {reconciliation_session_id}] {endpoint_name} ({source_doc_type}) metrics: "
        f"Pages: {page_count}, Documents: {raw_doc_count}, Reconciliation Rows: {len(endpoint_invoices)}, "
        f"Total Time: {elapsed:.2f}s, Avg Page Time: {avg_page_time:.2f}s"
    )
    return endpoint_invoices, raw_doc_count, flattened_line_count, page_count, elapsed


def get_invoices(
    from_date: date,
    to_date: date,
    reconciliation_type: ReconciliationType = ReconciliationType.SALES,
    sap_client: SAPClient = None,
    reconciliation_session_id: str = "N/A",
    sales_cu_source: str = "U_CUINV",
    purchase_cu_source: str = "U_CUINV",
    page_size: int | None = None,
) -> list[Invoice]:
    """
    Fetches Invoices and Credit Notes (Sales or Purchases) in parallel page-by-page from SAP Service Layer,
    maps them to CanonicalReconciliationRows, and returns a flattened list of Invoice objects.
    """
    if sap_client is None:
        sap_client = SAPClient()

    if page_size is None:
        page_size = get_settings().sap_page_size

    total_start_time = time.perf_counter()
    logger.info(
        f"[ReconciliationSession: {reconciliation_session_id}] Starting parallel SAP fetch for {reconciliation_type.value} (page_size={page_size})..."
    )

    endpoints = []
    if reconciliation_type == ReconciliationType.SALES:
        endpoints = [("Invoices", "Invoice"), ("CreditNotes", "CreditNote")]
    else:
        endpoints = [("PurchaseInvoices", "Invoice"), ("PurchaseCreditNotes", "CreditNote")]

    cu_field = sales_cu_source if reconciliation_type == ReconciliationType.SALES else purchase_cu_source

    all_invoices = []
    total_raw_documents = 0
    total_flattened_lines = 0
    total_pages = 0

    with ThreadPoolExecutor(max_workers=len(endpoints)) as executor:
        futures = [
            executor.submit(
                _fetch_endpoint_invoices,
                sap_client_clone=sap_client.clone(),
                endpoint_name=endpoint_name,
                source_doc_type=source_doc_type,
                from_date=from_date,
                to_date=to_date,
                reconciliation_type=reconciliation_type,
                reconciliation_session_id=reconciliation_session_id,
                cu_field=cu_field,
                page_size=page_size,
            )
            for endpoint_name, source_doc_type in endpoints
        ]

        for future in as_completed(futures):
            ep_invoices, raw_cnt, line_cnt, pages_cnt, _ = future.result()
            all_invoices.extend(ep_invoices)
            total_raw_documents += raw_cnt
            total_flattened_lines += line_cnt
            total_pages += pages_cnt

    total_elapsed = time.perf_counter() - total_start_time
    logger.info(
        f"[ReconciliationSession: {reconciliation_session_id}] Parallel SAP fetch complete: "
        f"Total Pages: {total_pages}, Total Documents: {total_raw_documents}, "
        f"Total Flattened Rows: {total_flattened_lines}, Total Time: {total_elapsed:.2f}s"
    )
    logger.info(f"[ReconciliationSession: {reconciliation_session_id}] Returned {len(all_invoices)} normalized records to caller")

    return all_invoices

