"use client";

import { useState, useEffect, useMemo } from "react";
import { KRAParsingProfilesConfig, SystemSettings } from "@/types/settings";
import { fetchWithAuth } from "@/lib/api";
import { getApiErrorMessage } from "@/lib/errors";
import { indexToExcelColumnName, validateKRAParsingProfileSection } from "@/lib/validators";
import { useToast } from "@/components/ToastProvider";
import {
  FileSpreadsheet,
  Save,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
} from "lucide-react";

interface KRAParsingProfilesCardProps {
  settings: SystemSettings;
  selectedCompanyId?: number | null;
  onSaved: () => void;
}

const KRA_FIELDS = [
  { key: "pin_column", label: "PIN Column Index" },
  { key: "partner_name_column", label: "Partner Name Column Index" },
  { key: "invoice_number_column", label: "Invoice Number Column Index" },
  { key: "invoice_date_column", label: "Invoice Date Column Index" },
  { key: "cu_number_column", label: "CU / Receipt Number Column Index" },
  { key: "base_amount_column", label: "Base Amount Column Index" },
] as const;

const KRA_DEFAULT_COLUMNS: Record<string, number> = {
  pin_column: 0,
  partner_name_column: 1,
  invoice_number_column: 2,
  invoice_date_column: 3,
  cu_number_column: 4,
  base_amount_column: 5,
};

const availableSections = ["SEC_B", "SEC_F", "SEC_G", "SEC_H", "SEC_I"];

