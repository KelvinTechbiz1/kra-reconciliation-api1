"""TLS trust for SAP Service Layer connections.

SAP Business One ships the Service Layer with a self-signed certificate, so the system CA
store rejects most on-premise installs. Rather than disabling verification, a connection can
pin the certificate (or private CA) its server presents, and we verify against that alone.
"""
import ssl
import urllib.parse
from datetime import datetime, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization

from app.schemas.settings import CertificateInfo

MAX_PEM_LENGTH = 64 * 1024
FETCH_TIMEOUT_SECONDS = 8.0


def normalize_certificate_pem(pem: str) -> str:
    """Parse one or more PEM certificates and return them re-serialized.

    Raises ValueError with a user-facing message when the text is not a valid certificate.
    """
    text = (pem or "").strip()
    if len(text) > MAX_PEM_LENGTH:
        raise ValueError("Certificate is too large.")
    if "-----BEGIN CERTIFICATE-----" not in text:
        raise ValueError("Certificate must be PEM text starting with '-----BEGIN CERTIFICATE-----'.")
    try:
        certs = x509.load_pem_x509_certificates(text.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ValueError(f"Could not read the certificate: {exc}") from exc
    return "".join(c.public_bytes(serialization.Encoding.PEM).decode("ascii") for c in certs)


def describe_certificate(pem: str) -> CertificateInfo:
    """Summarize the first certificate in a PEM bundle for display and audit."""
    certs = x509.load_pem_x509_certificates(pem.encode("ascii"))
    cert = certs[0]
    not_after = cert.not_valid_after_utc
    return CertificateInfo(
        subject=cert.subject.rfc4514_string(),
        issuer=cert.issuer.rfc4514_string(),
        not_valid_before=cert.not_valid_before_utc,
        not_valid_after=not_after,
        fingerprint_sha256=cert.fingerprint(hashes.SHA256()).hex(":").upper(),
        is_expired=not_after < datetime.now(timezone.utc),
        is_self_signed=cert.subject == cert.issuer,
        certificate_count=len(certs),
    )


def build_verify(verify_ssl: bool, ca_certificate: str | None) -> ssl.SSLContext | bool:
    """Return the ``verify`` argument for httpx.

    With a pinned certificate, only that certificate (or chains ending in it) is trusted;
    the system CA store is not consulted. Hostname checking is off in that mode because
    Service Layer certs are usually issued to an internal hostname while customers connect
    by IP. Trust is still bound to the pinned key, so another server cannot impersonate it.
    """
    if not verify_ssl:
        return False
    if not ca_certificate:
        return True
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    # Lets a pinned leaf act as a trust anchor even when its issuer is not supplied.
    ctx.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
    ctx.load_verify_locations(cadata=ca_certificate)
    return ctx


def fetch_server_certificate(base_url: str) -> str:
    """Retrieve the certificate a server presents, without verifying it.

    Used so an admin can review the fingerprint and choose to trust it.
    """
    parsed = urllib.parse.urlparse((base_url or "").strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Base URL must be an https:// address to fetch its certificate.")
    port = parsed.port or 443
    try:
        pem = ssl.get_server_certificate((parsed.hostname, port), timeout=FETCH_TIMEOUT_SECONDS)
    except (OSError, ssl.SSLError) as exc:
        raise ConnectionError(f"Could not retrieve certificate from {parsed.hostname}:{port}: {exc}") from exc
    return normalize_certificate_pem(pem)


def is_untrusted_certificate_error(exc: BaseException) -> bool:
    """True when an httpx/ssl error was caused by certificate verification failing."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        if isinstance(current, ssl.SSLCertVerificationError):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return "CERTIFICATE_VERIFY_FAILED" in str(exc)
