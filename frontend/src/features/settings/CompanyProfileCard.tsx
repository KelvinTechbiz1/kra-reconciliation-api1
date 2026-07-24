"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { CompanyProfile, CompanyCreatePayload, CompanyUpdatePayload } from "@/types/company";
import { fetchWithAuth } from "@/lib/api";
import { useToast } from "@/components/ToastProvider";
import {
  Building2,
  Plus,
  Search,
  Save,
  Loader2,
  CheckCircle2,
  ShieldAlert,
  MapPin,
  Calendar,
  Globe,
  Trash2,
  Edit3,
  X,
  ShieldCheck,
} from "lucide-react";

interface CompanyProfileCardProps {
  companies: CompanyProfile[];
  onSaved: () => void;
}

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const TIMEZONES = [
  "Africa/Nairobi",
  "Africa/Lagos",
  "Africa/Johannesburg",
  "Africa/Cairo",
  "Europe/London",
  "Europe/Paris",
  "America/New_York",
  "America/Los_Angeles",
  "Asia/Dubai",
  "Asia/Kolkata",
  "UTC",
];

const CURRENCIES = ["KES", "USD", "EUR", "GBP", "ZAR", "NGN", "UGX", "TZS", "ETB"];

// --- Modal: Onboard New Company ---
interface CreateCompanyModalProps {
  onClose: () => void;
  onCreated: () => void;
}