export function KRAParsingProfilesCard({ settings, selectedCompanyId, onSaved }: KRAParsingProfilesCardProps) {
  const [kraParsingProfiles, setKraParsingProfiles] = useState<KRAParsingProfilesConfig>(
    settings.kra_parsing_profiles || { schema_version: 1, profiles: {} }
  );
  const [activeProfileTab, setActiveProfileTab] = useState("SEC_B");

  useEffect(() => {
    setKraParsingProfiles(
      settings.kra_parsing_profiles || { schema_version: 1, profiles: {} }
    );
  }, [settings.kra_parsing_profiles]);

  const handleProfileChange = (section: string, field: string, value: string) => {
    const numValue = value === "" ? null : parseInt(value, 10);
    setKraParsingProfiles((prev) => ({
      ...prev,
      profiles: {
        ...prev.profiles,
        [section]: {
          ...prev.profiles[section],
          [field]: numValue,
        },
      },
    }));
  };

  const handleApplyDefaults = (section: string) => {
    setKraParsingProfiles((prev) => ({
      ...prev,
      profiles: {
        ...prev.profiles,
        [section]: {
          ...prev.profiles[section],
          ...KRA_DEFAULT_COLUMNS,
        },
      },
    }));
  };

  const [saving, setSaving] = useState(false);
  const { notify } = useToast();

  const activeProfileData = useMemo(() => {
    return (
      (kraParsingProfiles.profiles as unknown as Record<string, Record<string, number | null>>)[activeProfileTab] || {}
    );
  }, [kraParsingProfiles.profiles, activeProfileTab]);

  // Compute live client validation for the active profile tab
  const validationResult = useMemo(() => {
    return validateKRAParsingProfileSection(activeProfileData);
  }, [activeProfileData]);

  // Check all sections for tab badge status
  const sectionValidationStatus = useMemo(() => {
    const statusMap: Record<string, { valid: boolean; errorCount: number }> = {};
    for (const sec of availableSections) {
      const secData = (kraParsingProfiles.profiles as unknown as Record<string, Record<string, number | null>>)[sec] || {};
      const res = validateKRAParsingProfileSection(secData);
      statusMap[sec] = {
        valid: res.valid,
        errorCount: Object.keys(res.fieldErrors).length,
      };
    }
    return statusMap;
  }, [kraParsingProfiles.profiles]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();

    // Overall validation check across all sections before submission
    let hasAnyValidationError = false;
    for (const sec of availableSections) {
      const secData = (kraParsingProfiles.profiles as unknown as Record<string, Record<string, number | null>>)[sec] || {};
      const res = validateKRAParsingProfileSection(secData);
      if (!res.valid) {
        hasAnyValidationError = true;
        setActiveProfileTab(sec);
        break;
      }
    }

    if (hasAnyValidationError) {
      notify("Please resolve the highlighted validation errors before saving.", "error");
      return;
    }

    setSaving(true);

    try {
      const payload = {
        kra_parsing_profiles: kraParsingProfiles,
        version: settings.version,
      };

      const url = `/settings/system-settings${selectedCompanyId ? `?company_id=${selectedCompanyId}` : ""}`;
      const res = await fetchWithAuth(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        const errorMsg = getApiErrorMessage(
          errData,
          res.status === 409
            ? "Optimistic lock error: Remote settings have been updated by another user."
            : "Failed to update KRA CSV parsing profiles."
        );
        throw new Error(errorMsg);
      }

      notify("KRA CSV parsing profiles saved successfully!", "success");
      onSaved();
    } catch (err: unknown) {
      const msg = getApiErrorMessage(err, "An error occurred while saving profiles.");
      notify(msg, "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-6 py-5 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-slate-50 rounded-lg border border-slate-200">
            <FileSpreadsheet className="w-5 h-5 text-slate-500" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900">KRA CSV Parsing Profiles</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Configure 0-based column positions for CSV ingestion per KRA section
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => handleApplyDefaults(activeProfileTab)}
          className="text-xs text-[#0e1734] hover:text-[#16224c] font-semibold flex items-center gap-1 cursor-pointer"
        >
          <RotateCcw className="w-3.5 h-3.5" /> Reset {activeProfileTab} to KRA Defaults
        </button>
      </div>

      <form onSubmit={handleSave} className="p-6 space-y-6">
        {/* Section Tabs */}
        <div className="border border-slate-200 rounded-lg overflow-hidden">
          <div className="flex bg-slate-50 border-b border-slate-200 p-1 gap-1 overflow-x-auto">
            {availableSections.map((sec) => {
              const isActive = activeProfileTab === sec;
              const status = sectionValidationStatus[sec];
              const isInvalid = status && !status.valid;

              return (
                <button
                  key={sec}
                  type="button"
                  onClick={() => setActiveProfileTab(sec)}
                  className={`px-3.5 py-1.5 rounded-md text-xs font-semibold transition-colors cursor-pointer border flex items-center gap-1.5 ${
                    isActive
                      ? "bg-white text-slate-900 shadow-xs border-slate-200"
                      : "text-slate-500 border-transparent hover:text-slate-800"
                  }`}
                >
                  <span>{sec}</span>
                  {isInvalid ? (
                    <span className="flex items-center gap-0.5 text-red-600 text-[10px] font-bold" title={`${status.errorCount} collision/validation issue(s)`}>
                      <AlertTriangle className="w-3 h-3 text-red-500" />
                    </span>
                  ) : (
                    <CheckCircle2 className="w-3 h-3 text-emerald-500 opacity-60" />
                  )}
                </button>
              );
            })}
          </div>

          <div className="p-5 bg-white">
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
              {KRA_FIELDS.map((f) => {
                const rawVal = activeProfileData[f.key];
                const val = rawVal ?? "";
                const excelCol = typeof rawVal === "number" ? indexToExcelColumnName(rawVal) : "";
                const fieldError = validationResult.fieldErrors[f.key];

                return (
                  <div key={f.key} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-slate-700">{f.label}</label>
                      {excelCol && (
                        <span className="text-[11px] font-mono text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                          Col {rawVal} ({excelCol})
                        </span>
                      )}
                    </div>

                    <input
                      type="number"
                      min={0}
                      value={val}
                      onChange={(e) => handleProfileChange(activeProfileTab, f.key, e.target.value)}
                      placeholder="–"
                      className={`w-full px-3 py-1.5 h-9 rounded-md border text-xs font-mono text-slate-900 focus:outline-none transition-colors placeholder:text-slate-300 ${
                        fieldError
                          ? "border-red-400 bg-red-50/50 focus:border-red-500 ring-1 ring-red-400/20"
                          : "border-slate-200 focus:border-[#0e1734]"
                      }`}
                    />

                    {fieldError && (
                      <p className="text-[11px] font-medium text-red-600 mt-0.5 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3 shrink-0 text-red-500" />
                        {fieldError}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Save Button */}
        <div className="pt-2 flex items-center justify-between">
          {!validationResult.valid ? (
            <p className="text-xs font-medium text-red-600 flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              {validationResult.messages[0]}
            </p>
          ) : (
            <div />
          )}

          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-[#0e1734] hover:bg-[#16224c] active:bg-[#080d21] text-white rounded-lg font-semibold text-xs transition-colors cursor-pointer disabled:opacity-50 shrink-0 h-9"
          >
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            Save Parsing Profiles
          </button>
        </div>
      </form>
    </div>
  );
}
