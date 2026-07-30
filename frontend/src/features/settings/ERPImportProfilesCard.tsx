"use client";

import { useEffect, useState, useCallback } from "react";
import { createPortal } from "react-dom";
import {
  ImportProfile,
  ImportProfileCreate,
  HeaderDetectionResponse,
  MappingPreviewResponse,
  ReconciliationType,
  SourceFormat,
} from "@/types/import_profile";
import { fetchWithAuth } from "@/lib/api";
import { getApiErrorMessage } from "@/lib/errors";
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
  Pencil,
  Eye,
  Upload,
  Play,
  Sparkles,
  AlertCircle,
  Tag,
  ChevronDown,
  ChevronRight,
  Star,
} from "lucide-react";

interface ERPImportProfilesCardProps {
  selectedCompanyId?: number | null;
}

/* ─── Confirm Modal ─────────────────────────────────────────────────────── */

interface ConfirmModalProps {
  title: string;
  message: string;
  confirmLabel: string;
  variant?: "danger" | "warning" | "default";
  onConfirm: () => void;
  onClose: () => void;
  loading?: boolean;
}

function ConfirmModal({ title, message, confirmLabel, variant = "default", onConfirm, onClose, loading }: ConfirmModalProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);
  if (!mounted) return null;

  const btnColors = {
    danger: "bg-rose-600 hover:bg-rose-700 text-white",
    warning: "bg-amber-600 hover:bg-amber-700 text-white",
    default: "bg-[#0e1734] hover:bg-[#16224c] text-white",
  };

  return createPortal(
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-sm overflow-hidden animate-in zoom-in-95 duration-150">
        <div className="px-6 py-5">
          <h3 className="font-bold text-slate-900 text-sm">{title}</h3>
          <p className="text-xs text-slate-500 mt-1.5">{message}</p>
        </div>
        <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-slate-600 hover:text-slate-900 text-xs font-semibold transition-colors cursor-pointer">
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50 ${btnColors[variant]}`}
          >
            {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

/* ─── Add / Edit Import Profile Modal ───────────────────────────────────── */

interface AddEditModalProps {
  profileToEdit?: ImportProfile | null;
  onClose: () => void;
  onSaved: () => void;
}

function AddEditImportProfileModal({ profileToEdit, onClose, onSaved }: AddEditModalProps) {
  const [mounted, setMounted] = useState(false);
  const [saving, setSaving] = useState(false);

  // Form State — Basics
  const [formName, setFormName] = useState(profileToEdit?.name || "");
  const [formModule, setFormModule] = useState<ReconciliationType>(profileToEdit?.module || "sales");
  const [formProvider, setFormProvider] = useState(profileToEdit?.provider || "CUSTOM");
  const [formDescription, setFormDescription] = useState(profileToEdit?.description || "");
  const [formFormat, setFormFormat] = useState<SourceFormat>(profileToEdit?.source_format || "csv");
  const [isDefault, setIsDefault] = useState(profileToEdit?.is_default || false);

  // Helper to extract primary column header for UI display and editing
  const getMappedString = (val: string[] | string | undefined): string => {
    if (!val) return "";
    if (Array.isArray(val)) return val[0] || "";
    return String(val);
  };

  // Column Mappings
  const [pinAlias, setPinAlias] = useState(getMappedString(profileToEdit?.column_mapping.pin));
  const [partnerAlias, setPartnerAlias] = useState(getMappedString(profileToEdit?.column_mapping.partner_name));
  const [invNumAlias, setInvNumAlias] = useState(getMappedString(profileToEdit?.column_mapping.invoice_number));
  const [invDateAlias, setInvDateAlias] = useState(getMappedString(profileToEdit?.column_mapping.invoice_date));
  const [cuNumAlias, setCuNumAlias] = useState(getMappedString(profileToEdit?.column_mapping.cu_number));
  const [vatGroupAlias, setVatGroupAlias] = useState(getMappedString(profileToEdit?.column_mapping.vat_group));
  const [baseAmtAlias, setBaseAmtAlias] = useState(getMappedString(profileToEdit?.column_mapping.base_amount));
  const [taxAmtAlias, setTaxAmtAlias] = useState(getMappedString(profileToEdit?.column_mapping.tax_amount));
  const [vatDerivationEnabled, setVatDerivationEnabled] = useState(profileToEdit?.validation_rules.vat_derivation_enabled || false);

  // Active Focused Alias Input
  const [activeAliasField, setActiveAliasField] = useState<string>("pin");

  // Parsing Hints
  const [headerRow, setHeaderRow] = useState(profileToEdit?.parsing_hints.header_row || 1);
  const [dataStartRow, setDataStartRow] = useState(profileToEdit?.parsing_hints.data_start_row || 2);
  const [dateFormat, setDateFormat] = useState(profileToEdit?.parsing_hints.date_format || "YYYY-MM-DD");
  const [delimiter, setDelimiter] = useState(profileToEdit?.parsing_hints.delimiter || ",");

  // Collapsible sections
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Sample File & Preview
  const [sampleFile, setSampleFile] = useState<File | null>(null);
  const [detectedHeaders, setDetectedHeaders] = useState<string[]>([]);
  const [previewing, setPreviewing] = useState(false);
  const [previewData, setPreviewData] = useState<MappingPreviewResponse | null>(null);

  const { notify } = useToast();

  useEffect(() => { setMounted(true); }, []);

  const handleSampleFileUpload = async (file: File) => {
    setSampleFile(file);
    setPreviewData(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetchWithAuth("/import-profiles/detect-headers", { method: "POST", body: formData });
      if (!res.ok) throw new Error("Failed to detect headers.");
      const data: HeaderDetectionResponse = await res.json();

      if (data.detected_headers.length > 0) {
        setDetectedHeaders(data.detected_headers);
        setHeaderRow(data.header_row);
        setDataStartRow(data.data_start_row);
        const confMsg = data.confidence === "high" ? "Confident" : data.confidence === "medium" ? "Likely" : "Guessed";
        notify(`${confMsg}: headers found on row ${data.header_row}, data starts row ${data.data_start_row} (${data.detected_headers.length} columns).`, "success");
      } else {
        notify("No headers detected. Try setting the header row manually.", "error");
      }
    } catch (err: unknown) {
      notify(err instanceof Error ? err.message : "Failed to detect headers.", "error");
    }
  };

  const addHeaderToField = (headerName: string) => {
    const updaters: Record<string, React.Dispatch<React.SetStateAction<string>>> = {
      pin: setPinAlias, partner: setPartnerAlias, invNum: setInvNumAlias,
      invDate: setInvDateAlias, cuNum: setCuNumAlias, vatGroup: setVatGroupAlias,
      baseAmt: setBaseAmtAlias, taxAmt: setTaxAmtAlias,
    };
    updaters[activeAliasField]?.(headerName);
  };

  const buildColumnMapping = () => {
    const formatValue = (s: string): string[] => {
      const trimmed = s.trim();
      return trimmed ? [trimmed] : [];
    };
    return {
      pin: formatValue(pinAlias),
      partner_name: formatValue(partnerAlias),
      invoice_number: formatValue(invNumAlias),
      invoice_date: formatValue(invDateAlias),
      cu_number: formatValue(cuNumAlias),
      vat_group: formatValue(vatGroupAlias),
      base_amount: formatValue(baseAmtAlias),
      tax_amount: formatValue(taxAmtAlias),
    };
  };

  const buildValidationRules = () => {
    const existingRules = profileToEdit?.validation_rules;
    const baseSales = {
      module: "sales" as const,
      required_fields: existingRules?.module === "sales" ? (existingRules.required_fields ?? []) : ["cu_number", "vat_group", "base_amount"],
      allowed_vat_codes: existingRules?.module === "sales" ? (existingRules.allowed_vat_codes ?? ["16", "8", "0", "EXEMPT"]) : ["16", "8", "0", "EXEMPT"],
      date_strictness: (existingRules?.module === "sales" ? existingRules.date_strictness : "LENIENT") as "STRICT" | "LENIENT",
      row_skip_policy: (existingRules?.module === "sales" ? existingRules.row_skip_policy : "SKIP_EMPTY_AND_TOTALS") as "SKIP_EMPTY_AND_TOTALS" | "FAIL_ON_EMPTY",
      default_vat_group: existingRules?.module === "sales" ? (existingRules.default_vat_group ?? "16") : "16",
      require_valid_pin_format: existingRules?.module === "sales" ? (existingRules.require_valid_pin_format ?? true) : true,
      vat_derivation_enabled: vatDerivationEnabled,
    };
    const basePurchases = {
      module: "purchases" as const,
      required_fields: existingRules?.module === "purchases" ? (existingRules.required_fields ?? []) : ["cu_number", "vat_group", "base_amount"],
      allowed_vat_codes: existingRules?.module === "purchases" ? (existingRules.allowed_vat_codes ?? ["16", "8", "0", "EXEMPT"]) : ["16", "8", "0", "EXEMPT"],
      date_strictness: (existingRules?.module === "purchases" ? existingRules.date_strictness : "LENIENT") as "STRICT" | "LENIENT",
      row_skip_policy: (existingRules?.module === "purchases" ? existingRules.row_skip_policy : "SKIP_EMPTY_AND_TOTALS") as "SKIP_EMPTY_AND_TOTALS" | "FAIL_ON_EMPTY",
      default_vat_group: existingRules?.module === "purchases" ? (existingRules.default_vat_group ?? "16") : "16",
      purchase_cu_fallback_field: existingRules?.module === "purchases" ? existingRules.purchase_cu_fallback_field : undefined,
      vat_derivation_enabled: vatDerivationEnabled,
    };
    return formModule === "sales" ? baseSales : basePurchases;
  };

  const handleRunLivePreview = async () => {
    if (!sampleFile) { notify("Please upload a sample file first.", "error"); return; }
    setPreviewing(true);
    try {
      const draftSnapshot = {
        id: profileToEdit?.id || 0,
        scope: profileToEdit?.scope || "company",
        name: formName.trim() || "Draft Profile",
        module: formModule,
        provider: formProvider.trim().toUpperCase() || "CUSTOM",
        source_format: formFormat,
        parsing_hints: {
          has_header: true,
          header_row: Number(headerRow),
          data_start_row: Number(dataStartRow),
          delimiter: delimiter || ",",
          date_format: dateFormat || "YYYY-MM-DD",
          decimal_separator: ".",
          thousands_separator: ",",
        },
        column_mapping: buildColumnMapping(),
        validation_rules: buildValidationRules(),
      };

      const formData = new FormData();
      formData.append("file", sampleFile);
      formData.append("draft_profile", JSON.stringify(draftSnapshot));

      const profileParam = profileToEdit?.id ? `&profile_id=${profileToEdit.id}` : "";
      const res = await fetchWithAuth(`/import-profiles/preview?module=${formModule}${profileParam}`, { method: "POST", body: formData });
      if (!res.ok) { const err = await res.json().catch(() => null); throw new Error(getApiErrorMessage(err, "Preview failed.")); }
      const data: MappingPreviewResponse = await res.json();
      setPreviewData(data);
      if (data.detected_headers.length > 0) setDetectedHeaders(data.detected_headers);
      notify(`Preview: ${data.total_rows_detected} rows detected.`, "success");
    } catch (err: unknown) {
      notify(getApiErrorMessage(err, "Preview error."), "error");
    } finally { setPreviewing(false); }
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim()) { notify("Profile name is required.", "error"); return; }
    setSaving(true);

    const payload: ImportProfileCreate = {
      name: formName.trim(),
      module: formModule,
      provider: formProvider.trim().toUpperCase() || "CUSTOM",
      description: formDescription.trim() || undefined,
      source_format: formFormat,
      parsing_hints: {
        has_header: true,
        header_row: Number(headerRow),
        data_start_row: Number(dataStartRow),
        delimiter: delimiter || ",",
        date_format: dateFormat || "YYYY-MM-DD",
        decimal_separator: ".",
        thousands_separator: ",",
      },
      column_mapping: buildColumnMapping(),
      validation_rules: buildValidationRules(),
      is_default: isDefault,
    };

    try {
      const url = profileToEdit ? `/import-profiles/${profileToEdit.id}` : "/import-profiles";
      const method = profileToEdit ? "PUT" : "POST";
      const res = await fetchWithAuth(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) { const errData = await res.json().catch(() => null); throw new Error(getApiErrorMessage(errData, "Failed to save profile.")); }
      notify(profileToEdit ? "Profile updated!" : "Profile created!", "success");
      onSaved();
      onClose();
    } catch (err: unknown) {
      notify(getApiErrorMessage(err, "Error saving profile."), "error");
    } finally { setSaving(false); }
  };

  if (!mounted) return null;

  const aliasFields = [
    { key: "cuNum", label: "CU / ETR Number", value: cuNumAlias, set: setCuNumAlias, required: true },
    { key: "vatGroup", label: "VAT Group / Tax Rate", value: vatGroupAlias, set: setVatGroupAlias, required: true },
    { key: "baseAmt", label: "Base Taxable Amount", value: baseAmtAlias, set: setBaseAmtAlias, required: true },
    { key: "taxAmt", label: "Tax Amount", value: taxAmtAlias, set: setTaxAmtAlias, required: false },
    { key: "pin", label: "PIN", value: pinAlias, set: setPinAlias, required: false },
    { key: "partner", label: "Partner / Customer Name", value: partnerAlias, set: setPartnerAlias, required: false },
    { key: "invNum", label: "Invoice Number", value: invNumAlias, set: setInvNumAlias, required: false },
    { key: "invDate", label: "Invoice Date", value: invDateAlias, set: setInvDateAlias, required: false },
  ];

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-3xl max-h-[92vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 shrink-0">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-sm">
                {profileToEdit ? `Edit: ${profileToEdit.name}` : "New Import Profile"}
              </h3>
              <p className="text-xs text-slate-500">Configure column mappings and parsing rules</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1 rounded-lg transition-colors cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSaveProfile} id="add-edit-import-profile-form" className="flex-1 overflow-y-auto p-6 space-y-6 text-xs">

          {/* ── Section 1: Basics ── */}
          <div className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block font-semibold text-slate-700 mb-1 text-[10px] uppercase tracking-wider">Profile Name *</label>
                <input type="text" required value={formName} onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. Bill Details - Purchases"
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium" />
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1 text-[10px] uppercase tracking-wider">Module *</label>
                <select value={formModule} onChange={(e) => setFormModule(e.target.value as ReconciliationType)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-800 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium cursor-pointer">
                  <option value="sales">Sales</option>
                  <option value="purchases">Purchases</option>
                </select>
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1 text-[10px] uppercase tracking-wider">Source Format *</label>
                <div className="flex rounded-lg border border-slate-200 overflow-hidden">
                  <button type="button" onClick={() => setFormFormat("csv")}
                    className={`flex-1 px-3 py-2 text-xs font-semibold transition-colors cursor-pointer ${formFormat === "csv" ? "bg-[#0e1734] text-white" : "bg-white text-slate-600 hover:bg-slate-50"}`}>
                    CSV
                  </button>
                  <button type="button" onClick={() => setFormFormat("xlsx")}
                    className={`flex-1 px-3 py-2 text-xs font-semibold transition-colors cursor-pointer ${formFormat === "xlsx" ? "bg-[#0e1734] text-white" : "bg-white text-slate-600 hover:bg-slate-50"}`}>
                    XLSX
                  </button>
                </div>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-slate-700 mb-1 text-[10px] uppercase tracking-wider">Provider</label>
                <input type="text" value={formProvider} onChange={(e) => setFormProvider(e.target.value)}
                  placeholder="ZOHO, QUICKBOOKS, CUSTOM"
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium" />
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1 text-[10px] uppercase tracking-wider">Description</label>
                <input type="text" value={formDescription} onChange={(e) => setFormDescription(e.target.value)}
                  placeholder="Optional notes"
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500" />
              </div>
            </div>
            <label className="inline-flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)}
                className="w-4 h-4 text-blue-600 rounded-md border-slate-300 focus:ring-blue-500 cursor-pointer" />
              <span className="font-semibold text-slate-700 text-xs">Set as default for {formModule.toUpperCase()}</span>
            </label>
          </div>

          {/* ── Section 2: Column Mappings ── */}
          <div className="border border-slate-200 rounded-xl overflow-hidden">
            <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sliders className="w-4 h-4 text-blue-600" />
                <h4 className="font-bold text-slate-800 text-xs">Column Mappings</h4>
              </div>
              <label className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer transition-colors">
                <Upload className="w-3.5 h-3.5 text-blue-600" />
                {sampleFile ? sampleFile.name : "Upload Sample File"}
                <input type="file" accept=".csv,.xlsx" className="hidden"
                  onChange={(e) => { if (e.target.files?.[0]) handleSampleFileUpload(e.target.files[0]); }} />
              </label>
            </div>
            <div className="p-4 space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {[
                  { key: "cuNum", label: "CU / ETR Number", value: cuNumAlias, set: setCuNumAlias, required: true },
                  { key: "vatGroup", label: "VAT Rate / Group", value: vatGroupAlias, set: setVatGroupAlias, required: true },
                  { key: "baseAmt", label: "Base Amount", value: baseAmtAlias, set: setBaseAmtAlias, required: true },
                  { key: "invNum", label: "Invoice Number", value: invNumAlias, set: setInvNumAlias, required: false },
                  { key: "partner", label: "Vendor / Customer Name", value: partnerAlias, set: setPartnerAlias, required: false },
                  { key: "invDate", label: "Invoice Date", value: invDateAlias, set: setInvDateAlias, required: false },
                  { key: "pin", label: "PIN", value: pinAlias, set: setPinAlias, required: false },
                  { key: "taxAmt", label: "Tax Amount", value: taxAmtAlias, set: setTaxAmtAlias, required: false },
                ].map(({ key, label, value, set, required }) => (
                  <div key={key} onFocus={() => setActiveAliasField(key)}>
                    <label className="block font-semibold text-slate-700 mb-1 text-[11px]">
                      {label} {required && <span className="text-rose-500 font-bold">*</span>}
                    </label>
                    {detectedHeaders.length > 0 ? (
                      <select
                        value={value}
                        onChange={(e) => set(e.target.value)}
                        className="w-full px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-800 text-xs font-medium focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 cursor-pointer"
                      >
                        <option value="">{required ? "-- Select Column --" : "-- Unmapped --"}</option>
                        {detectedHeaders.map((h) => (
                          <option key={h} value={h}>{h}</option>
                        ))}
                      </select>
                    ) : (
                      <input type="text" value={value} onChange={(e) => set(e.target.value)}
                        placeholder={required ? "e.g. CU Number" : "Optional column header"}
                        className="w-full px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-900 text-[11px] font-mono focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500" />
                    )}
                  </div>
                ))}
              </div>

              {/* VAT Derivation Toggle */}
              <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg border border-slate-200">
                <label className="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" checked={vatDerivationEnabled} onChange={(e) => setVatDerivationEnabled(e.target.checked)} className="sr-only peer" />
                  <div className="w-9 h-5 bg-slate-300 peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
                <div>
                  <span className="font-semibold text-slate-700 text-xs">Auto-derive VAT rate from Tax Amount</span>
                  <p className="text-[10px] text-slate-400">Calculate rate from (Tax Amount / Base Amount) when VAT column is empty</p>
                </div>
              </div>
            </div>
          </div>

          {/* ── Section 3: Advanced Parsing (Collapsible) ── */}
          <div className="border border-slate-200 rounded-xl overflow-hidden">
            <button type="button" onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center gap-2 text-left cursor-pointer hover:bg-slate-100 transition-colors">
              {showAdvanced ? <ChevronDown className="w-4 h-4 text-slate-500" /> : <ChevronRight className="w-4 h-4 text-slate-500" />}
              <FileCode className="w-4 h-4 text-slate-500" />
              <span className="font-bold text-slate-800 text-xs">Advanced Parsing Rules</span>
              <span className="text-[10px] text-slate-400 ml-1">(header row, date format, delimiter)</span>
            </button>
            {showAdvanced && (
              <div className="p-4 space-y-3">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1 text-[10px] uppercase tracking-wider">Header Row</label>
                    <input type="number" min={1} value={headerRow} onChange={(e) => setHeaderRow(parseInt(e.target.value) || 1)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500" />
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1 text-[10px] uppercase tracking-wider">Data Start Row</label>
                    <input type="number" min={2} value={dataStartRow} onChange={(e) => setDataStartRow(parseInt(e.target.value) || 2)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500" />
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1 text-[10px] uppercase tracking-wider">Date Format</label>
                    <select value={dateFormat} onChange={(e) => setDateFormat(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-800 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-mono font-medium cursor-pointer">
                      <option value="YYYY-MM-DD">YYYY-MM-DD</option>
                      <option value="DD/MM/YYYY">DD/MM/YYYY</option>
                      <option value="MM/DD/YYYY">MM/DD/YYYY</option>
                      <option value="DD-MM-YYYY">DD-MM-YYYY</option>
                      <option value="DD Mon YYYY">DD Mon YYYY (e.g. 01 Jun 2026)</option>
                      <option value="DD-Mon-YYYY">DD-Mon-YYYY (e.g. 01-Jun-2026)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1 text-[10px] uppercase tracking-wider">CSV Delimiter</label>
                    <select value={delimiter} onChange={(e) => setDelimiter(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-800 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-mono font-medium cursor-pointer">
                      <option value=",">Comma (,)</option>
                      <option value=";">Semicolon (;)</option>
                      <option value="\t">Tab</option>
                    </select>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* ── Section 4: Live Preview ── */}
          <div className="border border-slate-200 rounded-xl overflow-hidden">
            <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Play className="w-4 h-4 text-emerald-600" />
                <span className="font-bold text-slate-800 text-xs">Live Dry-Run Preview</span>
              </div>
              <button type="button" onClick={handleRunLivePreview} disabled={previewing || !sampleFile}
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer">
                {previewing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-white" />}
                Execute Test
              </button>
            </div>
            {previewData && (
              <div className="p-4 space-y-3">
                <div className="flex items-center gap-2 text-xs">
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${previewData.is_valid ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-amber-50 text-amber-700 border border-amber-200"}`}>
                    {previewData.is_valid ? "Valid" : "Has Issues"}
                  </span>
                  <span className="text-slate-500">{previewData.total_rows_detected} rows detected</span>
                </div>
                {previewData.general_errors.length > 0 && (
                  <div className="p-2 bg-rose-50 border border-rose-200 rounded-lg text-[11px] text-rose-700">
                    {previewData.general_errors.join("; ")}
                  </div>
                )}
                {previewData.preview_samples.length > 0 && (
                  <div className="overflow-x-auto border border-slate-200 rounded-lg">
                    <table className="w-full text-left text-[11px]">
                      <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase text-[10px]">
                        <tr>
                          <th className="px-3 py-2">Row</th>
                          <th className="px-3 py-2">Invoice No</th>
                          <th className="px-3 py-2">PIN</th>
                          <th className="px-3 py-2">Partner</th>
                          <th className="px-3 py-2">Date</th>
                          <th className="px-3 py-2 text-right">Amount</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 font-mono">
                        {previewData.preview_samples.map((s) => (
                          <tr key={s.row_index} className="hover:bg-slate-50/50">
                            <td className="px-3 py-2 font-sans font-semibold text-slate-400">{s.row_index}</td>
                            <td className="px-3 py-2 font-semibold text-slate-900">{s.mapped_invoice.invoice_number || "-"}</td>
                            <td className="px-3 py-2 text-slate-700">{s.mapped_invoice.pin || "-"}</td>
                            <td className="px-3 py-2 font-sans text-slate-800">{s.mapped_invoice.partner_name || "-"}</td>
                            <td className="px-3 py-2 text-slate-600">{s.mapped_invoice.invoice_date || "-"}</td>
                            <td className="px-3 py-2 text-right font-bold text-slate-900">
                              {s.mapped_invoice.base_amount != null ? s.mapped_invoice.base_amount.toLocaleString() : "-"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        </form>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between bg-slate-50/50 shrink-0">
          <div className="flex items-center gap-2 text-[11px] text-slate-400">
            <Info className="w-3.5 h-3.5 text-blue-500" />
            <span>Profiles use immutable snapshots for reconciliation safety.</span>
          </div>
          <div className="flex items-center gap-3">
            <button type="button" onClick={onClose}
              className="px-4 py-2 text-slate-600 hover:text-slate-900 text-xs font-semibold transition-colors cursor-pointer">
              Cancel
            </button>
            <button type="submit" form="add-edit-import-profile-form" disabled={saving}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#0e1734] hover:bg-[#16224c] active:bg-[#080d21] text-white rounded-lg text-xs font-semibold shadow-xs transition-all duration-150 cursor-pointer disabled:opacity-50">
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              {profileToEdit ? "Update Profile" : "Save Profile"}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}

/* ─── View Import Profile Modal ─────────────────────────────────────────── */

interface ViewModalProps {
  profile: ImportProfile;
  onClose: () => void;
  onEdit: (profile: ImportProfile) => void;
}

function ViewImportProfileModal({ profile, onClose, onEdit }: ViewModalProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);
  if (!mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-2xl overflow-hidden animate-in zoom-in-95 duration-150">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 shrink-0">
              <Eye className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-slate-900 text-sm">{profile.name}</h3>
                {profile.is_builtin ? (
                  <span className="px-2 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 text-[10px] font-bold rounded-full">System Built-in</span>
                ) : (
                  <span className="px-2 py-0.5 bg-slate-100 text-slate-700 border border-slate-200 text-[10px] font-bold rounded-full">Company Custom</span>
                )}
              </div>
              <p className="text-xs text-slate-500">Provider: {profile.provider} &middot; Format: {profile.source_format.toUpperCase()} &middot; v{profile.version}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1 rounded-lg transition-colors cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4 text-xs max-h-[70vh] overflow-y-auto">
          {profile.description && (
            <div className="p-3 bg-slate-50 rounded-lg text-slate-600 border border-slate-200">{profile.description}</div>
          )}

          <div className="space-y-2">
            <h4 className="font-bold text-slate-800 text-[11px] uppercase tracking-wider">Column Mapping</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 font-mono text-[11px]">
              {Object.entries(profile.column_mapping).map(([field, val]) => {
                const mappedVal = Array.isArray(val) ? val[0] : (val ? String(val) : "");
                return (
                  <div key={field} className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                    <div className="font-sans font-semibold text-slate-700 uppercase text-[10px] tracking-wider mb-1">{field.replace(/_/g, " ")}</div>
                    <div>
                      {mappedVal ? (
                        <span className="px-2 py-0.5 bg-white border border-slate-300 rounded text-slate-800 text-[11px] font-semibold">{mappedVal}</span>
                      ) : <span className="text-slate-400 font-sans italic text-[10px]">Unmapped</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="space-y-2 pt-2 border-t border-slate-100">
            <h4 className="font-bold text-slate-800 text-[11px] uppercase tracking-wider">Parsing Rules</h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-[11px]">
              <div className="p-2 bg-slate-50 rounded border border-slate-200">
                <span className="font-sans text-[10px] text-slate-400 block">Header Row</span>
                <span className="font-bold text-slate-800">{profile.parsing_hints.header_row}</span>
              </div>
              <div className="p-2 bg-slate-50 rounded border border-slate-200">
                <span className="font-sans text-[10px] text-slate-400 block">Data Start</span>
                <span className="font-bold text-slate-800">{profile.parsing_hints.data_start_row}</span>
              </div>
              <div className="p-2 bg-slate-50 rounded border border-slate-200">
                <span className="font-sans text-[10px] text-slate-400 block">Date Format</span>
                <span className="font-bold text-slate-800">{profile.parsing_hints.date_format}</span>
              </div>
              <div className="p-2 bg-slate-50 rounded border border-slate-200">
                <span className="font-sans text-[10px] text-slate-400 block">Delimiter</span>
                <span className="font-bold text-slate-800">{profile.parsing_hints.delimiter || ","}</span>
              </div>
            </div>
          </div>

          {profile.validation_rules.vat_derivation_enabled && (
            <div className="flex items-center gap-2 p-2 bg-blue-50 border border-blue-200 rounded-lg text-[11px] text-blue-700">
              <Sparkles className="w-3.5 h-3.5" />
              VAT auto-derivation is enabled (computes rate from Tax Amount / Base Amount)
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between bg-slate-50/50">
          <button onClick={onClose} className="px-4 py-2 text-slate-600 hover:text-slate-900 font-semibold text-xs cursor-pointer">Close</button>
          <button onClick={() => { onClose(); onEdit(profile); }}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold text-xs cursor-pointer transition-colors">
            <Pencil className="w-4 h-4" />Edit Profile
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

/* ─── Main Component ────────────────────────────────────────────────────── */

export function ERPImportProfilesCard({ selectedCompanyId }: ERPImportProfilesCardProps) {
  const { notify } = useToast();
  const [profiles, setProfiles] = useState<ImportProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeModuleFilter, setActiveModuleFilter] = useState<"all" | "sales" | "purchases">("all");

  // Modals
  const [showAddEditModal, setShowAddEditModal] = useState(false);
  const [editingProfile, setEditingProfile] = useState<ImportProfile | null>(null);
  const [showViewModal, setShowViewModal] = useState(false);
  const [viewingProfile, setViewingProfile] = useState<ImportProfile | null>(null);

  // Confirm modal
  const [confirmModal, setConfirmModal] = useState<{
    open: boolean;
    title: string;
    message: string;
    confirmLabel: string;
    variant?: "danger" | "warning" | "default";
    onConfirm: () => void;
  }>({ open: false, title: "", message: "", confirmLabel: "", onConfirm: () => {} });
  const [confirmLoading, setConfirmLoading] = useState(false);

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
      notify(err instanceof Error ? err.message : "Failed to load profiles.", "error");
    } finally { setLoading(false); }
  }, [activeModuleFilter, notify]);

  useEffect(() => { loadProfiles(); }, [loadProfiles]);

  const handleSetDefault = async (id: number) => {
    setActionProfileId(id);
    try {
      const res = await fetchWithAuth(`/import-profiles/${id}/set-default`, { method: "POST" });
      if (!res.ok) throw new Error("Failed to set default.");
      notify("Default profile updated.", "success");
      loadProfiles();
    } catch (err: unknown) {
      notify(err instanceof Error ? err.message : "Error setting default.", "error");
    } finally { setActionProfileId(null); }
  };

  const handleClone = async (id: number, name: string): Promise<ImportProfile | null> => {
    setActionProfileId(id);
    try {
      const res = await fetchWithAuth(`/import-profiles/${id}/clone?name=${encodeURIComponent(`${name} (Custom)`)}`, { method: "POST" });
      if (!res.ok) throw new Error("Failed to clone profile.");
      notify("Profile cloned successfully.", "success");
      loadProfiles();
      return await res.json();
    } catch (err: unknown) {
      notify(err instanceof Error ? err.message : "Error cloning.", "error");
      return null;
    } finally { setActionProfileId(null); }
  };

  const handleCloneAndEdit = async (profile: ImportProfile) => {
    const cloned = await handleClone(profile.id, profile.name);
    if (cloned) {
      setEditingProfile(cloned);
      setShowAddEditModal(true);
    }
  };

  const handleDelete = async (id: number) => {
    setConfirmModal({
      open: true,
      title: "Delete Import Profile",
      message: "This will permanently delete this profile. This action cannot be undone.",
      confirmLabel: "Delete Permanently",
      variant: "danger",
      onConfirm: async () => {
        setConfirmLoading(true);
        try {
          const res = await fetchWithAuth(`/import-profiles/${id}`, { method: "DELETE" });
          if (!res.ok) throw new Error("Failed to delete profile.");
          notify("Profile deleted permanently.", "success");
          loadProfiles();
        } catch (err: unknown) {
          notify(err instanceof Error ? err.message : "Error deleting profile.", "error");
        } finally {
          setConfirmLoading(false);
          setConfirmModal((prev) => ({ ...prev, open: false }));
        }
      },
    });
  };

  const openSetDefaultConfirm = (p: ImportProfile) => {
    setConfirmModal({
      open: true,
      title: "Set Default Profile",
      message: `Set "${p.name}" as the default profile for ${p.module}? This will replace any existing default for this module.`,
      confirmLabel: "Set as Default",
      variant: "default",
      onConfirm: async () => {
        setConfirmLoading(true);
        await handleSetDefault(p.id);
        setConfirmLoading(false);
        setConfirmModal((prev) => ({ ...prev, open: false }));
      },
    });
  };

  return (
    <>
      {showAddEditModal && (
        <AddEditImportProfileModal
          profileToEdit={editingProfile}
          onClose={() => { setShowAddEditModal(false); setEditingProfile(null); }}
          onSaved={loadProfiles}
        />
      )}

      {showViewModal && viewingProfile && (
        <ViewImportProfileModal
          profile={viewingProfile}
          onClose={() => { setShowViewModal(false); setViewingProfile(null); }}
          onEdit={(p) => { setEditingProfile(p); setShowAddEditModal(true); }}
        />
      )}

      {confirmModal.open && (
        <ConfirmModal
          title={confirmModal.title}
          message={confirmModal.message}
          confirmLabel={confirmModal.confirmLabel}
          variant={confirmModal.variant}
          loading={confirmLoading}
          onConfirm={confirmModal.onConfirm}
          onClose={() => { setConfirmModal((prev) => ({ ...prev, open: false })); setConfirmLoading(false); }}
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
              Column mappings, header auto-detection, and dry-run preview for Zoho, QuickBooks, Xero & custom exports.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="inline-flex p-1 bg-slate-100 rounded-lg text-xs font-semibold">
              {(["all", "sales", "purchases"] as const).map((f) => (
                <button key={f} onClick={() => setActiveModuleFilter(f)}
                  className={`px-3 py-1 rounded-md transition-colors cursor-pointer capitalize ${activeModuleFilter === f ? "bg-white text-slate-900 shadow-xs" : "text-slate-500 hover:text-slate-800"}`}>
                  {f}
                </button>
              ))}
            </div>

            <button onClick={() => { setEditingProfile(null); setShowAddEditModal(true); }}
              className="inline-flex items-center gap-1.5 px-3 py-2 bg-[#0e1734] hover:bg-[#16224c] text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer">
              <Plus className="w-4 h-4" />Add Profile
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="p-6">
          {loading ? (
            <div className="flex items-center justify-center py-12 gap-2 text-slate-400 text-xs">
              <Loader2 className="w-5 h-5 animate-spin text-blue-600" />Loading profiles...
            </div>
          ) : profiles.length === 0 ? (
            <div className="text-center py-12 text-slate-400 text-xs space-y-2">
              <FileCode className="w-8 h-8 mx-auto text-slate-300" />
              <p>No profiles found for this filter.</p>
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
                      <td className="px-4 py-3">
                        <div className="font-semibold text-slate-900">{p.name}</div>
                        {p.description && <div className="text-[11px] font-normal text-slate-400 mt-0.5">{p.description}</div>}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${p.module === "sales" ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-purple-50 text-purple-700 border border-purple-200"}`}>
                          {p.module}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 bg-slate-100 rounded-md border border-slate-200 text-[10px] font-bold font-mono">{p.provider}</span>
                      </td>
                      <td className="px-4 py-3">
                        {p.is_builtin ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-blue-600">
                            <Database className="w-3 h-3" />System
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-600">
                            <Sliders className="w-3 h-3" />Custom
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-500 uppercase">{p.source_format}</td>
                      <td className="px-4 py-3 text-center">
                        {p.is_default ? (
                          <span className="inline-flex items-center gap-1 text-amber-600 font-semibold text-[11px]">
                            <Star className="w-3.5 h-3.5 fill-amber-400" />Default
                          </span>
                        ) : (
                          <button onClick={() => openSetDefaultConfirm(p)} disabled={actionProfileId === p.id}
                            className="inline-flex items-center gap-1 px-2 py-1 text-slate-400 hover:text-amber-600 hover:bg-amber-50 rounded-md text-[11px] font-semibold transition-colors cursor-pointer disabled:opacity-50">
                            <Star className="w-3 h-3" />Set Default
                          </button>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="inline-flex items-center gap-0.5">
                          <button onClick={() => { setViewingProfile(p); setShowViewModal(true); }}
                            title="View Details" className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-md transition-colors cursor-pointer">
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                          <button onClick={() => { setEditingProfile(p); setShowAddEditModal(true); }}
                            title="Edit" className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors cursor-pointer">
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button onClick={() => handleDelete(p.id)} disabled={actionProfileId === p.id}
                            title="Delete" className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors cursor-pointer disabled:opacity-50">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
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
