"use client";

import { useEffect, useState, useCallback } from "react";
import { SettingsComposite } from "@/types/settings";
import { CompanyProfile, UserRecord } from "@/types/company";
import { fetchWithAuth } from "@/lib/api";
import { SAPConnectionCard } from "@/features/settings/SAPConnectionCard";
import { SystemSettingsCard } from "@/features/settings/SystemSettingsCard";
import { VATMappingEditor } from "@/features/settings/VATMappingEditor";
import { KRAVATMappingEditor } from "@/features/settings/KRAVATMappingEditor";
import { KRAParsingProfilesCard } from "@/features/settings/KRAParsingProfilesCard";
import { CompanyProfileCard } from "@/features/settings/CompanyProfileCard";
import { UserManagementCard } from "@/features/settings/UserManagementCard";
import { ERPImportProfilesCard } from "@/features/settings/ERPImportProfilesCard";
import {
  Server,
  Sliders,
  Tag,
  Loader2,
  AlertCircle,
  ShieldCheck,
  RefreshCw,
  Building2,
  Users,
  FileSpreadsheet,
  FileCode,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

type ActiveTab =
  | "company-profile"
  | "users"
  | "sap-connection"
  | "sap-vat-mappings"
  | "recon-rules"
  | "erp-import-profiles"
  | "kra-section-profiles"
  | "kra-vat-mappings";


interface NavItem {
  id: ActiveTab;
  label: string;
  icon: React.ReactNode;
  adminOnly?: boolean;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

export default function SettingsPage() {
  const [data, setData] = useState<SettingsComposite | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>("sap-connection");

  // Multi-Company & Users state
  const [companies, setCompanies] = useState<CompanyProfile[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [currentUserId, setCurrentUserId] = useState<number | null>(null);
  const [currentUserRole, setCurrentUserRole] = useState<string>("checker");
  const [isPlatformAdmin, setIsPlatformAdmin] = useState(false);

  const loadSettingsForCompany = useCallback(async (targetCompanyId?: number | null) => {
    setLoading(true);
    setError(null);
    try {
      const queryParam = targetCompanyId ? `?company_id=${targetCompanyId}` : "";
      const res = await fetchWithAuth(`/settings${queryParam}`);
      if (!res.ok) throw new Error("Failed to load enterprise settings parameters.");
      const compositeData: SettingsComposite = await res.json();
      setData(compositeData);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg || "Failed to retrieve configuration settings.");
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial Bootstrap: fetch User profile and, if Admin, companies list
  useEffect(() => {
    let isMounted = true;
    async function init() {
      try {
        const meRes = await fetchWithAuth("/auth/me");

        let userCompId: number | null = null;
        let isAdminFlag = false;

        if (meRes.ok) {
          const me = await meRes.json();
          if (isMounted) {
            setCurrentUserId(me.id);
            setCurrentUserRole(me.role);
            userCompId = me.company_id ?? null;
            isAdminFlag = me.role === "admin";
            setIsPlatformAdmin(isAdminFlag);
          }
        }

        let fetchedCompanies: CompanyProfile[] = [];
        if (isAdminFlag) {
          const companyRes = await fetchWithAuth("/company/all");
          if (companyRes.ok) {
            fetchedCompanies = await companyRes.json();
            if (isMounted) setCompanies(fetchedCompanies);
          }
        }

        // Determine target company id
        let initialTargetId = userCompId;
        if (isAdminFlag && fetchedCompanies.length > 0) {
          initialTargetId = fetchedCompanies[0].id;
        }

        if (isMounted) {
          setSelectedCompanyId(initialTargetId);
          loadSettingsForCompany(initialTargetId);
        }
      } catch (err) {
        if (isMounted) {
          setError("Failed to initialize enterprise settings workspace.");
          setLoading(false);
        }
      }
    }
    init();
    return () => {
      isMounted = false;
    };
  }, [loadSettingsForCompany]);

  const handleCompanySelectChange = (newCompId: number) => {
    setSelectedCompanyId(newCompId);
    loadSettingsForCompany(newCompId);
  };

  const loadCompanyData = useCallback(async () => {
    if (currentUserRole !== "admin") return;
    try {
      const [companyRes, usersRes] = await Promise.all([
        fetchWithAuth("/company/all"),
        fetchWithAuth("/users"),
      ]);
      if (companyRes.ok) setCompanies(await companyRes.json());
      if (usersRes.ok) setUsers(await usersRes.json());
    } catch {
      // non-critical — tab will show loading state
    }
  }, [currentUserRole]);

  // Reload company list when company tab is opened or company updated
  useEffect(() => {
    if (currentUserRole === "admin" && (activeTab === "company-profile" || activeTab === "users")) {
      const timer = setTimeout(() => {
        loadCompanyData();
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [activeTab, currentUserRole, loadCompanyData]);

  const handleCompanySaved = useCallback(() => {
    loadCompanyData();
    if (selectedCompanyId) {
      loadSettingsForCompany(selectedCompanyId);
    }
  }, [loadCompanyData, selectedCompanyId, loadSettingsForCompany]);

  const handleSettingsSaved = useCallback(() => {
    loadSettingsForCompany(selectedCompanyId);
  }, [loadSettingsForCompany, selectedCompanyId]);

  if (loading && !data) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[400px] gap-3 bg-[#F8FAFC]">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
        <span className="text-sm font-medium text-slate-600">Loading Enterprise Configuration...</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 space-y-4 max-w-2xl mx-auto my-8">
        <div className="flex items-center gap-3">
          <AlertCircle className="w-6 h-6 text-rose-600 shrink-0" />
          <h3 className="font-semibold text-base">Configuration Loading Error</h3>
        </div>
        <p className="text-sm">{error || "Unable to reach settings endpoint."}</p>
        <button
          onClick={() => loadSettingsForCompany(selectedCompanyId)}
          className="px-4 py-2 bg-rose-600 text-white rounded-lg text-sm font-medium hover:bg-rose-700 transition-colors flex items-center gap-2 cursor-pointer"
        >
          <RefreshCw className="w-4 h-4" />
          Retry Connection
        </button>
      </div>
    );
  }

  const isAdmin = currentUserRole === "admin" || isPlatformAdmin;
  const currentSelectedCompany = companies.find((c) => c.id === selectedCompanyId);

  const sections: NavSection[] = [
    {
      title: "Organization & Access",
      items: [
        { id: "company-profile", label: "Multi-Company Management", icon: <Building2 className="w-4 h-4" />, adminOnly: true },
        { id: "users", label: "User Management", icon: <Users className="w-4 h-4" />, adminOnly: true },
      ],
    },
    {
      title: "SAP Integration",
      items: [
        { id: "sap-connection", label: "Connection Parameters", icon: <Server className="w-4 h-4" /> },
        { id: "sap-vat-mappings", label: "SAP VAT Codes", icon: <Tag className="w-4 h-4" /> },
      ],
    },
    {
      title: "Reconciliation",
      items: [
        { id: "recon-rules", label: "Rules & Tolerances", icon: <Sliders className="w-4 h-4" /> },
        { id: "erp-import-profiles", label: "ERP Import Profiles", icon: <FileCode className="w-4 h-4" /> },
        { id: "kra-section-profiles", label: "KRA Section Profiles", icon: <FileSpreadsheet className="w-4 h-4" /> },
        { id: "kra-vat-mappings", label: "KRA Section VAT Mappings", icon: <Tag className="w-4 h-4" /> },
      ],
    },

  ];

  const filteredSections = sections
    .map((sec) => ({
      ...sec,
      items: sec.items.filter((item) => !item.adminOnly || isAdmin),
    }))
    .filter((sec) => sec.items.length > 0);

  // Derive the display label for the active tab
  const activeItemLabel = filteredSections
    .flatMap((s) => s.items)
    .find((i) => i.id === activeTab)?.label ?? "Settings";

  return (
    <div className="flex-1 max-w-7xl mx-auto w-full space-y-6 pb-12 px-4 md:px-6">
      {/* Header with Company Scope Switcher */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200/80 pb-5">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-blue-600" />
            Settings
          </h1>
          <p className="text-sm text-slate-400 mt-0.5">
            SAP infrastructure · Reconciliation rules · KRA mappings · Team access
          </p>
        </div>

        {/* Target Entity Switcher for Admins */}
        {isAdmin && companies.length > 0 && (
          <div className="flex items-center gap-2.5 bg-white border border-slate-200 p-2 rounded-xl shadow-xs">
            <div className="p-1.5 bg-slate-100 rounded-lg">
              <Building2 className="w-4 h-4 text-slate-600" />
            </div>
            <div className="flex flex-col">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Target Company Context</span>
              <div className="relative">
                <select
                  suppressHydrationWarning
                  value={selectedCompanyId ?? ""}
                  onChange={(e) => handleCompanySelectChange(Number(e.target.value))}
                  className="bg-transparent text-xs font-semibold text-slate-800 pr-6 py-0.5 appearance-none focus:outline-none cursor-pointer"
                >
                  {companies.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.kra_pin || "No PIN"})
                    </option>
                  ))}
                </select>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-0 top-1/2 -translate-y-1/2 pointer-events-none" />
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-col lg:flex-row gap-8 items-start">
        {/* Left Sticky Sidebar */}
        <aside className="w-full lg:w-56 shrink-0 lg:sticky lg:top-6">
          <nav className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
            {filteredSections.map((section, idx) => (
              <div key={idx}>
                {idx > 0 && <div className="border-t border-slate-100" />}

                <div className="px-4 pt-4 pb-1.5">
                  <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest">
                    {section.title}
                  </p>
                </div>

                <ul className="pb-3">
                  {section.items.map((item) => {
                    const active = activeTab === item.id;
                    return (
                      <li key={item.id}>
                        <button
                          type="button"
                          onClick={() => setActiveTab(item.id)}
                          className={`group relative w-full flex items-center gap-2.5 pl-4 pr-3 py-2 text-xs font-medium cursor-pointer transition-all duration-100 ${active
                              ? "text-[#0e1734] bg-slate-100/80 font-semibold"
                              : "text-slate-500 hover:text-slate-800 hover:bg-slate-50"
                            }`}
                        >
                          {/* Left accent bar */}
                          {active && (
                            <span className="absolute left-0 top-1 bottom-1 w-[3px] bg-[#0e1734] rounded-r-full" />
                          )}

                          {/* Icon */}
                          <span className={`shrink-0 ${active ? "text-[#0e1734]" : "text-slate-400 group-hover:text-slate-500"}`}>
                            {item.icon}
                          </span>

                          {/* Label — truncate prevents wrapping */}
                          <span className={`truncate ${active ? "font-semibold" : ""}`}>
                            {item.label}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </nav>
        </aside>

        {/* Right Tab Panel Content */}
        <main key={activeTab} className="settings-panel flex-1 min-w-0 w-full">
          {/* Breadcrumb path */}
          <div className="flex items-center gap-1.5 text-xs text-slate-400 font-medium mb-4">
            <span>Settings</span>
            <ChevronRight className="w-3.5 h-3.5" />
            <span className="text-slate-700 font-semibold">{activeItemLabel}</span>
          </div>

          {activeTab === "sap-connection" && (
            <SAPConnectionCard
              connection={data.sap_connection}
              selectedCompanyId={selectedCompanyId}
              companyName={currentSelectedCompany?.name}
              onSaved={handleSettingsSaved}
            />
          )}

          {activeTab === "recon-rules" && (
            <SystemSettingsCard
              settings={data.system_settings}
              selectedCompanyId={selectedCompanyId}
              onSaved={handleSettingsSaved}
            />
          )}

          {activeTab === "erp-import-profiles" && (
            <ERPImportProfilesCard selectedCompanyId={selectedCompanyId} />
          )}


          {activeTab === "sap-vat-mappings" && (
            <VATMappingEditor
              connectionId={data.sap_connection?.id || null}
              mappings={data.vat_mappings}
              selectedCompanyId={selectedCompanyId}
              onSaved={handleSettingsSaved}
            />
          )}

          {activeTab === "kra-section-profiles" && (
            <KRAParsingProfilesCard
              settings={data.system_settings}
              selectedCompanyId={selectedCompanyId}
              onSaved={handleSettingsSaved}
            />
          )}

          {activeTab === "kra-vat-mappings" && (
            <KRAVATMappingEditor
              mappings={data.kra_vat_mappings}
              selectedCompanyId={selectedCompanyId}
              onSaved={handleSettingsSaved}
            />
          )}

          {activeTab === "company-profile" && isAdmin && (
            <CompanyProfileCard companies={companies} onSaved={handleCompanySaved} />
          )}

          {activeTab === "users" && isAdmin && (
            <UserManagementCard
              users={users}
              companies={companies}
              currentUserId={currentUserId ?? 0}
              onSaved={handleCompanySaved}
            />
          )}
        </main>
      </div>
    </div>
  );
}
