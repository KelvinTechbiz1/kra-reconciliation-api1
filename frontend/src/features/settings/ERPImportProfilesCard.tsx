"use client";

import { useEffect, useState, useCallback } from "react";
import { createPortal } from "react-dom";
import { ImportProfile, ImportProfileCreate, ReconciliationType, SourceFormat } from "@/types/import_profile";
import { fetchWithAuth } from "@/lib/api";
import { useToast } from "@/components/ToastProvider";
import {
  FileSpreadsheet,
  Plus,
  Copy,
  CheckCircle2,
  Trash2,
  Loader2,
  Info,
  Sliders,
  Database,
  FileCode,
  X,
} from "lucide-react";

interface ERPImportProfilesCardProps {
  selectedCompanyId?: number | null;
}

interface AddImportProfileModalProps {
  onClose: () => void;
  onSaved: () => void;
}

function AddImportProfileModal({ onClose, onSaved }: AddImportProfileModalProps) {
  const [mounted, setMounted] = useState(false);
  const [saving, setSaving] = useState(false);

  // Form State
  const [formName, setFormName] = useState("");
  const [formModule, setFormModule] = useState<ReconciliationType>("sales");
  const [formProvider, setFormProvider] = useState("ZOHO");
  const [formDescription, setFormDescription] = useState("");
  const [formFormat, setFormFormat] = useState<SourceFormat>("csv");

  const [pinAlias, setPinAlias] = useState("Customer PIN, Tax Number, PIN");
  const [partnerAlias, setPartnerAlias] = useState("Customer Name, Client Name, Vendor");
  const [invNumAlias, setInvNumAlias] = useState("Invoice Number, Invoice No, DocNum");
  const [invDateAlias, setInvDateAlias] = useState("Invoice Date, Date");
  const [cuNumAlias, setCuNumAlias] = useState("CU Number, ETR Number, Control Unit No");
  const [vatGroupAlias, setVatGroupAlias] = useState("Tax Rate, VAT Code, VAT Group");
  const [baseAmtAlias, setBaseAmtAlias] = useState("SubTotal, Taxable Amount, Base Amount");

  const { notify } = useToast();

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim()) {
      notify("Please provide a profile name.", "error");
      return;
    }

    setSaving(true);
    const parseAliases = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

    const payload: ImportProfileCreate = {
      name: formName.trim(),
      module: formModule,
      provider: formProvider.trim().toUpperCase(),
      description: formDescription.trim() || undefined,
      source_format: formFormat,
      parsing_hints: {
        has_header: true,
        header_row: 1,
        data_start_row: 2,
        delimiter: ",",
        date_format: "YYYY-MM-DD",
        decimal_separator: ".",
        thousands_separator: ",",
      },
      column_mapping: {
        pin: parseAliases(pinAlias),
        partner_name: parseAliases(partnerAlias),
        invoice_number: parseAliases(invNumAlias),
        invoice_date: parseAliases(invDateAlias),
        cu_number: parseAliases(cuNumAlias),
        vat_group: parseAliases(vatGroupAlias),
        base_amount: parseAliases(baseAmtAlias),
      },
      validation_rules:
        formModule === "sales"
          ? {
              module: "sales",
              required_fields: ["pin", "invoice_number", "base_amount"],
              allowed_vat_codes: ["16", "8", "0", "EXEMPT"],
              date_strictness: "LENIENT",
              row_skip_policy: "SKIP_EMPTY_AND_TOTALS",
              default_vat_group: "A16",
              require_valid_pin_format: true,
            }
          : {
              module: "purchases",
              required_fields: ["pin", "invoice_number", "base_amount"],
              allowed_vat_codes: ["16", "8", "0", "EXEMPT"],
              date_strictness: "LENIENT",
              row_skip_policy: "SKIP_EMPTY_AND_TOTALS",
              default_vat_group: "A16",
            },
      is_default: false,
    };

    try {
      const res = await fetchWithAuth("/import-profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to create profile.");
      }

      notify("Custom import profile created successfully!", "success");
      onSaved();
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error saving profile.";
      notify(msg, "error");
    } finally {
      setSaving(false);
    }
  };

  if (!mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-150">
        {/* Fixed Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 shrink-0">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-sm">Add Custom Import Profile</h3>
              <p className="text-xs text-slate-500">Configure canonical column header mappings and source formats</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-lg transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Form Body */}
        <form onSubmit={handleSaveProfile} id="add-import-profile-form" className="flex-1 overflow-y-auto p-6 space-y-4 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block font-semibold text-slate-700 mb-1 uppercase tracking-wider text-[11px]">
                Profile Name *
              </label>
              <input
                type="text"
                required
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="e.g. Zoho Books - Custom Sales"
                className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 bg-white text-slate-900 text-xs transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium placeholder:text-slate-400"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 mb-1 uppercase tracking-wider text-[11px]">
                Module *
              </label>
              <select
                value={formModule}
                onChange={(e) => setFormModule(e.target.value as ReconciliationType)}
                className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 bg-white text-slate-800 text-xs transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium cursor-pointer"
              >
                <option value="sales">Sales</option>
                <option value="purchases">Purchases</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block font-semibold text-slate-700 mb-1 uppercase tracking-wider text-[11px]">
                Provider Label
              </label>
              <input
                type="text"
                value={formProvider}
                onChange={(e) => setFormProvider(e.target.value)}
                placeholder="ZOHO, QUICKBOOKS, XERO, CUSTOM"
                className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 bg-white text-slate-900 text-xs transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-mono font-medium placeholder:text-slate-400"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 mb-1 uppercase tracking-wider text-[11px]">
                Source Format
              </label>
              <select
                value={formFormat}
                onChange={(e) => setFormFormat(e.target.value as SourceFormat)}
                className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 bg-white text-slate-800 text-xs transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium cursor-pointer"
              >
                <option value="csv">CSV File (.csv)</option>
                <option value="xlsx">Excel File (.xlsx)</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1 uppercase tracking-wider text-[11px]">
              Description (Optional)
            </label>
            <input
              type="text"
              value={formDescription}
              onChange={(e) => setFormDescription(e.target.value)}
              placeholder="Notes on column structure or export settings"
              className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 bg-white text-slate-900 text-xs transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 placeholder:text-slate-400"
            />
          </div>

          <div className="pt-3 border-t border-slate-100 space-y-3">
            <div className="flex items-center gap-2">
              <Info className="w-4 h-4 text-blue-600 shrink-0" />
              <h4 className="font-bold text-slate-800 text-xs">
                Canonical Column Header Aliases (Comma Separated)
              </h4>
            </div>
            <div className="space-y-3 font-mono text-[11px]">
              <div>
                <label className="block font-semibold text-slate-600 mb-1">PIN Aliases</label>
                <input
                  type="text"
                  value={pinAlias}
                  onChange={(e) => setPinAlias(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block font-semibold text-slate-600 mb-1">Partner Name Aliases</label>
                <input
                  type="text"
                  value={partnerAlias}
                  onChange={(e) => setPartnerAlias(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block font-semibold text-slate-600 mb-1">Invoice Number Aliases</label>
                <input
                  type="text"
                  value={invNumAlias}
                  onChange={(e) => setInvNumAlias(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block font-semibold text-slate-600 mb-1">Invoice Date Aliases</label>
                <input
                  type="text"
                  value={invDateAlias}
                  onChange={(e) => setInvDateAlias(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block font-semibold text-slate-600 mb-1">CU/ETR Number Aliases</label>
                <input
                  type="text"
                  value={cuNumAlias}
                  onChange={(e) => setCuNumAlias(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block font-semibold text-slate-600 mb-1">VAT Group / Tax Rate Aliases</label>
                <input
                  type="text"
                  value={vatGroupAlias}
                  onChange={(e) => setVatGroupAlias(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block font-semibold text-slate-600 mb-1">Base Amount Aliases</label>
                <input
                  type="text"
                  value={baseAmtAlias}
                  onChange={(e) => setBaseAmtAlias(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>
            </div>
          </div>
        </form>

        {/* Fixed Footer */}
        <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-end gap-3 bg-slate-50/50 shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2.5 text-slate-600 hover:text-slate-900 text-xs font-semibold transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="add-import-profile-form"
            disabled={saving}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#0e1734] hover:bg-[#16224c] active:bg-[#080d21] text-white rounded-lg text-xs font-semibold shadow-sm transition-all duration-150 cursor-pointer disabled:opacity-50"
          >
            {saving && <Loader2 className="w-4 h-4 animate-spin" />}
            Save Import Profile
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

export function ERPImportProfilesCard({ selectedCompanyId }: ERPImportProfilesCardProps) {
  const { notify } = useToast();
  const [profiles, setProfiles] = useState<ImportProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeModuleFilter, setActiveModuleFilter] = useState<"all" | "sales" | "purchases">("all");

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [actionProfileId, setActionProfileId] = useState<number | null>(null);

  const loadProfiles = useCallback(async () => {
    setLoading(true);
    try {
      const query = activeModuleFilter !== "all" ? `?module=${activeModuleFilter}` : "";
      const res = await fetchWithAuth(`/import-profiles${query}`);
      if (!res.ok) throw new Error("Failed to load import profiles.");
      const data: ImportProfile[] = await res.json();
      setProfiles(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load import profiles.";
      notify(msg, "error");
    } finally {
      setLoading(false);
    }
  }, [activeModuleFilter, notify]);

  useEffect(() => {
    loadProfiles();
  }, [loadProfiles]);

  const handleSetDefault = async (id: number) => {
    setActionProfileId(id);
    try {
      const res = await fetchWithAuth(`/import-profiles/${id}/set-default`, { method: "POST" });
      if (!res.ok) throw new Error("Failed to set profile as default.");
      notify("Default import profile updated successfully.", "success");
      loadProfiles();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error setting default profile.";
      notify(msg, "error");
    } finally {
      setActionProfileId(null);
    }
  };

  const handleClone = async (id: number, name: string) => {
    setActionProfileId(id);
    try {
      const res = await fetchWithAuth(`/import-profiles/${id}/clone?name=${encodeURIComponent(`${name} (Custom)`)}`, { method: "POST" });
      if (!res.ok) throw new Error("Failed to clone profile.");
      notify(`Profile cloned successfully into editable company profile.`, "success");
      loadProfiles();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error cloning profile.";
      notify(msg, "error");
    } finally {
      setActionProfileId(null);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to archive this custom import profile?")) return;
    setActionProfileId(id);
    try {
      const res = await fetchWithAuth(`/import-profiles/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to archive profile.");
      notify("Import profile archived successfully.", "success");
      loadProfiles();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error archiving profile.";
      notify(msg, "error");
    } finally {
      setActionProfileId(null);
    }
  };

  return (
    <>
      {showModal && (
        <AddImportProfileModal
          onClose={() => setShowModal(false)}
          onSaved={loadProfiles}
        />
      )}

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {/* Header */}
        <div className="p-6 border-b border-slate-100 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <FileSpreadsheet className="w-5 h-5 text-blue-600" />
              ERP Import Profiles
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Configurable column mappings and parsing profiles for Zoho, QuickBooks, Xero, and custom Excel files.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Module Filter */}
            <div className="inline-flex p-1 bg-slate-100 rounded-lg text-xs font-semibold">
              <button
                onClick={() => setActiveModuleFilter("all")}
                className={`px-3 py-1 rounded-md transition-colors ${activeModuleFilter === "all" ? "bg-white text-slate-900 shadow-xs" : "text-slate-500 hover:text-slate-800"}`}
              >
                All
              </button>
              <button
                onClick={() => setActiveModuleFilter("sales")}
                className={`px-3 py-1 rounded-md transition-colors ${activeModuleFilter === "sales" ? "bg-white text-slate-900 shadow-xs" : "text-slate-500 hover:text-slate-800"}`}
              >
                Sales
              </button>
              <button
                onClick={() => setActiveModuleFilter("purchases")}
                className={`px-3 py-1 rounded-md transition-colors ${activeModuleFilter === "purchases" ? "bg-white text-slate-900 shadow-xs" : "text-slate-500 hover:text-slate-800"}`}
              >
                Purchases
              </button>
            </div>

            <button
              onClick={() => setShowModal(true)}
              className="inline-flex items-center gap-1.5 px-3 py-2 bg-[#0e1734] hover:bg-[#16224c] text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              Add Import Profile
            </button>
          </div>
        </div>

        {/* Profile List Table */}
        <div className="p-6">
          {loading ? (
            <div className="flex items-center justify-center py-12 gap-2 text-slate-400 text-xs">
              <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
              Loading import profiles...
            </div>
          ) : profiles.length === 0 ? (
            <div className="text-center py-12 text-slate-400 text-xs space-y-2">
              <FileCode className="w-8 h-8 mx-auto text-slate-300" />
              <p>No import profiles found for selected filter.</p>
            </div>
          ) : (
            <div className="border border-slate-200 rounded-lg overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider text-[11px]">
                  <tr>
                    <th className="px-4 py-3">Profile Name</th>
                    <th className="px-4 py-3">Module</th>
                    <th className="px-4 py-3">Provider</th>
                    <th className="px-4 py-3">Scope</th>
                    <th className="px-4 py-3">Format</th>
                    <th className="px-4 py-3 text-center">Default</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {profiles.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-4 py-3 font-semibold text-slate-900">
                        <div>{p.name}</div>
                        {p.description && <div className="text-[11px] font-normal text-slate-400">{p.description}</div>}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${p.module === "sales" ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-purple-50 text-purple-700 border border-purple-200"}`}>
                          {p.module}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono font-medium text-slate-700">
                        <span className="px-2 py-0.5 bg-slate-100 rounded-md border border-slate-200 text-[10px] font-bold">
                          {p.provider}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-500">
                        {p.is_builtin ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-blue-600">
                            <Database className="w-3 h-3" /> System Built-in
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-600">
                            <Sliders className="w-3 h-3" /> Company Custom
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-500 uppercase">{p.source_format}</td>
                      <td className="px-4 py-3 text-center">
                        {p.is_default ? (
                          <span className="inline-flex items-center gap-1 text-emerald-600 font-semibold text-[11px]">
                            <CheckCircle2 className="w-3.5 h-3.5" /> Default
                          </span>
                        ) : (
                          <button
                            onClick={() => handleSetDefault(p.id)}
                            disabled={actionProfileId === p.id}
                            className="text-slate-400 hover:text-slate-700 underline text-[11px] cursor-pointer"
                          >
                            Make Default
                          </button>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right space-x-2">
                        <button
                          onClick={() => handleClone(p.id, p.name)}
                          disabled={actionProfileId === p.id}
                          title="Clone as Company Custom Profile"
                          className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors cursor-pointer"
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                        {!p.is_builtin && (
                          <button
                            onClick={() => handleDelete(p.id)}
                            disabled={actionProfileId === p.id}
                            title="Archive Profile"
                            className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors cursor-pointer"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

