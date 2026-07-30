"use client";

import { useState, useEffect } from "react";
import { VATMappingItem, VatModule } from "@/types/settings";
import { fetchWithAuth } from "@/lib/api";
import { getApiErrorMessage } from "@/lib/errors";
import { useToast } from "@/components/ToastProvider";
import {
  Plus,
  Save,
  Loader2,
  Tag,
  ShoppingBag,
  ShoppingCart,
} from "lucide-react";

interface VATMappingEditorProps {
  connectionId: number | null;
  mappings: VATMappingItem[];
  selectedCompanyId?: number | null;
  onSaved: () => void;
}

export function VATMappingEditor({ connectionId, mappings: initialMappings, selectedCompanyId, onSaved }: VATMappingEditorProps) {
  const [mappings, setMappings] = useState<VATMappingItem[]>(initialMappings);
  const [activeModule, setActiveModule] = useState<VatModule>("purchases");

  useEffect(() => {
    setMappings(initialMappings);
  }, [initialMappings]);

  const [saving, setSaving] = useState(false);
  const { notify } = useToast();

  // New Code Form State
  const [newCode, setNewCode] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newCategory, setNewCategory] = useState<string>("16");

  const filteredMappings = mappings.filter((m) => m.module === activeModule);

  const handleCategoryChange = (index: number, newCategory: string) => {
    const updated = [...mappings];
    const target = filteredMappings[index];
    const targetIdx = mappings.findIndex(
      (m) => m.module === target.module && m.sap_code.toUpperCase() === target.sap_code.toUpperCase()
    );
    if (targetIdx !== -1) {
      updated[targetIdx].canonical_rate = newCategory;
      setMappings(updated);
    }
  };

  const handleDescriptionChange = (index: number, newDesc: string) => {
    const updated = [...mappings];
    const target = filteredMappings[index];
    const targetIdx = mappings.findIndex(
      (m) => m.module === target.module && m.sap_code.toUpperCase() === target.sap_code.toUpperCase()
    );
    if (targetIdx !== -1) {
      updated[targetIdx].description = newDesc;
      setMappings(updated);
    }
  };

  const handleAddCustomCode = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCode.trim()) return;

    const codeUpper = newCode.trim().toUpperCase();
    const exists = mappings.some((m) => m.module === activeModule && m.sap_code.toUpperCase() === codeUpper);
    if (exists) {
      notify(`Tax code '${codeUpper}' already exists in ${activeModule}.`, "error");
      return;
    }

    setMappings([
      ...mappings,
      {
        module: activeModule,
        sap_code: codeUpper,
        description: newDescription.trim() || `${codeUpper} Custom Tax Group`,
        canonical_rate: newCategory,
        is_builtin: false,
      },
    ]);

    setNewCode("");
    setNewDescription("");
    setNewCategory("16");
  };

  const handleSaveMappings = async () => {
    setSaving(true);

    try {
      const payload = {
        connection_id: connectionId || undefined,
        mappings: mappings.map((m) => ({
          module: m.module,
          sap_code: m.sap_code,
          description: m.description,
          canonical_rate: m.canonical_rate,
          is_builtin: m.is_builtin,
        })),
      };

      const url = `/settings/vat-mappings${selectedCompanyId ? `?company_id=${selectedCompanyId}` : ""}`;
      const res = await fetchWithAuth(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(getApiErrorMessage(errData, "Failed to update tax code mappings."));
      }

      notify("VAT tax code mappings updated successfully!", "success");
      onSaved();
    } catch (err: unknown) {
      const msg = getApiErrorMessage(err, "An error occurred while saving VAT mappings.");
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
            <Tag className="w-5 h-5 text-slate-500" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900">
              SAP VAT Mapping
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Link ERP tax codes (e.g. O1, I1) to canonical rates (16%, 8%, Zero Rated, Exempt).
            </p>
          </div>
        </div>
      </div>

      {/* Reusable Datalist for VAT Rates */}
      <datalist id="vat-rates-list">
        <option value="16">16% (Standard Rate)</option>
        <option value="12">12% (New Policy)</option>
        <option value="8">8% (Reduced Rate)</option>
        <option value="0">0% (Zero Rated)</option>
        <option value="EXEMPT">Exempt (Tax Free)</option>
      </datalist>

      <div className="p-6 space-y-6">
        {/* Module Segment Selector Tabs */}
        <div className="flex bg-slate-100 p-1.5 gap-1.5 rounded-lg border border-slate-200/60 max-w-md">
          <button
            type="button"
            onClick={() => setActiveModule("purchases")}
            aria-pressed={activeModule === "purchases"}
            className={`flex-1 py-2 rounded-md text-xs font-bold flex items-center justify-center gap-2 transition-colors cursor-pointer border ${activeModule === "purchases"
              ? "bg-white text-[#0e1734] shadow-sm border-slate-200"
              : "text-slate-600 border-transparent hover:text-slate-950"
              }`}
          >
            <ShoppingBag className="w-3.5 h-3.5" />
            Purchases (Input VAT)
            <span className={`ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold ${activeModule === "purchases" ? "bg-slate-200 text-[#0e1734]" : "bg-slate-200 text-slate-600"
              }`}>
              {mappings.filter((m) => m.module === "purchases").length}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setActiveModule("sales")}
            aria-pressed={activeModule === "sales"}
            className={`flex-1 py-2 rounded-md text-xs font-bold flex items-center justify-center gap-2 transition-colors cursor-pointer border ${activeModule === "sales"
              ? "bg-white text-[#0e1734] shadow-sm border-slate-200"
              : "text-slate-600 border-transparent hover:text-slate-950"
              }`}
          >
            <ShoppingCart className="w-3.5 h-3.5" />
            Sales (Output VAT)
            <span className={`ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold ${activeModule === "sales" ? "bg-slate-200 text-[#0e1734]" : "bg-slate-200 text-slate-600"
              }`}>
              {mappings.filter((m) => m.module === "sales").length}
            </span>
          </button>
        </div>

        {/* Tax Code Table */}
        <div className="border border-slate-200 rounded-lg overflow-hidden">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 text-xs font-semibold uppercase tracking-wider">
                <th className="py-3 px-4">SAP Tax Code</th>
                <th className="py-3 px-4">Description</th>
                <th className="py-3 px-4">KRA Rate</th>
                <th className="py-3 px-4">Created Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 text-slate-800">
              {filteredMappings.map((item, index) => (
                <tr key={`${item.module}-${item.sap_code}`} className="hover:bg-slate-50/70 transition-colors">
                  <td className="py-3 px-4 font-mono font-bold text-slate-900">{item.sap_code}</td>
                  <td className="py-3 px-4">
                    <input
                      type="text"
                      value={item.description}
                      onChange={(e) => handleDescriptionChange(index, e.target.value)}
                      className="w-full px-2.5 py-1.5 text-xs rounded-md border border-slate-200 transition-colors focus:outline-none focus:ring-1 focus:ring-[#0e1734]/30 focus:border-[#0e1734]"
                    />
                  </td>
                  <td className="py-3 px-4">
                    <input
                      type="text"
                      list="vat-rates-list"
                      value={item.canonical_rate}
                      onChange={(e) => handleCategoryChange(index, e.target.value)}
                      placeholder="e.g. 16, 0, EXEMPT"
                      className="w-full px-2.5 py-1.5 text-xs rounded-md border border-slate-200 font-semibold text-slate-800 transition-colors focus:outline-none focus:ring-1 focus:ring-[#0e1734]/30 focus:border-[#0e1734] placeholder:text-slate-300"
                    />
                  </td>
                  <td suppressHydrationWarning className="py-3 px-4 text-xs font-medium text-slate-500">
                    {item.created_at
                      ? new Date(item.created_at).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })
                      : "Built-in System Default"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Form to Add Custom Tax Group */}
        <form onSubmit={handleAddCustomCode} className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3">
          <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
            <Plus className="w-4 h-4 text-[#0e1734]" />
            Add Custom SAP Tax Code ({activeModule.toUpperCase()})
          </h4>

          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
            <input
              type="text"
              placeholder="SAP Code (e.g. S1)"
              value={newCode}
              onChange={(e) => setNewCode(e.target.value)}
              required
              className="px-3 py-2 h-9 rounded-lg border border-slate-200 bg-white text-xs font-mono transition-colors focus:outline-none focus:ring-2 focus:ring-[#0e1734]/20 focus:border-[#0e1734] placeholder:text-slate-400"
            />
            <input
              type="text"
              placeholder="Description (e.g. Special Rate)"
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              className="px-3 py-2 h-9 rounded-lg border border-slate-200 bg-white text-xs transition-colors focus:outline-none focus:ring-2 focus:ring-[#0e1734]/20 focus:border-[#0e1734] placeholder:text-slate-400"
            />
            <input
              type="text"
              list="vat-rates-list"
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
              placeholder="Rate (e.g. 16, 0)"
              className="px-3 py-2 h-9 rounded-lg border border-slate-200 bg-white text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-[#0e1734]/20 focus:border-[#0e1734] placeholder:text-slate-400"
            />
            <button
              type="submit"
              className="px-4 py-2 h-9 bg-[#0e1734] hover:bg-[#16224c] active:bg-[#080d21] text-white rounded-lg text-xs font-semibold transition-all duration-150 shadow-sm cursor-pointer inline-flex items-center justify-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" /> Add Code
            </button>
          </div>
        </form>

        {/* Action Button */}
        <div className="pt-4 border-t border-slate-200 flex justify-end">
          <button
            type="submit"
            onClick={handleSaveMappings}
            disabled={saving}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#0e1734] hover:bg-[#16224c] active:bg-[#080d21] text-white rounded-lg text-sm font-semibold shadow-sm transition-all duration-150 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Save Tax Mappings
          </button>
        </div>
      </div>
    </div>
  );
}