function CreateCompanyModal({ onClose, onCreated }: CreateCompanyModalProps) {
  const [mounted, setMounted] = useState(false);
  const [name, setName] = useState("");
  const [kraPin, setKraPin] = useState("");
  const [currency, setCurrency] = useState("KES");
  const [timezone, setTimezone] = useState("Africa/Nairobi");
  const [fiscalYearStartMonth, setFiscalYearStartMonth] = useState(1);
  const [saving, setSaving] = useState(false);
  const { notify } = useToast();

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!kraPin.trim()) {
      notify("KRA PIN is required.", "error");
      return;
    }
    setSaving(true);
    try {
      const payload: CompanyCreatePayload = {
        name: name.trim(),
        kra_pin: kraPin.trim().toUpperCase(),
        currency,
        timezone,
        fiscal_year_start_month: fiscalYearStartMonth,
      };
      const res = await fetchWithAuth("/company", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create company profile.");
      }
      notify(`Company profile "${name.trim()}" created successfully.`, "success");
      onCreated();
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      notify(msg || "An error occurred while creating company.", "error");
    } finally {
      setSaving(false);
    }
  };

  if (!mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Building2 className="w-5 h-5 text-[#0e1734]" />
            <div>
              <h3 className="font-bold text-slate-900 text-sm">Onboard New Company Entity</h3>
              <p className="text-xs text-slate-500">Register subsidiary or multi-client parameters</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleCreate} className="p-6 space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Company Legal Name *</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Safari Enterprises Ltd"
              className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-900 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-[#0e1734]/20 focus:border-[#0e1734] font-medium placeholder:text-slate-400"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">KRA PIN *</label>
              <input
                type="text"
                required
                value={kraPin}
                onChange={(e) => setKraPin(e.target.value.toUpperCase())}
                placeholder="e.g. P051234567Q"
                className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-900 text-sm font-mono transition-colors focus:outline-none focus:ring-2 focus:ring-[#0e1734]/20 focus:border-[#0e1734] placeholder:text-slate-400"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Base Currency</label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-[#0e1734]/20 focus:border-[#0e1734] font-medium cursor-pointer"
              >
                {CURRENCIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Timezone</label>
              <select
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-[#0e1734]/20 focus:border-[#0e1734] cursor-pointer"
              >
                {TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>{tz}</option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Fiscal Year Start</label>
              <select
                value={fiscalYearStartMonth}
                onChange={(e) => setFiscalYearStartMonth(parseInt(e.target.value))}
                className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-[#0e1734]/20 focus:border-[#0e1734] cursor-pointer"
              >
                {MONTH_NAMES.map((month, idx) => (
                  <option key={idx + 1} value={idx + 1}>{month}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="pt-3 flex justify-end gap-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 text-slate-600 hover:text-slate-900 text-sm font-medium transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#0e1734] hover:bg-[#16224c] active:bg-[#080d21] text-white rounded-lg text-sm font-semibold shadow-sm transition-all duration-150 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Building2 className="w-4 h-4" />}
              Create Company
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}

// --- Modal: Edit Company Details ---
interface EditCompanyModalProps {
  company: CompanyProfile;
  onClose: () => void;
  onSaved: () => void;
}

function EditCompanyModal({ company, onClose, onSaved }: EditCompanyModalProps) {
  const [mounted, setMounted] = useState(false);
  const [name, setName] = useState(company.name);
  const [kraPin, setKraPin] = useState(company.kra_pin || "");
  const [timezone, setTimezone] = useState(company.timezone);
  const [currency, setCurrency] = useState(company.currency);
  const [fiscalYearStartMonth, setFiscalYearStartMonth] = useState(company.fiscal_year_start_month);
  const [saving, setSaving] = useState(false);
  const { notify } = useToast();

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload: CompanyUpdatePayload = {
        name,
        kra_pin: kraPin || undefined,
        timezone,
        currency,
        fiscal_year_start_month: fiscalYearStartMonth,
      };
      const res = await fetchWithAuth(`/company/${company.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to update company.");
      }
      notify(`Company profile "${name.trim()}" updated successfully.`, "success");
      onSaved();
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      notify(msg || "An error occurred.", "error");
    } finally {
      setSaving(false);
    }
  };

  if (!mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Edit3 className="w-5 h-5 text-blue-600" />
            <h3 className="font-bold text-slate-900 text-sm">Edit Company Profile — #{company.id}</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleUpdate} className="p-6 space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Company Legal Name *</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-900 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">KRA PIN</label>
              <input
                type="text"
                value={kraPin}
                onChange={(e) => setKraPin(e.target.value.toUpperCase())}
                placeholder="e.g. P051234567Q"
                className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-900 text-sm font-mono transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Base Currency</label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium cursor-pointer"
              >
                {CURRENCIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Timezone</label>
              <select
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 cursor-pointer"
              >
                {TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>{tz}</option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Fiscal Year Start</label>
              <select
                value={fiscalYearStartMonth}
                onChange={(e) => setFiscalYearStartMonth(parseInt(e.target.value))}
                className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 cursor-pointer"
              >
                {MONTH_NAMES.map((month, idx) => (
                  <option key={idx + 1} value={idx + 1}>{month}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="pt-3 flex justify-end gap-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 text-slate-600 hover:text-slate-900 text-sm font-medium transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#0e1734] hover:bg-[#16224c] active:bg-[#080d21] text-white rounded-lg text-sm font-semibold shadow-sm transition-all duration-150 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Save Changes
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}

// --- Main Multi-Company Workspace Component ---
export function CompanyProfileCard({ companies = [], onSaved }: CompanyProfileCardProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingCompany, setEditingCompany] = useState<CompanyProfile | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const { notify } = useToast();

  const filteredCompanies = companies.filter(
    (c) =>
      c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (c.kra_pin && c.kra_pin.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const handleDelete = async (company: CompanyProfile) => {
    if (company.id === 1) return;
    if (!confirm(`Are you sure you want to delete company profile "${company.name}"?`)) return;

    setDeletingId(company.id);
    try {
      const res = await fetchWithAuth(`/company/${company.id}`, { method: "DELETE" });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to delete company profile.");
      }
      notify(`Company "${company.name}" deleted successfully.`, "success");
      onSaved();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      notify(msg || "Failed to delete company profile.", "error");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <>
      {showCreateModal && (
        <CreateCompanyModal
          onClose={() => setShowCreateModal(false)}
          onCreated={onSaved}
        />
      )}

      {editingCompany && (
        <EditCompanyModal
          company={editingCompany}
          onClose={() => setEditingCompany(null)}
          onSaved={onSaved}
        />
      )}

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden space-y-0">
        {/* Workspace Header */}
        <div className="px-6 py-5 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center text-[#0e1734] shrink-0">
              <Building2 className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-900">Multi-Company Management</h2>
                <span suppressHydrationWarning className="px-2 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-200">
                  {companies.length} Registered
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">Manage legal entity profiles, tax PINs, and operational defaults</p>
            </div>
          </div>

          <button
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-[#0e1734] hover:bg-[#16224c] active:bg-[#080d21] text-white rounded-lg text-sm font-semibold shadow-sm transition-all duration-150 cursor-pointer"
          >
            <Plus className="w-4 h-4" /> Onboard Company
          </button>
        </div>

        {/* Filter Bar & Action Banners */}
        <div className="p-6 space-y-4">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search companies by legal name or KRA PIN..."
              className="w-full pl-10 pr-4 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 placeholder:text-slate-400"
            />
          </div>

          {/* Company Profiles Grid */}
          {filteredCompanies.length === 0 ? (
            <div className="py-12 text-center border-2 border-dashed border-slate-200 rounded-xl">
              <Building2 className="w-8 h-8 text-slate-300 mx-auto mb-2" />
              <p className="text-sm font-medium text-slate-600">No matching company profiles found</p>
              <p className="text-xs text-slate-400 mt-1">Try refining your search query or onboard a new company</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredCompanies.map((c) => {
                const isPrimary = c.id === 1;
                const initials = c.name
                  .split(" ")
                  .slice(0, 2)
                  .map((w) => w[0]?.toUpperCase() || "")
                  .join("");

                return (
                  <div
                    key={c.id}
                    className="p-5 rounded-xl border border-slate-200 hover:border-slate-300 bg-white shadow-sm hover:shadow transition-all space-y-4 flex flex-col justify-between"
                  >
                    <div>
                      {/* Top Row: Avatar + Name + Badges */}
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <div className="w-11 h-11 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-center text-slate-700 font-bold text-base shrink-0">
                            {initials || <Building2 className="w-5 h-5 text-slate-400" />}
                          </div>
                          <div>
                            <h3 className="font-bold text-slate-900 text-sm leading-tight">{c.name}</h3>
                            <div className="flex items-center gap-2 mt-1">
                              {isPrimary ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-blue-50 text-blue-700 border border-blue-200">
                                  <ShieldCheck className="w-3 h-3 text-blue-600" /> Primary Entity
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-600 border border-slate-200">
                                  ID #{c.id}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Quick Edit / Delete Controls */}
                        <div className="flex items-center gap-1 shrink-0">
                          <button
                            onClick={() => setEditingCompany(c)}
                            className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all cursor-pointer"
                            title="Edit company profile"
                          >
                            <Edit3 className="w-4 h-4" />
                          </button>
                          {!isPrimary && (
                            <button
                              onClick={() => handleDelete(c)}
                              disabled={deletingId === c.id}
                              className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-all cursor-pointer disabled:opacity-50"
                              title="Delete company profile"
                            >
                              {deletingId === c.id ? (
                                <Loader2 className="w-4 h-4 animate-spin text-rose-600" />
                              ) : (
                                <Trash2 className="w-4 h-4" />
                              )}
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Meta Parameters */}
                      <div className="grid grid-cols-2 gap-2 mt-4 pt-3 border-t border-slate-100 text-xs">
                        <div className="flex items-center gap-1.5 text-slate-600">
                          <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          <span className="font-mono text-slate-800 font-medium">
                            {c.kra_pin || "PIN Unassigned"}
                          </span>
                        </div>

                        <div className="flex items-center gap-1.5 text-slate-600">
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-600 border border-slate-200">
                            {c.currency}
                          </span>
                          <span className="font-medium text-slate-800">Base Currency</span>
                        </div>

                        <div className="flex items-center gap-1.5 text-slate-600">
                          <Globe className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          <span className="truncate text-slate-700">{c.timezone}</span>
                        </div>

                        <div className="flex items-center gap-1.5 text-slate-600">
                          <Calendar className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          <span className="text-slate-700">Starts {MONTH_NAMES[c.fiscal_year_start_month - 1]}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
