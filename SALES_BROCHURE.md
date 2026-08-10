# UshuruLens
## Tax Reconciliation, Supercharged.

**A KRA iTax ↔ SAP Business One+ANy ERP reconciliation engine built for finance teams who are tired of spreadsheets, late nights, and penalty letters from KRA.**

---

## The Problem We Kill

Every month, thousands of Kenyan businesses face the same nightmare:

- ❌ **Hours wasted** manually cross-checking SAP invoices against KRA iTax exports
- ❌ **Human errors** slipping through — missed invoices, wrong amounts, mismatched CU numbers
- ❌ **Penalties & interest** from KRA because a single invoice didn't reconcile
- ❌ **No audit trail** — when KRA asks, you can't prove your numbers fast enough
- ❌ **Fraud exposure** — no automated way to catch invoices that exist in SAP but never made it to KRA (or vice versa)

**UshuruLens ends that. Automatically. In seconds.**

---

## What UshuruLens Does

UshuruLens pulls invoices straight from **SAP Business One**, matches them against your **KRA iTax CSV exports**, and tells you — invoice by invoice — exactly what matches, what doesn't, and why.

No exporting to Excel. No manual matching. No guesswork.

---

## The Killer Feature: Lightning-Fast Reconciliation

> **Reconcile 10,000+ invoices in under 2 seconds.**

Our engine uses a **hash-based matching algorithm** (O(n) — not the slow O(n²) approach used by every spreadsheet) to compare datasets instantly, even at enterprise scale.

Every invoice is automatically classified into one of four statuses:

| Status | What It Means | Business Action |
|---|---|---|
| ✅ **Matched** | Exists in both SAP & KRA — all fields align | Nothing — sit back |
| ⚠️ **Mismatch** | Exists in both, but fields differ | Investigate & correct before KRA does |
| 🔴 **SAP Only** | In SAP, but missing from KRA | **This is unreported income — fix it NOW** |
| 🔵 **KRA Only** | In KRA, but missing from SAP | Flag & investigate — possible data error or fraud |

**No more "where did this come from?"** — UshuruLens tells you *exactly* which fields differ and by how much, e.g.:

> `Base Amount differs (SAP: 1,200.00, KRA: 1,250.00)`<br>
> `CU Number differs (SAP: KRA123, KRA: KRA999)`

Field-by-field discrepancy reporting on:
- 📅 **Invoice Date**
- 💰 **Base Amount** (Decimal-precision — no floating-point rounding tricks)
- 🧾 **VAT Group / tax code**
- 🔢 **CU Number** (Control Unit serial)

---

## Every Feature, Front and Center

### 1. Native SAP Business One Integration
- Pulls **Sales (A/R)** and **Purchases (A/P)** invoices directly from SAP B1 Service Layer
- **Secure session management** — automatic login, keep-alive, and cookie handling
- **Enterprise-grade pagination** — handles millions of records without choking
- **Resilient by design** — automatic retries, graceful timeout handling, no crashes

### 2. KRA iTax CSV Made Painless
- Drag-and-drop **CSV upload** with instant validation
- **Smart header detection** — accepts multiple column-name variations (no more "wrong template" rejections)
- **Duplicate prevention** — rejects duplicate invoice numbers before they poison your data
- **Custom parsing profiles** — configurable column aliases to fit your ERP's export format
- **Ready-made templates** — download a compliant CSV template in one click

### 3. Multi-Company & Multi-Branch Ready
- **Per-company SAP connections** — every company configured with its own credentials
- **Per-company policies** — base-amount rules, VAT mappings, and CU source set independently per entity
- Built for **groups, holding companies, and ERP resellers** managing many clients

### 4. Background Processing You Can Trust
- **Long-running SAP loads run in the background** — your browser never locks up
- **Live status tracking & polling** — watch progress in real time
- Load 100,000 invoices while you go grab a coffee

### 5. Audit-Ready Reporting & Export
- **Professional, styled Excel (XLSX) reports** — boardroom-ready, no formatting needed
- **ZIP archive exports** for bulk delivery & record-keeping
- **Side-by-side tax bases** — SAP vs KRA on the same page
- A complete, exportable **audit trail** for KRA compliance queries

### 6. Bank-Grade Security & Access Control
- **JWT access tokens** (short-lived) + **rotating refresh tokens** — a new token every session, theft-proof by design
- **SHA-256 hashed tokens** at rest — even a database breach exposes nothing usable
- **Role-based access** (Admin / Checker) — separation of duties built in
- **Password reset** via encrypted email links (SendGrid SMTP)
- **Full logout revocation** — kill sessions instantly

### 7. Powerful Settings, Zero Code
- **VAT group mapping editor** — align your VAT codes with KRA's in a UI, not a ticket
- **KRA VAT mapping editor** — see exactly how each tax code maps to iTax
- **SAP connection manager** — configure & test connections without touching code
- **System settings** — everything tunable: upload limits, amount tolerance, timeouts

### 8. Beautiful, Purpose-Built Dashboard
- **Modern Next.js web app** — clean, fast, and works on any device
- Dedicated workspaces for **Sales** and **Purchases** reconciliation
- **Infinite-scroll results tables** — navigate 10,000+ results without pagination lag
- Real-time **summary cards** — matched / mismatched / SAP-only / KRA-only at a glance

### 9. Deploy Anywhere, Fast
- **One-command Docker deployment** — API + frontend + database + web server, all in a single container image
- **Runs on-premise or in the cloud** — your data stays yours
- Built on a **battle-tested stack**: FastAPI, PostgreSQL, SQLAlchemy, Alembic migrations

---

## Why Finance & IT Both Love It

| For Finance | For IT |
|---|---|
| Reconcile 10,000+ invoices in seconds | Clean, documented REST API |
| Field-level discrepancy details | Swagger/OpenAPI interactive docs built-in |
| Exportable audit trail for KRA | Dockerized, one-command deployment |
| No more manual spreadsheet matching | Battle-tested stack (FastAPI + PostgreSQL) |
| Multi-company support out of the box | Tested & CI-pipelined codebase |

---

## Numbers That Speak

- ⚡ **10,000 invoices reconciled in < 2 seconds**
- 🧠 **~50 MB memory** to process 10,000 invoices — light enough for any server
- 🔄 **100% automated** matching — zero manual cross-referencing
- 🔒 **Double-layer token security** — access + rotating refresh tokens

---

## The Bottom Line

UshuruLens isn't just a reconciliation tool — it's **compliance insurance**.

Every invoice reconciled, every discrepancy caught before KRA catches it, every audit question answered in minutes instead of days. For the cost of one late-night reconciliation session, you buy back an entire finance team's month.

---

## Ready to See It in Action?

📅 **Book a live demo** — we'll run *your* SAP data through it in front of you.

📧 **Email the team:** [47CRM@techbizafrica.com](mailto:47CRM@techbizafrica.com)

🌐 **Visit:** [app.ushurulens.techbizafrica.com](https://app.ushurulens.techbizafrica.com)

---

*UshuruLens — powered by Techbiz Group. Tax compliance, on autopilot.*
