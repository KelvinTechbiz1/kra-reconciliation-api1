"use client";

import { useState, useEffect } from "react";
import { KRAVATMappingItem } from "@/types/settings";
import { fetchWithAuth } from "@/lib/api";
import { useToast } from "@/components/ToastProvider";
import {
  Save,
  Plus,
  Trash2,
  Tag,
  Loader2,
  CheckCircle2,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

interface KRAVATMappingEditorProps {
  mappings: KRAVATMappingItem[];
  selectedCompanyId?: number | null;
  onSaved: () => void;
}

const SCHEDULE_GUIDE = [
  { prefix: "SEC_B", file: "SEC_B_WITH_VAT_PIN1.csv", name: "B – General Rated Supplies (Sales)", rate: "16%" },
  { prefix: "SEC_F", file: "SEC_F_WITH_VAT_PIN1.csv", name: "F – General Rated Purchases (local)", rate: "16%" },
  { prefix: "SEC_G", file: "SEC_G_WITH_VAT_PIN1.csv", name: "G – Other Rated Purchases", rate: "8% (Petroleum)" },
  { prefix: "SEC_H", file: "SEC_H_WITH_VAT_PIN1.csv", name: "H – Zero-Rated Purchases", rate: "0%" },
  { prefix: "SEC_I", file: "SEC_I_WITH_VAT_PIN1.csv", name: "I – Exempt Purchases", rate: "Exempt" },
];

const sortMappingsBySchedule = (items: KRAVATMappingItem[]): KRAVATMappingItem[] => {
  const prefixOrder = new Map(SCHEDULE_GUIDE.map((s, i) => [s.prefix.toUpperCase(), i]));
  return [...items].sort((a, b) => {
    const ai = prefixOrder.get(a.section_prefix.toUpperCase());
    const bi = prefixOrder.get(b.section_prefix.toUpperCase());
    if (ai !== undefined && bi !== undefined) return ai - bi;
    if (ai !== undefined) return -1;
    if (bi !== undefined) return 1;
    return 0;
  });
};

export function KRAVATMappingEditor({ mappings: initialMappings, selectedCompanyId, onSaved }: KRAVATMappingEditorProps) {
  const [mappings, setMappings] = useState<KRAVATMappingItem[]>(initialMappings);

  useEffect(() => {
    setMappings(sortMappingsBySchedule(initialMappings));
  }, [initialMappings]);
  const [showGuide, setShowGuide] = useState(false);
  const [saving, setSaving] = useState(false);
  const { notify } = useToast();
  const [reason, setReason] = useState("");

  const handleAdd = (defaultPrefix = "", defaultRate = "16") => {
    setMappings([
      ...mappings,
      {
        section_prefix: defaultPrefix,
        canonical_rate: defaultRate,
      },
    ]);
  };

  const handleRemove = (index: number) => {
    const newMappings = [...mappings];
    newMappings.splice(index, 1);
    setMappings(newMappings);
  };

  const handleChange = (index: number, field: keyof KRAVATMappingItem, value: string) => {
    const newMappings = [...mappings];
    newMappings[index] = { ...newMappings[index], [field]: value };
    setMappings(newMappings);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);

    const prefixes = new Set();
    for (const m of mappings) {
      if (!m.section_prefix.trim()) {
        notify("Section prefix cannot be empty.", "error");
        setSaving(false);
        return;
      }
      const upper = m.section_prefix.trim().toUpperCase();
      if (prefixes.has(upper)) {
        notify(`Duplicate prefix '${upper}' found in mappings.`, "error");
        setSaving(false);
        return;
      }
      prefixes.add(upper);
    }

    try {
      const payload = {
        mappings: mappings.map((m) => ({
          section_prefix: m.section_prefix.trim().toUpperCase(),
          canonical_rate: m.canonical_rate,
        })),
        reason: reason.trim() || undefined,
      };

      const res = await fetchWithAuth("/settings/kra-vat-mappings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to update KRA VAT mappings.");
      }

      setReason("");
      notify("KRA VAT mappings saved successfully!", "success");
      onSaved();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      notify(msg || "An error occurred saving KRA VAT mappings.", "error");
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
            <Tag className="w-5 h-5 text-slate-500" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900">KRA Section VAT Mappings</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Map CSV filename prefixes to canonical VAT rates for automated schedule classification
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setShowGuide(!showGuide)}
          className="text-xs text-[#0e1734] hover:text-[#16224c] font-semibold flex items-center gap-1 cursor-pointer"
        >
          {showGuide ? "Hide KRA Specs" : "View KRA Specs"}
          {showGuide ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>

      <datalist id="kra-vat-rates-list">
        <option value="16">16% (Standard Rate)</option>
        <option value="8">8% (Petroleum / Fuel Rate)</option>
        <option value="0">0% (Zero Rated Schedule)</option>
        <option value="EXEMPT">Exempt (Tax Free Schedule)</option>
      </datalist>

      <form onSubmit={handleSave} className="p-6 space-y-5">
        {/* Collapsible Specs Reference */}
        {showGuide && (
          <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 text-xs space-y-2">
            <div className="font-semibold text-slate-800">KRA iTax Standard Schedule Reference</div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-slate-600">
                <thead>
                  <tr className="border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase">
                    <th className="py-1 pr-3">Filename Pattern</th>
                    <th className="py-1 px-3">KRA Schedule</th>
                    <th className="py-1 pl-3 text-right">Standard Rate</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                  {SCHEDULE_GUIDE.map((s) => (
                    <tr key={s.prefix}>
                      <td className="py-1.5 pr-3 font-bold text-slate-800">{s.file}</td>
                      <td className="py-1.5 px-3 font-sans text-slate-700">{s.name}</td>
                      <td className="py-1.5 pl-3 text-right font-bold text-slate-900">{s.rate}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="border border-slate-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                  Filename Prefix
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                  VAT Rate
                </th>
                <th className="w-16 px-4 py-2.5"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {mappings.map((mapping, idx) => (
                <tr key={idx} className="hover:bg-slate-50/50">
                  <td className="px-4 py-2.5">
                    <input
                      type="text"
                      value={mapping.section_prefix}
                      onChange={(e) => handleChange(idx, "section_prefix", e.target.value)}
                      placeholder="e.g. SEC_B"
                      className="w-full px-3 py-1.5 h-9 rounded-md border border-slate-200 bg-white font-mono text-xs text-slate-900 focus:outline-none focus:border-[#0e1734]"
                    />
                  </td>
                  <td className="px-4 py-2.5">
                    <input
                      type="text"
                      list="kra-vat-rates-list"
                      value={mapping.canonical_rate}
                      onChange={(e) => handleChange(idx, "canonical_rate", e.target.value)}
                      placeholder="e.g. 16, 8, EXEMPT"
                      className="w-full px-3 py-1.5 h-9 rounded-md border border-slate-200 bg-white text-xs text-slate-900 focus:outline-none focus:border-[#0e1734]"
                    />
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <button
                      type="button"
                      onClick={() => handleRemove(idx)}
                      className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors cursor-pointer"
                      title="Remove row"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}

              {mappings.length === 0 && (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-slate-400 text-xs">
                    No section prefix mappings defined. Click &quot;Add Mapping Row&quot; below.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="flex justify-between items-center pt-1">
          <button
            type="button"
            onClick={() => handleAdd()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-[#0e1734] hover:text-[#16224c] hover:bg-slate-100 rounded-md border border-slate-300 transition-colors cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" /> Add Mapping Row
          </button>

          <div className="text-xs text-slate-400">
            {mappings.length} prefix rule{mappings.length !== 1 ? "s" : ""} active
          </div>
        </div>

        {/* Audit Note & Save Button */}
        <div className="pt-4 border-t border-slate-200 flex flex-col sm:flex-row items-stretch sm:items-end gap-3">
          <div className="flex-1 space-y-1">
            <label className="text-[11px] font-semibold text-slate-600 uppercase">
              Audit Note (Optional)
            </label>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Reason for changing VAT mapping rules"
              className="w-full px-3 py-2 h-9 rounded-md border border-slate-200 bg-white text-xs text-slate-900 focus:outline-none focus:border-[#0e1734] placeholder:text-slate-400"
            />
          </div>
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-[#0e1734] hover:bg-[#16224c] active:bg-[#080d21] text-white rounded-lg font-semibold text-xs transition-colors cursor-pointer disabled:opacity-50 shrink-0 h-9"
          >
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            Save Mappings
          </button>
        </div>
      </form>
    </div>
  );
}
