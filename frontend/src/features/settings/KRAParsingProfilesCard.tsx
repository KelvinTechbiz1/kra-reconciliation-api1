"use client";

import { useState, useEffect, useMemo } from "react";
import { KRAParsingProfileItem, KRAParsingProfilesConfig, SystemSettings } from "@/types/settings";
import { fetchWithAuth } from "@/lib/api";
import { getApiErrorMessage } from "@/lib/errors";
import {
  indexToExcelColumnName,
  validateKRAParsingProfileSection,
  validateKRASectionPrefix,
} from "@/lib/validators";
import { useToast } from "@/components/ToastProvider";
import {
  FileSpreadsheet,
  Save,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Plus,
  Trash2,
  X,
  Info,
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

const SECTION_DEFAULTS: Record<string, KRAParsingProfileItem> = {
  SEC_B: { pin_column: 0, partner_name_column: 1, invoice_number_column: 2, invoice_date_column: 3, cu_number_column: 4, base_amount_column: 6 },
  SEC_E: { pin_column: 0, partner_name_column: 1, invoice_number_column: 2, invoice_date_column: 3, cu_number_column: 4, base_amount_column: 6 },
  SEC_F: { pin_column: 1, partner_name_column: 2, invoice_number_column: null, invoice_date_column: 3, cu_number_column: 4, base_amount_column: 7 },
  SEC_G: { pin_column: 1, partner_name_column: 2, invoice_number_column: null, invoice_date_column: 3, cu_number_column: 4, base_amount_column: 7 },
  SEC_H: { pin_column: 1, partner_name_column: 2, invoice_number_column: null, invoice_date_column: 3, cu_number_column: 4, base_amount_column: 8 },
  SEC_I: { pin_column: 1, partner_name_column: 2, invoice_number_column: null, invoice_date_column: 3, cu_number_column: 4, base_amount_column: 7 },
};

const KRA_DEFAULT_COLUMNS: KRAParsingProfileItem = SECTION_DEFAULTS.SEC_B;

export function KRAParsingProfilesCard({ settings, selectedCompanyId, onSaved }: KRAParsingProfilesCardProps) {
  const [kraParsingProfiles, setKraParsingProfiles] = useState<KRAParsingProfilesConfig>(
    settings.kra_parsing_profiles || { schema_version: 1, profiles: {} }
  );

  const availableSections = useMemo(() => {
    const set = new Set([
      ...Object.keys(SECTION_DEFAULTS),
      ...Object.keys(kraParsingProfiles.profiles || {}),
    ]);
    return Array.from(set).sort();
  }, [kraParsingProfiles.profiles]);

  const [activeProfileTab, setActiveProfileTab] = useState<string>("SEC_B");

  useEffect(() => {
    setKraParsingProfiles(
      settings.kra_parsing_profiles || { schema_version: 1, profiles: {} }
    );
  }, [settings.kra_parsing_profiles]);

  useEffect(() => {
    if (availableSections.length > 0 && !availableSections.includes(activeProfileTab)) {
      setActiveProfileTab(availableSections[0]);
    }
  }, [availableSections, activeProfileTab]);

  // Modal / inline form states for adding a new section profile
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newPrefixInput, setNewPrefixInput] = useState("");
  const [templateSection, setTemplateSection] = useState("SEC_B");
  const [addPrefixError, setAddPrefixError] = useState<string | null>(null);

  // Confirmation state for deleting a section profile
  const [deleteConfirmSection, setDeleteConfirmSection] = useState<string | null>(null);

  const handleProfileChange = (section: string, field: keyof KRAParsingProfileItem, value: string) => {
    const numValue = value === "" ? null : parseInt(value, 10);
    setKraParsingProfiles((prev) => {
      const currentSection: KRAParsingProfileItem =
        prev.profiles[section] || SECTION_DEFAULTS[section] || KRA_DEFAULT_COLUMNS;
      return {
        ...prev,
        profiles: {
          ...prev.profiles,
          [section]: {
            ...currentSection,
            [field]: numValue,
          },
        },
      };
    });
  };

  const handleApplyDefaults = (section: string) => {
    const defaults = SECTION_DEFAULTS[section] || KRA_DEFAULT_COLUMNS;
    setKraParsingProfiles((prev) => ({
      ...prev,
      profiles: {
        ...prev.profiles,
        [section]: defaults,
      },
    }));
    notify(`Reset ${section} column positions to defaults. Remember to save changes.`, "info");
  };

  const handleOpenAddModal = () => {
    setNewPrefixInput("");
    setTemplateSection(activeProfileTab || "SEC_B");
    setAddPrefixError(null);
    setIsAddModalOpen(true);
  };

  const handleCreateSectionProfile = (e: React.FormEvent) => {
    e.preventDefault();
    const validation = validateKRASectionPrefix(newPrefixInput);
    if (!validation.valid || !validation.formatted) {
      setAddPrefixError(validation.error || "Invalid section identifier format.");
      return;
    }

    const formattedPrefix = validation.formatted;
    if (availableSections.includes(formattedPrefix) && kraParsingProfiles.profiles[formattedPrefix]) {
      setAddPrefixError(`Section profile '${formattedPrefix}' already exists.`);
      return;
    }

    const templateData: KRAParsingProfileItem =
      kraParsingProfiles.profiles[templateSection] ||
      SECTION_DEFAULTS[templateSection] ||
      KRA_DEFAULT_COLUMNS;

    setKraParsingProfiles((prev) => ({
      ...prev,
      profiles: {
        ...prev.profiles,
        [formattedPrefix]: { ...templateData },
      },
    }));

    setActiveProfileTab(formattedPrefix);
    setIsAddModalOpen(false);
    notify(`Created profile for ${formattedPrefix}. Save changes to persist.`, "success");
  };

  const handleDeleteSectionProfile = (section: string) => {
    setKraParsingProfiles((prev) => {
      const updatedProfiles = { ...prev.profiles };
      delete updatedProfiles[section];
      return {
        ...prev,
        profiles: updatedProfiles,
      };
    });

    const remaining = availableSections.filter((s) => s !== section);
    if (remaining.length > 0) {
      setActiveProfileTab(remaining[0]);
    }
    setDeleteConfirmSection(null);
    notify(`Removed profile for ${section}. Save changes to persist.`, "info");
  };

  const [saving, setSaving] = useState(false);
  const { notify } = useToast();

  const activeProfileData = useMemo(() => {
    const stored = (kraParsingProfiles.profiles as Record<string, KRAParsingProfileItem>)[activeProfileTab];
    if (stored) return stored;
    if (SECTION_DEFAULTS[activeProfileTab]) return SECTION_DEFAULTS[activeProfileTab];
    return KRA_DEFAULT_COLUMNS;
  }, [kraParsingProfiles.profiles, activeProfileTab]);

  const validationResult = useMemo(() => {
    return validateKRAParsingProfileSection(activeProfileData as unknown as Record<string, number | null>);
  }, [activeProfileData]);

  const sectionValidationStatus = useMemo(() => {
    const statusMap: Record<string, { valid: boolean; errorCount: number }> = {};
    for (const sec of availableSections) {
      const secData =
        (kraParsingProfiles.profiles as Record<string, KRAParsingProfileItem>)[sec] ||
        SECTION_DEFAULTS[sec] ||
        KRA_DEFAULT_COLUMNS;
      const res = validateKRAParsingProfileSection(secData as unknown as Record<string, number | null>);
      statusMap[sec] = {
        valid: res.valid,
        errorCount: Object.keys(res.fieldErrors).length,
      };
    }
    return statusMap;
  }, [availableSections, kraParsingProfiles.profiles]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();

    let hasAnyValidationError = false;
    for (const sec of availableSections) {
      const secData =
        (kraParsingProfiles.profiles as Record<string, KRAParsingProfileItem>)[sec] ||
        SECTION_DEFAULTS[sec] ||
        KRA_DEFAULT_COLUMNS;
      const res = validateKRAParsingProfileSection(secData as unknown as Record<string, number | null>);
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
      <div className="px-6 py-5 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-slate-50 rounded-lg border border-slate-200">
            <FileSpreadsheet className="w-5 h-5 text-slate-500" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900">KRA CSV Parsing Profiles</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Configure 0-based column positions for CSV ingestion per KRA section (e.g. SEC_B, SEC_J)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={handleOpenAddModal}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#0e1734] hover:bg-[#16224c] text-white text-xs font-semibold rounded-lg transition-colors cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" /> Add Section Profile
          </button>
        </div>
      </div>

      <form onSubmit={handleSave} className="p-6 space-y-6">
        {/* Section Tabs Container */}
        <div className="border border-slate-200 rounded-lg overflow-hidden">
          {/* Tabs bar */}
          <div className="flex bg-slate-50 border-b border-slate-200 p-1.5 gap-1.5 overflow-x-auto items-center justify-between">
            <div className="flex items-center gap-1.5 overflow-x-auto">
              {availableSections.map((sec) => {
                const isActive = activeProfileTab === sec;
                const status = sectionValidationStatus[sec];
                const isInvalid = status && !status.valid;
                const isCustom = !SECTION_DEFAULTS[sec];

                return (
                  <button
                    key={sec}
                    type="button"
                    onClick={() => setActiveProfileTab(sec)}
                    className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors cursor-pointer border flex items-center gap-1.5 shrink-0 ${
                      isActive
                        ? "bg-white text-slate-900 shadow-xs border-slate-200"
                        : "text-slate-500 border-transparent hover:text-slate-800"
                    }`}
                  >
                    <span>{sec}</span>
                    {isCustom && (
                      <span className="text-[9px] font-mono px-1 bg-slate-200 text-slate-600 rounded">
                        custom
                      </span>
                    )}
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
          </div>

          {/* Active Tab Workspace Header */}
          <div className="px-5 py-3 bg-slate-50/50 border-b border-slate-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-900">{activeProfileTab} Configuration</span>
              {!SECTION_DEFAULTS[activeProfileTab] && (
                <span className="text-[10px] bg-slate-200 text-slate-700 font-mono px-1.5 py-0.5 rounded font-medium">
                  Custom Section Profile
                </span>
              )}
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => handleApplyDefaults(activeProfileTab)}
                className="text-xs text-slate-600 hover:text-slate-900 font-medium flex items-center gap-1 cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" /> Reset to Defaults
              </button>

              <button
                type="button"
                onClick={() => setDeleteConfirmSection(activeProfileTab)}
                className="text-xs text-red-600 hover:text-red-700 font-medium flex items-center gap-1 cursor-pointer"
                title={`Delete ${activeProfileTab} parsing profile`}
              >
                <Trash2 className="w-3.5 h-3.5" /> Delete Profile
              </button>
            </div>
          </div>

          {/* Column Index Inputs Grid */}
          <div className="p-5 bg-white">
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
              {KRA_FIELDS.map((f) => {
                const rawVal = (activeProfileData as unknown as Record<string, number | null>)[f.key];
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

        {/* Save & Validation Bar */}
        <div className="pt-2 flex items-center justify-between">
          {!validationResult.valid ? (
            <p className="text-xs font-medium text-red-600 flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              {validationResult.messages[0]}
            </p>
          ) : (
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <Info className="w-4 h-4 text-slate-400" />
              <span>Clicking Save will update CSV parsing column positions for your company.</span>
            </div>
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

      {/* Add New Section Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full border border-slate-200 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-2">
                <Plus className="w-4 h-4 text-[#0e1734]" />
                <h3 className="text-sm font-bold text-slate-900">Add KRA CSV Section Profile</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsAddModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-md cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateSectionProfile} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Section Prefix Identifier
                </label>
                <input
                  type="text"
                  placeholder="e.g. SEC_J, SEC_A, SEC_J1"
                  value={newPrefixInput}
                  onChange={(e) => {
                    setNewPrefixInput(e.target.value);
                    setAddPrefixError(null);
                  }}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs font-mono text-slate-900 focus:outline-none focus:border-[#0e1734]"
                  autoFocus
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  Must start with <code className="bg-slate-100 px-1 py-0.5 rounded text-[#0e1734]">SEC_</code> followed by uppercase letters, numbers, or underscores.
                </p>
                {addPrefixError && (
                  <p className="text-xs font-medium text-red-600 mt-1.5 flex items-center gap-1">
                    <AlertTriangle className="w-3.5 h-3.5 text-red-500 shrink-0" />
                    {addPrefixError}
                  </p>
                )}
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Copy Initial Column Settings From
                </label>
                <select
                  value={templateSection}
                  onChange={(e) => setTemplateSection(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs text-slate-900 focus:outline-none focus:border-[#0e1734] bg-white cursor-pointer"
                >
                  {availableSections.map((sec) => (
                    <option key={sec} value={sec}>
                      {sec} Column Layout
                    </option>
                  ))}
                </select>
              </div>

              <div className="pt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 rounded-lg cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-[#0e1734] hover:bg-[#16224c] text-white text-xs font-semibold rounded-lg cursor-pointer"
                >
                  Create Profile
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirmSection && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full border border-slate-200 overflow-hidden">
            <div className="p-6 space-y-3">
              <div className="flex items-center gap-3 text-red-600">
                <div className="p-2 bg-red-50 rounded-full border border-red-200">
                  <Trash2 className="w-5 h-5 text-red-600" />
                </div>
                <h3 className="text-sm font-bold text-slate-900">Delete {deleteConfirmSection} Profile?</h3>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Are you sure you want to remove the CSV parsing profile for{" "}
                <strong className="text-slate-900 font-mono">{deleteConfirmSection}</strong>?
                This will remove its column mapping configuration upon saving.
              </p>

              <div className="pt-3 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setDeleteConfirmSection(null)}
                  className="px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 rounded-lg cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => handleDeleteSectionProfile(deleteConfirmSection)}
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-lg cursor-pointer"
                >
                  Delete Profile
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
