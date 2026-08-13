# Reconciliation Engine

The Reconciliation Engine matches **SAP Business One** invoice data against **KRA iTax** CSV exports. It pairs documents, validates them field-by-field, and classifies every pair into a canonical status that flows through the API, dashboard, and Excel exports.

---

## 1. Matching Algorithm

The engine runs a **7-stage modular pipeline** in `reconcile_invoices` (`app/services/reconciliation_service.py`):

| Stage | Purpose |
|---|---|
| 1. Preprocess | Normalize and group source invoices |
| 2. Integrity | Classify rows with a missing CU number **without discarding them** (data-preservation principle) |
| 3. Symmetric normalization | Build CU-keyed maps; group duplicate CU rows into a single normalized document with a `tax_breakdown` |
| 4. Document pairing | Pair by CU number, then a **fallback heuristic** pairs near-identical documents (same base amount within tolerance **and** matching partner PIN/name) to catch minor CU typos / OCR errors |
| 5. Document validation | Check base amount (within tolerance), PIN, date, partner name |
| 6. Tax breakdown validation | Always-on per-category base comparison (16%/8%/0%/Exempt) for the VAT verdict |
| 7. Result generation | Build `ReconciliationResult` rows and classify status |

### Fallback pairing

- Documents whose CU numbers do not match exactly are still considered for pairing if their **base amounts match within tolerance** and their **partner PIN or name matches** (e.g. `190349340000000511` vs `190439340000000511` — a single-digit typo).
- Such pairs are *paired but flagged*: because their CU numbers differ, they are classified **`CU Mismatch`**, not silently treated as a match.

### `check_pin_matches` rule

- PINs compare **normalized** (whitespace/stray characters stripped, uppercase).
- `True` only when **both** PINs are present and equal, or **both** are missing.
- A **one-sided missing PIN** (SAP empty but KRA present, or vice-versa) returns `False` and produces a `PIN Mismatch` — it is never silently treated as a match.

---

## 2. Statuses

Statuses are defined in `ReconciliationStatus` (`app/domain/reconciliation_status.py`) and ordered by `STATUS_ORDER` in `app/domain/reconciliation_constants.py`.

| Status | Condition |
|---|---|
| `Duplicate Source Key` | Same CU number + VAT group pairing detected |
| `Missing CU Number` | Row has no CU number, so it cannot be paired |
| `Missing in SAP` | Present in KRA upload but absent from SAP B1 |
| `Missing in KRA` | Present in SAP B1 but absent from KRA upload |
| `Multiple Mismatches` | More than one checked field differs |
| `Amount Mismatch` | Base amount differs beyond tolerance |
| `VAT Mismatch` | Base amount matches, but the per-category tax breakdown differs |
| `CU Mismatch` | CU numbers differ (typically a fallback-paired typo) |
| `PIN Mismatch` | KRA PIN is missing on one side or differs |
| `Match` | All checked fields align |

### Classification precedence

For a paired document, exactly one status is assigned (first rule that fires):

1. more than one difference → `Multiple Mismatches`
2. amount differs → `Amount Mismatch`
3. tax breakdown differs → `VAT Mismatch`
4. CU numbers differ → `CU Mismatch`
5. PINs differ / one-sided missing → `PIN Mismatch`
6. otherwise → `Match`

### Matching fields

- **Invoice Date** — must match exactly.
- **Base Amount** — compared with `Decimal` and the configured `amount_tolerance` to avoid float rounding issues.
- **VAT Group / tax breakdown** — per-category base comparison (16%, 8%, 0%, Exempt).
- **CU Number** — Control Unit serial number.
- **KRA PIN** — normalized string comparison (both present and equal, or both missing).

### Remarks

Remark text is centralized in `REMARK_MAP` in `app/domain/reconciliation_constants.py` — "change here = change everywhere" (export, future email/PDF, dashboard). Detailed field-level difference strings are generated per row (e.g. `CU Number differs (SAP: …, KRA: …)`).

### Versioning

- `STATUS_PRIORITY_VERSION` — bump **only** when `STATUS_ORDER` changes (currently `"3"`).
- `EXPORT_SCHEMA_VERSION` — bump only when the workbook layout or `Export.json` structure changes (currently `"2.0"`).
- `REMARK_MAP` wording changes are deliberate, explicit migrations; no version tracked.

---

## 3. Reporting

- Exports are built by `app/reporting/` (sheet definitions + workbook builder).
- Exception statuses requiring review (`NEEDS_REVIEW_STATUSES`) — including the newer `CU Mismatch` and `PIN Mismatch` — each get their own worksheet in `02 Exceptions.xlsx`, with matching breakdown rows in the workbook summary.

---

## 4. Performance

- CU-keyed dictionary lookups keep comparison **O(n)** on document count (no nested loops).
- Large batches (10,000+ invoices) reconcile in seconds on standard hardware; per-document memory footprint is small because rows are grouped by CU number into single normalized documents before comparison.
