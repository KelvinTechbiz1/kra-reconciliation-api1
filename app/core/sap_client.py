import datetime
import time
import logging
import urllib.parse
from typing import Any, Dict, Generator, List
import httpx

from app.core.config import get_settings
from app.core.exceptions import SAPConnectionError, SAPQueryError
from app.schemas.invoice import ReconciliationType

logger = logging.getLogger(__name__)


class SAPClient:
    """
    HTTP Client for connecting to the SAP Business One Service Layer.
    Handles Login authentication, dynamic session cookie caching, proactive session renewal,
    transient failure retries with exponential backoff, and OData pagination.
    """

    ENDPOINT_MAP = {
        ReconciliationType.SALES: "Invoices",
        ReconciliationType.PURCHASES: "PurchaseInvoices"
    }

    def __init__(
        self,
        base_url: str = "",
        username: str = "",
        password: str = "",
        company_db: str = "",
        verify_ssl: bool = True,
    ):
        self.base_url = str(base_url).rstrip("/") if base_url else ""
        self.username = username
        self.password = password
        self.company_db = company_db
        self.verify_ssl = verify_ssl

        # Initialize httpx Client
        self.client = httpx.Client(verify=self.verify_ssl, timeout=30.0)
        self.session_id = None
        self.cookies = {}
        self.session_expiry = None

    @classmethod
    def from_connection(cls, connection) -> "SAPClient":
        """Build a client from a per-company SAP connection record."""
        return cls(
            base_url=connection.base_url,
            username=connection.username,
            password=connection.password,
            company_db=connection.company_db,
            verify_ssl=connection.verify_ssl,
        )

    def clone(self) -> "SAPClient":
        """
        Creates a new independent SAPClient instance with matching connection parameters.
        State (session_id, cookies, session_expiry, httpx.Client) is NOT copied.
        """
        return SAPClient(
            base_url=self.base_url,
            username=self.username,
            password=self.password,
            company_db=self.company_db,
            verify_ssl=self.verify_ssl,
        )

    def login(self) -> None:
        """
        Logs in to the SAP Service Layer and caches session cookies and timeout.
        Raises SAPConnectionError on failure.
        """
        if not self.base_url:
            raise SAPConnectionError("SAP_BASE_URL is not configured.")

        login_url = f"{self.base_url}/Login"
        payload = {
            "CompanyDB": self.company_db,
            "UserName": self.username,
            "Password": self.password
        }

        logger.info("SAP Service Layer: Initiating Login request...")
        start_time = time.perf_counter()
        try:
            response = self.client.post(login_url, json=payload)
        except httpx.RequestError as exc:
            logger.error(f"SAP Service Layer Login failed due to connection error: {exc}")
            raise SAPConnectionError(f"Connection to SAP Service Layer failed: {exc}")

        if response.status_code != 200:
            logger.error(f"SAP Service Layer Login returned status {response.status_code}: {response.text}")
            raise SAPConnectionError(f"SAP Login failed (HTTP {response.status_code}): {response.text}")

        try:
            data = response.json()
        except ValueError:
            logger.error("SAP Service Layer Login returned invalid JSON.")
            raise SAPConnectionError("SAP Login failed: Service Layer did not return valid JSON.")

        self.session_id = data.get("SessionId")
        if not self.session_id:
            logger.error("SAP Service Layer Login response missing SessionId.")
            raise SAPConnectionError("SAP Login failed: Response missing SessionId.")

        self.cookies = dict(response.cookies)

        # Dynamic timeout renewal (B1 session timeout is in minutes)
        timeout_mins = int(data.get("SessionTimeout", 30))
        # Proactively refresh 2 minutes before expiry
        self.session_expiry = datetime.datetime.now() + datetime.timedelta(minutes=max(timeout_mins - 2, 1))
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        logger.info(f"SAP Service Layer: Login successful (took {elapsed_ms:.1f}ms).")

    def _ensure_session(self) -> None:
        """
        Ensures a valid session is active. Re-authenticates if expired.
        """
        if not self.session_id or not self.session_expiry or datetime.datetime.now() >= self.session_expiry:
            self.login()

    def _execute_request_with_retry(
        self, method: str, url: str, params: Dict[str, Any] = None, cookies: Dict[str, str] = None,
        headers: Dict[str, str] = None,
    ) -> httpx.Response:
        """
        Executes an HTTP request with transient retry logic (exponential backoff) for idempotent GETs.
        """
        attempts = 3
        backoff = 1.0

        for i in range(attempts):
            try:
                response = self.client.request(method, url, params=params, cookies=cookies, headers=headers)
                # Check for session expiration
                if response.status_code == 401:
                    logger.warning("SAP Service Layer session expired/invalid. Re-authenticating...")
                    self.login()
                    # Use new cookies
                    cookies = self.cookies
                    # Retry immediate request after re-login
                    response = self.client.request(method, url, params=params, cookies=cookies, headers=headers)

                if response.status_code == 200 or method != "GET":
                    return response

                # Retry for server errors (502, 503, 504)
                if response.status_code in (502, 503, 504) and method == "GET":
                    logger.warning(
                        f"SAP GET request returned {response.status_code}. Retry attempt {i+1} of {attempts}..."
                    )
                else:
                    return response
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                if method != "GET":
                    raise SAPConnectionError(f"SAP Request failed: {exc}")
                logger.warning(
                    f"SAP GET request failed due to connection/timeout error: {exc}. Retry attempt {i+1} of {attempts}..."
                )
                if i == attempts - 1:
                    raise SAPConnectionError(f"SAP Service Layer connection failed after {attempts} attempts: {exc}")

            time.sleep(backoff)
            backoff *= 2.0

        raise SAPConnectionError(f"SAP Service Layer returned transient error after {attempts} attempts.")

    def get_documents_pages(
        self,
        from_date: str,
        to_date: str,
        endpoint_name: str,
        page_size: int | None = None,
        reconciliation_session_id: str = "N/A",
        cu_field: str = "U_CUINV",
    ) -> Generator[List[Dict[str, Any]], None, None]:
        """
        Fetches SAP documents (Invoices or Credit Notes) page-by-page from Service Layer filtered by date range.
        Traverses @odata.nextLink exactly as returned by SAP.
        Yields raw document lists (pages) to keep memory footprint low.
        """
        if page_size is None:
            raise ValueError("page_size must be explicitly provided by caller (Settings/Service layer).")

        self._ensure_session()

        # OData filter query — Population Filter (exclude cancelled invoices based on default ingestion policy)
        # TODO: Move to configurable ingestion policy in settings if needed
        filter_str = f"DocDate ge '{from_date}' and DocDate le '{to_date}'  and Cancelled eq 'tNO'"
        params = {"$filter": filter_str}
        if page_size and page_size > 0:
            params["$top"] = str(page_size)

        # Try optimizing with $select if supported. Falling back if query returns HTTP 400.
        # cu_field is the configured SAP field holding the CU number (U_CUINV for sales,
        # configurable for purchases) so we only fetch what we need.
        select_str = f"FederalTaxID,CardName,DocNum,DocDate,{cu_field},DocumentLines,DocumentSubType"
        params_with_select = {**params, "$select": select_str}

        url = f"{self.base_url}/{endpoint_name}"
        next_url = url
        use_select = True

        logger.info(
            f"[ReconciliationSession: {reconciliation_session_id}] Fetching {endpoint_name} from SAP for range {from_date} to {to_date}"
        )

        page_number = 0
        total_rows = 0
        total_start = time.perf_counter()
        page_latencies = []
        total_json_parse = 0.0
        use_prefer = page_size and page_size > 0
        request_headers = {"Prefer": f"odata.maxpagesize={page_size}"} if use_prefer else None

        # When using Prefer: odata.maxpagesize, omit $top — SAP treats $top as a total limit
        # and would cap the result set. Prefer alone controls the page size.
        if use_prefer:
            params.pop("$top", None)
            params_with_select.pop("$top", None)

        while next_url:
            page_number += 1
            page_start = time.perf_counter()
            current_params = None
            if next_url == url:
                current_params = params_with_select if use_select else params
            else:
                # SAP treats $top as a total result limit, decrementing it per page.
                # Reset $top to the original page_size so pagination doesn't stop early.
                if page_size:
                    parsed = urllib.parse.urlparse(next_url)
                    query_params = dict(urllib.parse.parse_qsl(parsed.query))
                    if "$top" in query_params:
                        query_params["$top"] = str(page_size)
                        next_url = urllib.parse.urlunparse(
                            parsed._replace(query=urllib.parse.urlencode(query_params))
                        )

            # Build the effective request URL for logging
            req_url = next_url
            if current_params:
                parsed = urllib.parse.urlparse(next_url)
                existing_params = dict(urllib.parse.parse_qsl(parsed.query))
                merged = {**existing_params, **{k: v for k, v in current_params.items() if v is not None}}
                req_url = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(merged)))

            logger.info(
                f"[ReconciliationSession: {reconciliation_session_id}] Pagination page {page_number}: "
                f"GET {req_url}"
            )

            try:
                response = self._execute_request_with_retry(
                    "GET", next_url, params=current_params, cookies=self.cookies,
                    headers=request_headers,
                )
            except SAPConnectionError as exc:
                logger.error(
                    f"[ReconciliationSession: {reconciliation_session_id}] Connection error fetching SAP documents: {exc}"
                )
                raise

            # Fallback if $select is not supported (OData version mismatch / projection unsupported)
            if response.status_code == 400 and next_url == url and use_select:
                logger.warning(
                    f"[ReconciliationSession: {reconciliation_session_id}] SAP returned HTTP 400 with select projection. Retrying without $select projection..."
                )
                use_select = False
                continue

            if response.status_code != 200:
                logger.error(
                    f"[ReconciliationSession: {reconciliation_session_id}] SAP Query failed with status {response.status_code}: {response.text}"
                )
                raise SAPQueryError(f"SAP documents query failed (HTTP {response.status_code}): {response.text}")

            json_start = time.perf_counter()
            try:
                data = response.json()
            except ValueError:
                logger.error(
                    f"[ReconciliationSession: {reconciliation_session_id}] SAP returned non-JSON data: {response.text}"
                )
                raise SAPQueryError("SAP documents query returned invalid JSON.")
            json_elapsed = time.perf_counter() - json_start
            total_json_parse += json_elapsed

            documents_page = data.get("value", [])
            page_elapsed = time.perf_counter() - page_start
            page_latencies.append(page_elapsed)

            yield documents_page
            total_rows += len(documents_page)

            # Traverse @odata.nextLink exactly as returned by SAP
            next_link = data.get("odata.nextLink") or data.get("@odata.nextLink")

            logger.info(
                f"[ReconciliationSession: {reconciliation_session_id}] Pagination page {page_number} result: "
                f"returned {len(documents_page)} rows, "
                f"raw nextLink={next_link!r}, "
                f"page_time={page_elapsed*1000:.1f}ms, "
                f"json_parse={json_elapsed*1000:.1f}ms"
            )

            if next_link:
                if next_link.startswith("http"):
                    next_url = next_link
                else:
                    # If relative, construct using base URL
                    next_url = f"{self.base_url}/{next_link}"
            else:
                next_url = None

        total_elapsed = time.perf_counter() - total_start
        avg_page = (sum(page_latencies) / len(page_latencies) * 1000) if page_latencies else 0

        logger.info(
            f"[ReconciliationSession: {reconciliation_session_id}] Pagination complete: "
            f"{endpoint_name} fetched {total_rows} rows across {page_number} page(s) "
            f"in {total_elapsed*1000:.0f}ms total. "
            f"Avg page: {avg_page:.0f}ms, "
            f"JSON parse total: {total_json_parse*1000:.0f}ms "
            f"({((total_json_parse / total_elapsed)*100) if total_elapsed else 0:.0f}% of total)"
        )
