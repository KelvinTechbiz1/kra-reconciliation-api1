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
  const [purchaseCuSource, setPurchaseCuSource] = useState<PurchaseCUField>(
    settings.purchase_cu_source
  );

  useEffect(() => {
    setAmountTolerance(settings.amount_tolerance);
    setBaseAmountPolicy(settings.base_amount_policy);
    setUnmappedVatPolicy(settings.unmapped_vat_policy);
    setPurchaseCuSource(settings.purchase_cu_source);
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

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-slate-500" />
                Purchase CU Number Source
              </label>
              <select
                value={purchaseCuSource}
                onChange={(e) => setPurchaseCuSource(e.target.value as PurchaseCUField)}
                className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-[#0e1734]/20 focus:border-[#0e1734] font-medium cursor-pointer"
              >
                <option value="U_CUINV">KRA (U_CUINV)</option>
                <option value="NumAtCard">Vendor Reference (NumAtCard)</option>
                <option value="Comments">Comments</option>
                <option value="JournalMemo">Journal Memo (JournalMemo)</option>
                <option value="Reference1">Invoice Number (Reference1)</option>
              </select>
              <span className="text-[11px] text-slate-500 block">
                SAP field that stores the Control Unit number on Purchase Invoices.
              </span>
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
