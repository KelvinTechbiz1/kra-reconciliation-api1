"use client";

import { useEffect, useState, useCallback } from "react";
import { createPortal } from "react-dom";
import {
  ImportProfile,
  ImportProfileCreate,
  MappingPreviewResponse,
  ReconciliationType,
  SourceFormat,
} from "@/types/import_profile";
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
  Pencil,
  Eye,
  Upload,
  Play,
  Sparkles,
  AlertCircle,
  Tag,
  Check,
} from "lucide-react";

interface ERPImportProfilesCardProps {
  selectedCompanyId?: number | null;
}

interface AddEditModalProps {
  profileToEdit?: ImportProfile | null;
  onClose: () => void;
  onSaved: () => void;
}

function AddEditImportProfileModal({ profileToEdit, onClose, onSaved }: AddEditModalProps) {
  const [mounted, setMounted] = useState(false);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<"mapping" | "hints" | "preview">("mapping");

  // Form State
  const [formName, setFormName] = useState(profileToEdit?.name || "");
  const [formModule, setFormModule] = useState<ReconciliationType>(profileToEdit?.module || "sales");
  const [formProvider, setFormProvider] = useState(profileToEdit?.provider || "ZOHO");
  const [formDescription, setFormDescription] = useState(profileToEdit?.description || "");
  const [formFormat, setFormFormat] = useState<SourceFormat>(profileToEdit?.source_format || "csv");
  const [isDefault, setIsDefault] = useState(profileToEdit?.is_default || false);

  // Column Mappings (Comma Separated Strings)
  const [pinAlias, setPinAlias] = useState(profileToEdit?.column_mapping.pin.join(", ") || "Customer PIN, Tax Number, PIN");
  const [partnerAlias, setPartnerAlias] = useState(profileToEdit?.column_mapping.partner_name.join(", ") || "Customer Name, Client Name, Vendor");
  const [invNumAlias, setInvNumAlias] = useState(profileToEdit?.column_mapping.invoice_number.join(", ") || "Invoice Number, Invoice No, DocNum");
  const [invDateAlias, setInvDateAlias] = useState(profileToEdit?.column_mapping.invoice_date.join(", ") || "Invoice Date, Date");
  const [cuNumAlias, setCuNumAlias] = useState(profileToEdit?.column_mapping.cu_number.join(", ") || "CU Number, ETR Number, Control Unit No");
  const [vatGroupAlias, setVatGroupAlias] = useState(profileToEdit?.column_mapping.vat_group.join(", ") || "Tax Rate, VAT Code, VAT Group");
  const [baseAmtAlias, setBaseAmtAlias] = useState(profileToEdit?.column_mapping.base_amount.join(", ") || "SubTotal, Taxable Amount, Base Amount");

  // Active Focused Alias Input for Auto-Assigning Detected Headers
  const [activeAliasField, setActiveAliasField] = useState<"pin" | "partner" | "invNum" | "invDate" | "cuNum" | "vatGroup" | "baseAmt">("pin");

  // Configurable Parsing Hints State
  const [headerRow, setHeaderRow] = useState(profileToEdit?.parsing_hints.header_row || 1);
  const [dataStartRow, setDataStartRow] = useState(profileToEdit?.parsing_hints.data_start_row || 2);
  const [dateFormat, setDateFormat] = useState(profileToEdit?.parsing_hints.date_format || "YYYY-MM-DD");
  const [delimiter, setDelimiter] = useState(profileToEdit?.parsing_hints.delimiter || ",");

  // Sample File Header Auto-Detection & Dry-Run Preview State
  const [sampleFile, setSampleFile] = useState<File | null>(null);
  const [detectedHeaders, setDetectedHeaders] = useState<string[]>([]);
  const [previewing, setPreviewing] = useState(false);
  const [previewData, setPreviewData] = useState<MappingPreviewResponse | null>(null);

  const { notify } = useToast();

  useEffect(() => {
    setMounted(true);
  }, []);

  // Parse header text from uploaded sample file
  const handleSampleFileUpload = (file: File) => {
    setSampleFile(file);
    setPreviewData(null);

    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      if (!text) return;

      const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0);
      const targetHeaderLine = lines[Math.max(0, headerRow - 1)];

      if (targetHeaderLine) {
        // Detect split by delimiter or comma
        const sep = delimiter || ",";
        const headers = targetHeaderLine
          .split(sep)
          .map((h) => h.replace(/^["']|["']$/g, "").trim())
          .filter(Boolean);

        setDetectedHeaders(headers);
        notify(`Auto-detected ${headers.length} headers from sample file.`, "success");
      }
    };
    reader.readAsText(file);
  };

  // Helper to append a detected header tag to the active alias input
  const addHeaderToField = (headerName: string) => {
    const appendVal = (current: string) => {
      const parts = current.split(",").map((x) => x.trim()).filter(Boolean);
      if (parts.includes(headerName)) return current;
      return parts.length > 0 ? `${current}, ${headerName}` : headerName;
    };

    switch (activeAliasField) {
      case "pin": setPinAlias((c) => appendVal(c)); break;
      case "partner": setPartnerAlias((c) => appendVal(c)); break;
      case "invNum": setInvNumAlias((c) => appendVal(c)); break;
      case "invDate": setInvDateAlias((c) => appendVal(c)); break;
      case "cuNum": setCuNumAlias((c) => appendVal(c)); break;
      case "vatGroup": setVatGroupAlias((c) => appendVal(c)); break;
      case "baseAmt": setBaseAmtAlias((c) => appendVal(c)); break;
    }
  };

  // Live dry-run preview call
  const handleRunLivePreview = async () => {
    if (!sampleFile) {
      notify("Please select a sample CSV/XLSX file to run dry-run preview.", "error");
      return;
    }

    setPreviewing(true);
    try {
      const formData = new FormData();
      formData.append("file", sampleFile);

      const res = await fetchWithAuth(`/import-profiles/preview?module=${formModule}`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Preview failed.");
      }

      const data: MappingPreviewResponse = await res.json();
      setPreviewData(data);
      if (data.detected_headers.length > 0) {
        setDetectedHeaders(data.detected_headers);
      }
      notify(`Preview generated: ${data.total_rows_detected} rows detected.`, "success");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error executing preview.";
      notify(msg, "error");
    } finally {
      setPreviewing(false);
    }
  };

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
        header_row: Number(headerRow),
        data_start_row: Number(dataStartRow),
        delimiter: delimiter || ",",
        date_format: dateFormat || "YYYY-MM-DD",
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

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to save profile.");
      }

      notify(
        profileToEdit
          ? "Import profile updated successfully!"
          : "Custom import profile created successfully!",
        "success"
      );
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
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-3xl max-h-[92vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-150">
        {/* Fixed Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 shrink-0">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-sm">
                {profileToEdit ? `Edit Import Profile (${profileToEdit.name})` : "Add Custom Import Profile"}
              </h3>
              <p className="text-xs text-slate-500">Configure canonical column header mappers, parsing options & dry-run test</p>
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

        {/* Tab Selection */}
        <div className="px-6 border-b border-slate-100 bg-slate-50/30 flex items-center gap-4 text-xs font-semibold text-slate-500">
          <button
            type="button"
            onClick={() => setActiveTab("mapping")}
            className={`py-3 border-b-2 transition-colors flex items-center gap-1.5 cursor-pointer ${activeTab === "mapping" ? "border-blue-600 text-blue-600 font-bold" : "border-transparent hover:text-slate-800"
              }`}
          >
            <Sliders className="w-3.5 h-3.5" /> Column Mappings
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("hints")}
            className={`py-3 border-b-2 transition-colors flex items-center gap-1.5 cursor-pointer ${activeTab === "hints" ? "border-blue-600 text-blue-600 font-bold" : "border-transparent hover:text-slate-800"
              }`}
          >
            <FileCode className="w-3.5 h-3.5" /> File Parsing Rules
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("preview")}
            className={`py-3 border-b-2 transition-colors flex items-center gap-1.5 cursor-pointer ${activeTab === "preview" ? "border-blue-600 text-blue-600 font-bold" : "border-transparent hover:text-slate-800"
              }`}
          >
            <Play className="w-3.5 h-3.5 text-emerald-600" /> Live Dry-Run Preview
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSaveProfile} id="add-edit-import-profile-form" className="flex-1 overflow-y-auto p-6 space-y-4 text-xs">
          {/* Core Profile Attributes */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block font-semibold text-slate-700 mb-1 uppercase tracking-wider text-[10px]">
                Profile Name *
              </label>
              <input
                type="text"
                required
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="e.g. Zoho Books - Sales Custom"
                className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 mb-1 uppercase tracking-wider text-[10px]">
                Module *
              </label>
              <select
                value={formModule}
                onChange={(e) => setFormModule(e.target.value as ReconciliationType)}
                className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-800 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium cursor-pointer"
              >
                <option value="sales">Sales</option>
                <option value="purchases">Purchases</option>
              </select>
            </div>
            <div>
              <label className="block font-semibold text-slate-700 mb-1 uppercase tracking-wider text-[10px]">
                Provider Label
              </label>
              <input
                type="text"
                value={formProvider}
                onChange={(e) => setFormProvider(e.target.value)}
                placeholder="ZOHO, QUICKBOOKS, XERO, CUSTOM"
                className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium"
              />
            </div>
          </div>

          {activeTab === "mapping" && (
            <>
              {/* Sample File Drag & Auto-Detection Card */}
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-blue-600" />
                    <h4 className="font-bold text-slate-900 text-xs">
                      Auto-Detect Column Headers from Sample File
                    </h4>
                  </div>
                  <label className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer shadow-2xs transition-colors">
                    <Upload className="w-3.5 h-3.5 text-blue-600" />
                    {sampleFile ? sampleFile.name : "Upload Sample File"}
                    <input
                      type="file"
                      accept=".csv,.xlsx"
                      className="hidden"
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          handleSampleFileUpload(e.target.files[0]);
                        }
                      }}
                    />
                  </label>
                </div>

                {detectedHeaders.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-[11px] text-slate-500">
                      <span>Click any header tag below to assign to active input field: <strong className="text-blue-700 uppercase font-mono">[{activeAliasField}]</strong></span>
                      <span className="font-semibold text-emerald-700">{detectedHeaders.length} headers found</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto p-2 bg-white rounded-lg border border-slate-200">
                      {detectedHeaders.map((h) => (
                        <button
                          key={h}
                          type="button"
                          onClick={() => addHeaderToField(h)}
                          className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 rounded-md font-mono text-[10px] font-semibold transition-colors cursor-pointer"
                        >
                          <Tag className="w-2.5 h-2.5" />
                          {h}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Column Mapping Inputs */}
              <div className="space-y-3 font-mono text-[11px]">
                <div onFocus={() => setActiveAliasField("pin")}>
                  <label className="flex items-center justify-between font-semibold text-slate-700 mb-1">
                    <span>PIN Column Aliases *</span>
                    {activeAliasField === "pin" && <span className="text-[10px] text-blue-600 font-sans">Active Field</span>}
                  </label>
                  <input
                    type="text"
                    required
                    value={pinAlias}
                    onChange={(e) => setPinAlias(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  />
                </div>

                <div onFocus={() => setActiveAliasField("invNum")}>
                  <label className="flex items-center justify-between font-semibold text-slate-700 mb-1">
                    <span>Invoice Number Aliases *</span>
                    {activeAliasField === "invNum" && <span className="text-[10px] text-blue-600 font-sans">Active Field</span>}
                  </label>
                  <input
                    type="text"
                    required
                    value={invNumAlias}
                    onChange={(e) => setInvNumAlias(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  />
                </div>

                <div onFocus={() => setActiveAliasField("baseAmt")}>
                  <label className="flex items-center justify-between font-semibold text-slate-700 mb-1">
                    <span>Base Taxable Amount Aliases *</span>
                    {activeAliasField === "baseAmt" && <span className="text-[10px] text-blue-600 font-sans">Active Field</span>}
                  </label>
                  <input
                    type="text"
                    required
                    value={baseAmtAlias}
                    onChange={(e) => setBaseAmtAlias(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  />
                </div>

                <div onFocus={() => setActiveAliasField("partner")}>
                  <label className="flex items-center justify-between font-semibold text-slate-700 mb-1">
                    <span>Partner / Customer Name Aliases</span>
                    {activeAliasField === "partner" && <span className="text-[10px] text-blue-600 font-sans">Active Field</span>}
                  </label>
                  <input
                    type="text"
                    value={partnerAlias}
                    onChange={(e) => setPartnerAlias(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  />
                </div>

                <div onFocus={() => setActiveAliasField("invDate")}>
                  <label className="flex items-center justify-between font-semibold text-slate-700 mb-1">
                    <span>Invoice Date Aliases</span>
                    {activeAliasField === "invDate" && <span className="text-[10px] text-blue-600 font-sans">Active Field</span>}
                  </label>
                  <input
                    type="text"
                    value={invDateAlias}
                    onChange={(e) => setInvDateAlias(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  />
                </div>

                <div onFocus={() => setActiveAliasField("cuNum")}>
                  <label className="flex items-center justify-between font-semibold text-slate-700 mb-1">
                    <span>CU / ETR Control Unit Number Aliases</span>
                    {activeAliasField === "cuNum" && <span className="text-[10px] text-blue-600 font-sans">Active Field</span>}
                  </label>
                  <input
                    type="text"
                    value={cuNumAlias}
                    onChange={(e) => setCuNumAlias(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  />
                </div>

                <div onFocus={() => setActiveAliasField("vatGroup")}>
                  <label className="flex items-center justify-between font-semibold text-slate-700 mb-1">
                    <span>VAT Group / Tax Rate Aliases</span>
                    {activeAliasField === "vatGroup" && <span className="text-[10px] text-blue-600 font-sans">Active Field</span>}
                  </label>
                  <input
                    type="text"
                    value={vatGroupAlias}
                    onChange={(e) => setVatGroupAlias(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  />
                </div>
              </div>
            </>
          )}

          {activeTab === "hints" && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1 uppercase tracking-wider text-[10px]">
                    Header Row Line Number
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={headerRow}
                    onChange={(e) => setHeaderRow(parseInt(e.target.value) || 1)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  />
                  <p className="text-[10px] text-slate-400 mt-1">
                    Default: 1. Adjust if your export includes title headers on top lines.
                  </p>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1 uppercase tracking-wider text-[10px]">
                    Data Start Row Line Number
                  </label>
                  <input
                    type="number"
                    min={2}
                    value={dataStartRow}
                    onChange={(e) => setDataStartRow(parseInt(e.target.value) || 2)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1 uppercase tracking-wider text-[10px]">
                    Date Format Hint
                  </label>
                  <select
                    value={dateFormat}
                    onChange={(e) => setDateFormat(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-800 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-mono font-medium cursor-pointer"
                  >
                    <option value="YYYY-MM-DD">YYYY-MM-DD (e.g. 2026-01-15)</option>
                    <option value="DD/MM/YYYY">DD/MM/YYYY (e.g. 15/01/2026)</option>
                    <option value="MM/DD/YYYY">MM/DD/YYYY (e.g. 01/15/2026)</option>
                    <option value="DD-MM-YYYY">DD-MM-YYYY (e.g. 15-01-2026)</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1 uppercase tracking-wider text-[10px]">
                    CSV Delimiter
                  </label>
                  <select
                    value={delimiter}
                    onChange={(e) => setDelimiter(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-800 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-mono font-medium cursor-pointer"
                  >
                    <option value=",">Comma (,)</option>
                    <option value=";">Semicolon (;)</option>
                    <option value="\t">Tab (\t)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1 uppercase tracking-wider text-[10px]">
                  Description (Optional Notes)
                </label>
                <input
                  type="text"
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  placeholder="Notes on export parameters or ERP version"
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-900 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
              </div>

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="is-default-checkbox"
                  checked={isDefault}
                  onChange={(e) => setIsDefault(e.target.checked)}
                  className="w-4 h-4 text-blue-600 rounded-md border-slate-300 focus:ring-blue-500 cursor-pointer"
                />
                <label htmlFor="is-default-checkbox" className="font-semibold text-slate-700 text-xs cursor-pointer">
                  Set as default import profile for {formModule.toUpperCase()} module
                </label>
              </div>
            </div>
          )}

          {activeTab === "preview" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between bg-slate-50 border border-slate-200 p-4 rounded-xl">
                <div>
                  <h4 className="font-bold text-slate-900 text-xs">Run Dry-Run Mapping Preview</h4>
                  <p className="text-[11px] text-slate-500">
                    {sampleFile
                      ? `Ready to preview with ${sampleFile.name}`
                      : "Upload a sample CSV/XLSX file to execute a live parsing test."}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleRunLivePreview}
                  disabled={previewing || !sampleFile}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                >
                  {previewing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-white" />}
                  Execute Live Test
                </button>
              </div>

              {previewData && (
                <div className="border border-slate-200 rounded-xl p-4 space-y-3 bg-white">
                  <div className="flex items-center justify-between text-xs border-b border-slate-100 pb-2">
                    <span className="font-bold text-slate-800">Preview Results ({previewData.filename})</span>
                    <span className={`font-semibold px-2 py-0.5 rounded-full text-[10px] ${previewData.is_valid ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-amber-50 text-amber-700 border border-amber-200"}`}>
                      {previewData.total_rows_detected} Total Rows Detected
                    </span>
                  </div>

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
                            <th className="px-3 py-2 text-right">Base Amount</th>
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
          )}
        </form>

        {/* Fixed Footer */}
        <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between bg-slate-50/50 shrink-0">
          <div className="flex items-center gap-2 text-[11px] text-slate-400">
            <Info className="w-3.5 h-3.5 text-blue-500" />
            <span>Profiles use immutable snapshotting for reconciliation safety.</span>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-slate-600 hover:text-slate-900 text-xs font-semibold transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              form="add-edit-import-profile-form"
              disabled={saving}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#0e1734] hover:bg-[#16224c] active:bg-[#080d21] text-white rounded-lg text-xs font-semibold shadow-xs transition-all duration-150 cursor-pointer disabled:opacity-50"
            >
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              {profileToEdit ? "Update Import Profile" : "Save Import Profile"}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}

interface ViewModalProps {
  profile: ImportProfile;
  onClose: () => void;
  onClone: () => void;
}

function ViewImportProfileModal({ profile, onClose, onClone }: ViewModalProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-2xl overflow-hidden animate-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 shrink-0">
              <Eye className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-slate-900 text-sm">{profile.name}</h3>
                {profile.is_builtin ? (
                  <span className="px-2 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 text-[10px] font-bold rounded-full">
                    System Built-in
                  </span>
                ) : (
                  <span className="px-2 py-0.5 bg-slate-100 text-slate-700 border border-slate-200 text-[10px] font-bold rounded-full">
                    Company Custom
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500">Provider: {profile.provider} · Format: {profile.source_format.toUpperCase()} · v{profile.version}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1 rounded-lg transition-colors cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4 text-xs max-h-[75vh] overflow-y-auto">
          {profile.description && (
            <div className="p-3 bg-slate-50 rounded-lg text-slate-600 border border-slate-200">
              {profile.description}
            </div>
          )}

          <div className="space-y-2">
            <h4 className="font-bold text-slate-800 text-xs uppercase tracking-wider text-[11px]">
              Column Mapping Rules
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 font-mono text-[11px]">
              {(Object.entries(profile.column_mapping) as [string, string[]][]).map(([field, aliases]: [string, string[]]) => (
                <div key={field} className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                  <div className="font-sans font-semibold text-slate-700 uppercase text-[10px] tracking-wider mb-1">
                    {field.replace("_", " ")}
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {aliases.length > 0 ? (
                      aliases.map((a: string) => (
                        <span key={a} className="px-1.5 py-0.5 bg-white border border-slate-300 rounded text-slate-800 text-[10px]">
                          {a}
                        </span>
                      ))
                    ) : (

                      <span className="text-slate-400 font-sans italic text-[10px]">None defined</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-2 pt-2 border-t border-slate-100">
            <h4 className="font-bold text-slate-800 text-xs uppercase tracking-wider text-[11px]">
              Parsing Parameters
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-[11px]">
              <div className="p-2 bg-slate-50 rounded border border-slate-200">
                <span className="font-sans text-[10px] text-slate-400 block">Header Row</span>
                <span className="font-bold text-slate-800">{profile.parsing_hints.header_row}</span>
              </div>
              <div className="p-2 bg-slate-50 rounded border border-slate-200">
                <span className="font-sans text-[10px] text-slate-400 block">Data Start Row</span>
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
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between bg-slate-50/50">
          <button onClick={onClose} className="px-4 py-2 text-slate-600 hover:text-slate-900 font-semibold text-xs cursor-pointer">
            Close
          </button>

          <button
            onClick={() => {
              onClose();
              onClone();
            }}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold text-xs cursor-pointer transition-colors"
          >
            <Copy className="w-4 h-4" />
            Clone as Company Profile
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

  // Modal State
  const [showAddEditModal, setShowAddEditModal] = useState(false);
  const [editingProfile, setEditingProfile] = useState<ImportProfile | null>(null);

  const [showViewModal, setShowViewModal] = useState(false);
  const [viewingProfile, setViewingProfile] = useState<ImportProfile | null>(null);

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
      {showAddEditModal && (
        <AddEditImportProfileModal
          profileToEdit={editingProfile}
          onClose={() => {
            setShowAddEditModal(false);
            setEditingProfile(null);
          }}
          onSaved={loadProfiles}
        />
      )}

      {showViewModal && viewingProfile && (
        <ViewImportProfileModal
          profile={viewingProfile}
          onClose={() => {
            setShowViewModal(false);
            setViewingProfile(null);
          }}
          onClone={() => handleClone(viewingProfile.id, viewingProfile.name)}
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
              Configurable column mappings, header auto-detection, and dry-run preview for Zoho, QuickBooks, Xero & custom exports.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Module Filter */}
            <div className="inline-flex p-1 bg-slate-100 rounded-lg text-xs font-semibold">
              <button
                onClick={() => setActiveModuleFilter("all")}
                className={`px-3 py-1 rounded-md transition-colors cursor-pointer ${activeModuleFilter === "all" ? "bg-white text-slate-900 shadow-xs" : "text-slate-500 hover:text-slate-800"}`}
              >
                All
              </button>
              <button
                onClick={() => setActiveModuleFilter("sales")}
                className={`px-3 py-1 rounded-md transition-colors cursor-pointer ${activeModuleFilter === "sales" ? "bg-white text-slate-900 shadow-xs" : "text-slate-500 hover:text-slate-800"}`}
              >
                Sales
              </button>
              <button
                onClick={() => setActiveModuleFilter("purchases")}
                className={`px-3 py-1 rounded-md transition-colors cursor-pointer ${activeModuleFilter === "purchases" ? "bg-white text-slate-900 shadow-xs" : "text-slate-500 hover:text-slate-800"}`}
              >
                Purchases
              </button>
            </div>

            <button
              onClick={() => {
                setEditingProfile(null);
                setShowAddEditModal(true);
              }}
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
                      <td className="px-4 py-3 text-right space-x-1">
                        {/* View Rules Modal Action */}
                        <button
                          onClick={() => {
                            setViewingProfile(p);
                            setShowViewModal(true);
                          }}
                          title="View Profile Details &  Mappings"
                          className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-md transition-colors cursor-pointer"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>

                        {/* Edit Action (For Custom Profiles) */}
                        {!p.is_builtin && (
                          <button
                            onClick={() => {
                              setEditingProfile(p);
                              setShowAddEditModal(true);
                            }}
                            title="Edit Custom Profile"
                            className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors cursor-pointer"
                          >
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {/* Clone Action */}
                        <button
                          onClick={() => handleClone(p.id, p.name)}
                          disabled={actionProfileId === p.id}
                          title="Clone as Company Custom Profile"
                          className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors cursor-pointer"
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>

                        {/* Archive Action */}
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
