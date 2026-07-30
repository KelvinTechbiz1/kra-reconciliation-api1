"use client";

import { useState, useEffect } from "react";
import { BaseAmountPolicy, PurchaseCUField, SystemSettings, UnmappedVatPolicy } from "@/types/settings";
import { fetchWithAuth } from "@/lib/api";
import { getApiErrorMessage } from "@/lib/errors";
import { useToast } from "@/components/ToastProvider";
import {
  Sliders,
  AlertTriangle,
  FileCheck,
  Percent,
  Layers,
  Save,
  Loader2,
  CheckCircle2,
  ShieldAlert,
} from "lucide-react";

interface SystemSettingsCardProps {
  settings: SystemSettings;
  selectedCompanyId?: number | null;
  onSaved: () => void;
}

export function SystemSettingsCard({ settings, selectedCompanyId, onSaved }: SystemSettingsCardProps) {
  const [amountTolerance, setAmountTolerance] = useState(settings.amount_tolerance);
  const [baseAmountPolicy, setBaseAmountPolicy] = useState<BaseAmountPolicy>(
    settings.base_amount_policy
  );
  const [unmappedVatPolicy, setUnmappedVatPolicy] = useState<UnmappedVatPolicy>(
    settings.unmapped_vat_policy
  );
  const [salesCuSource, setSalesCuSource] = useState<string>(
    settings.sales_cu_source || "U_CUINV"
  );
  const [purchaseCuSource, setPurchaseCuSource] = useState<string>(
    settings.purchase_cu_source || "U_CUINV"
  );

  useEffect(() => {
    setAmountTolerance(settings.amount_tolerance);
    setBaseAmountPolicy(settings.base_amount_policy);
    setUnmappedVatPolicy(settings.unmapped_vat_policy);
    setSalesCuSource(settings.sales_cu_source || "U_CUINV");
    setPurchaseCuSource(settings.purchase_cu_source || "U_CUINV");
  }, [settings]);

  const [saving, setSaving] = useState(false);
  const { notify } = useToast();

  const numericTolerance = parseFloat(amountTolerance) || 0;
  const showToleranceWarning = numericTolerance > 1000.0;

  const handleSaveSystemSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);

    try {
      const payload = {
        amount_tolerance: amountTolerance,
        base_amount_policy: baseAmountPolicy,
        unmapped_vat_policy: unmappedVatPolicy,
        sales_cu_source: salesCuSource,
        purchase_cu_source: purchaseCuSource,
        version: settings.version,
      };

      const url = `/settings/system-settings${selectedCompanyId ? `?company_id=${selectedCompanyId}` : ""}`;
      const res = await fetchWithAuth(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.status === 409) {
        const errData = await res.json().catch(() => null);
        throw new Error(getApiErrorMessage(errData, "Optimistic lock conflict: Settings modified by another administrator."));
      }

      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(getApiErrorMessage(errData, "Failed to update system settings."));
      }

      notify("Operational reconciliation rules updated successfully!", "success");
      onSaved();
    } catch (err: unknown) {
      const msg = getApiErrorMessage(err, "An error occurred while saving system settings.");
      notify(msg, "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden transition-all">
      {/* Header */}
      <div className="px-6 py-5 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-slate-50 rounded-lg border border-slate-200">
            <Sliders className="w-5 h-5 text-slate-500" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900">
              Operational Reconciliation Rules
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Configure amount variances, zero-amount handling, missing CU flags, and ingestion filters.
            </p>
          </div>
        </div>
      </div>

      <form onSubmit={handleSaveSystemSettings} className="p-6 space-y-6">
        {/* Amount Tolerance Card */}
        <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
              <Percent className="w-3.5 h-3.5 text-slate-500" />
              Maximum Amount Tolerance (KES)
            </label>
            <span className="text-xs font-mono font-bold text-slate-900">
              KES {numericTolerance.toLocaleString("en-KE", { minimumFractionDigits: 2 })}
            </span>
          </div>

          <input
            type="number"
            step="0.01"
            min="0"
            max="1000000"
            value={amountTolerance}
            onChange={(e) => setAmountTolerance(e.target.value)}
            required
            className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-900 text-sm font-mono transition-colors focus:outline-none focus:ring-2 focus:ring-[#0e1734]/20 focus:border-[#0e1734]"
          />

          {showToleranceWarning && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-900 text-xs flex items-center gap-2.5">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
              <div>
                <strong>High Tolerance Warning:</strong> Variance above KES 1,000.00 will automatically mark invoices as MATCHED despite substantial financial discrepancy.
              </div>
            </div>
          )}
        </div>

        {/* Policies Selector */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-slate-500" />
              Base Amount Discrepancy Policy
            </label>
            <select
              value={baseAmountPolicy}
              onChange={(e) => setBaseAmountPolicy(e.target.value as BaseAmountPolicy)}
              className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-[#0e1734]/20 focus:border-[#0e1734] font-medium cursor-pointer"
            >
              <option value="allow">Allow All Amounts (Includes Negative & Zero - Default)</option>
              <option value="skip">Skip Zero Amounts (0.00)</option>
              <option value="reject">Reject Reconciliation Session on Zero Amount</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
              <FileCheck className="w-3.5 h-3.5 text-slate-500" />
              Unmapped VAT Tax Code Policy
            </label>
              <select
                value={unmappedVatPolicy}
                onChange={(e) => setUnmappedVatPolicy(e.target.value as UnmappedVatPolicy)}
                className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-[#0e1734]/20 focus:border-[#0e1734] font-medium cursor-pointer"
              >
                <option value="needs_review">Mark for Audit Review (NEEDS_REVIEW)</option>
                <option value="reject_invoice">Reject Specific Invoice Immediately</option>
              </select>
          </div>
        </div>

        {/* CU Number Field Sources (Sales & Purchases) */}
        <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-200/80 pb-2.5">
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-slate-500" />
              SAP Control Unit (CU) Field Mapping
            </h3>
            <span className="text-[11px] text-slate-500">
              Type custom SAP UDF name or pick a preset
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Sales CU Source */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                Sales Invoice CU Field
              </label>
              <div className="relative">
                <input
                  type="text"
                  list="sales-cu-preset-list"
                  value={salesCuSource}
                  onChange={(e) => setSalesCuSource(e.target.value)}
                  placeholder="e.g. U_CUINV, NumAtCard, Comments"
                  required
                  className="w-full px-3.5 py-2 h-9 rounded-lg border border-slate-200 bg-white text-slate-900 text-sm font-mono transition-colors focus:outline-none focus:ring-2 focus:ring-[#0e1734]/20 focus:border-[#0e1734]"
                />
                <datalist id="sales-cu-preset-list">
                  <option value="U_CUINV">KRA (U_CUINV)</option>
                  <option value="NumAtCard">Customer Ref (NumAtCard)</option>
                  <option value="Comments">Comments</option>
                  <option value="JournalMemo">Journal Memo</option>
                  <option value="Reference1">Ref 1</option>
                </datalist>
              </div>
              <div className="flex flex-wrap gap-1 pt-0.5">
                {["U_CUINV", "NumAtCard", "Comments", "JournalMemo", "Reference1"].map((field) => (
                  <button
                    key={field}
                    type="button"
                    onClick={() => setSalesCuSource(field)}
                    className={`px-2 py-0.5 text-[11px] font-mono rounded border transition-colors ${
                      salesCuSource === field
                        ? "bg-[#0e1734] text-white border-[#0e1734]"
                        : "bg-white text-slate-600 border-slate-200 hover:bg-slate-100"
                    }`}
                  >
                    {field}
                  </button>
                ))}
              </div>
              <span className="text-[11px] text-slate-500 block">
                SAP field holding the Control Unit number on Sales Invoices.
              </span>
            </div>

            {/* Purchase CU Source */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                Purchase Invoice CU Field
              </label>
              <div className="relative">
                <input
                  type="text"
                  list="purchase-cu-preset-list"
                  value={purchaseCuSource}
                  onChange={(e) => setPurchaseCuSource(e.target.value)}
                  placeholder="e.g. U_CUINV, NumAtCard, Comments"
                  required
                  className="w-full px-3.5 py-2 h-9 rounded-lg border border-slate-200 bg-white text-slate-900 text-sm font-mono transition-colors focus:outline-none focus:ring-2 focus:ring-[#0e1734]/20 focus:border-[#0e1734]"
                />
                <datalist id="purchase-cu-preset-list">
                  <option value="U_CUINV">KRA (U_CUINV)</option>
                  <option value="NumAtCard">Vendor Ref (NumAtCard)</option>
                  <option value="Comments">Comments</option>
                  <option value="JournalMemo">Journal Memo</option>
                  <option value="Reference1">Ref 1</option>
                </datalist>
              </div>
              <div className="flex flex-wrap gap-1 pt-0.5">
                {["U_CUINV", "NumAtCard", "Comments", "JournalMemo", "Reference1"].map((field) => (
                  <button
                    key={field}
                    type="button"
                    onClick={() => setPurchaseCuSource(field)}
                    className={`px-2 py-0.5 text-[11px] font-mono rounded border transition-colors ${
                      purchaseCuSource === field
                        ? "bg-[#0e1734] text-white border-[#0e1734]"
                        : "bg-white text-slate-600 border-slate-200 hover:bg-slate-100"
                    }`}
                  >
                    {field}
                  </button>
                ))}
              </div>
              <span className="text-[11px] text-slate-500 block">
                SAP field holding the Control Unit number on Purchase Invoices.
              </span>
            </div>
          </div>
        </div>

        {/* Action Button */}
        <div className="pt-4 border-t border-slate-200 flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#0e1734] hover:bg-[#16224c] active:bg-[#080d21] text-white rounded-lg text-sm font-semibold shadow-sm transition-all duration-150 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Save Operational Rules
          </button>
        </div>
      </form>
    </div>
  );
}
