"use client";

import { useState, useEffect } from "react";
import {
  CertificateInfo,
  FetchCertificateResponse,
  SAPConnection,
  TestConnectionResponse,
} from "@/types/settings";
import { fetchWithAuth } from "@/lib/api";
import { getApiErrorMessage } from "@/lib/errors";
import { useToast } from "@/components/ToastProvider";
import {
  Server,
  Key,
  Database,
  User,
  ShieldCheck,
  ShieldAlert,
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Save,
  Eye,
  EyeOff,
  Lock,
  Download,
  Trash2,
} from "lucide-react";

interface SAPConnectionCardProps {
  connection: SAPConnection | null;
  selectedCompanyId?: number | null;
  companyName?: string;
  onSaved: () => void;
}

export function SAPConnectionCard({
  connection,
  selectedCompanyId,
  companyName,
  onSaved,
}: SAPConnectionCardProps) {
  const [name, setName] = useState(connection?.name || "Primary SAP Connection");
  const [baseUrl, setBaseUrl] = useState(connection?.base_url || "");
  const [companyDb, setCompanyDb] = useState(connection?.company_db || "");
  const [username, setUsername] = useState(connection?.username || "");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  // Pinned certificate for servers with a self-signed cert. "" means use public CAs.
  const [caCertificate, setCaCertificate] = useState(connection?.ca_certificate || "");
  const [caInfo, setCaInfo] = useState<CertificateInfo | null>(connection?.ca_certificate_info || null);
  const [pendingCert, setPendingCert] = useState<FetchCertificateResponse | null>(null);
  const [fetchingCert, setFetchingCert] = useState(false);
  const [showPaste, setShowPaste] = useState(false);
  useEffect(() => {
    setName(connection?.name || "Primary SAP Connection");
    setBaseUrl(connection?.base_url || "");
    setCompanyDb(connection?.company_db || "");
    setUsername(connection?.username || "");
    setPassword("");
    setCaCertificate(connection?.ca_certificate || "");
    setCaInfo(connection?.ca_certificate_info || null);
    setPendingCert(null);
    setShowPaste(false);
    setTestResult(null);
  }, [connection]);

  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestConnectionResponse | null>(null);
  const { notify } = useToast();

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const url = `/settings/test-sap${selectedCompanyId ? `?company_id=${selectedCompanyId}` : ""}`;
      const res = await fetchWithAuth(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: baseUrl,
          company_db: companyDb,
          username: username,
          password: password || undefined,
          verify_ssl: true,
          ca_certificate: caCertificate,
        }),
      });
      const data: TestConnectionResponse = await res.json();
      setTestResult(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      notify(msg || "Failed to initiate SAP diagnostic test.", "error");
    } finally {
      setTesting(false);
    }
  };

  const handleSaveConnection = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);

    try {
      const payload: Record<string, unknown> = {
        name,
        base_url: baseUrl,
        company_db: companyDb,
        username,
        verify_ssl: true,
        ca_certificate: caCertificate,
        version: connection?.version || 1,
      };
      if (password) {
        payload.password = password;
      }

      const url = `/settings/sap-connection${selectedCompanyId ? `?company_id=${selectedCompanyId}` : ""}`;
      const res = await fetchWithAuth(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.status === 409) {
        const errData = await res.json().catch(() => null);
        throw new Error(getApiErrorMessage(errData, "Optimistic lock error: Remote settings have been updated by another user. Reload required."));
      }

      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(getApiErrorMessage(errData, "Failed to save SAP connection parameters."));
      }

      setPassword("");
      notify("SAP connection configuration saved successfully!", "success");
      onSaved();
    } catch (err: unknown) {
      const msg = getApiErrorMessage(err, "An error occurred while saving.");
      notify(msg, "error");
    } finally {
      setSaving(false);
    }
  };

  const handleFieldChange = <T,>(setter: (val: T) => void) => (val: T) => {
    setter(val);
    setTestResult(null);
  };

  const handleFetchCertificate = async () => {
    setFetchingCert(true);
    setPendingCert(null);
    try {
      const res = await fetchWithAuth("/settings/sap-certificate/fetch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ base_url: baseUrl }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(getApiErrorMessage(data, "Could not retrieve the server certificate."));
      }
      setPendingCert(data as FetchCertificateResponse);
    } catch (err: unknown) {
      notify(getApiErrorMessage(err, "Could not retrieve the server certificate."), "error");
    } finally {
      setFetchingCert(false);
    }
  };

  const trustCertificate = (cert: FetchCertificateResponse) => {
    setCaCertificate(cert.pem);
    setCaInfo(cert.info);
    setPendingCert(null);
    setShowPaste(false);
    setTestResult(null);
  };

  const removeCertificate = () => {
    setCaCertificate("");
    setCaInfo(null);
    setTestResult(null);
  };

  const canFetchCertificate = baseUrl.trim().toLowerCase().startsWith("https://");

  const isTestedAndValid = testResult?.connected === true;

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden transition-all">
      {/* Header */}
      <div className="px-6 py-5 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-slate-50 rounded-lg border border-slate-200">
            <Server className="w-5 h-5 text-slate-500" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900">
              SAP Business One Connection
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Service Layer parameters & credentials{companyName ? ` for ${companyName}` : ""}
            </p>
          </div>
        </div>

        {connection ? (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Connected
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" /> Unconfigured
          </span>
        )}
      </div>

      <form onSubmit={handleSaveConnection} className="p-6 space-y-6">
        {!connection && (
          <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-xs flex items-center gap-2.5 font-medium">
            <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0" />
            <div>
              No SAP connection currently exists for {companyName || "this company"}. Enter parameters below to establish integration.
            </div>
          </div>
        )}

        <div className="space-y-6 max-w-2xl mx-auto">
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">
              Connection Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => handleFieldChange(setName)(e.target.value)}
              placeholder="e.g. Production Service Layer"
              required
              className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium placeholder:text-slate-400"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700 flex items-center gap-2">
              <Server className="w-4 h-4 text-[#0e1734]" />
              Service Layer Base URL
            </label>
            <input
              type="url"
              value={baseUrl}
              onChange={(e) => handleFieldChange(setBaseUrl)(e.target.value)}
              placeholder="https://b1su0206.cloudtaktiks.com:50000/b1s/v1"
              required
              className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm font-mono transition-colors focus:outline-none focus:ring-2 focus:ring-[#0e1734]/20 focus:border-[#0e1734] placeholder:text-slate-400"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700 flex items-center gap-2">
              <Database className="w-4 h-4 text-[#0e1734]" />
              Company Database Name
            </label>
            <input
              type="text"
              value={companyDb}
              onChange={(e) => handleFieldChange(setCompanyDb)(e.target.value)}
              placeholder="CT_TECHBIZ_TESTII"
              required
              className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm font-mono transition-colors focus:outline-none focus:ring-2 focus:ring-[#0e1734]/20 focus:border-[#0e1734] placeholder:text-slate-400"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700 flex items-center gap-2">
              <User className="w-4 h-4 text-[#0e1734]" />
              Service Layer Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => handleFieldChange(setUsername)(e.target.value)}
              placeholder="cloudtaktiks\username"
              required
              className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm font-mono transition-colors focus:outline-none focus:ring-2 focus:ring-[#0e1734]/20 focus:border-[#0e1734] placeholder:text-slate-400"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700 flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Key className="w-4 h-4 text-[#0e1734]" />
                Password
              </span>
            </label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => handleFieldChange(setPassword)(e.target.value)}
                placeholder={connection?.password_set ? "•••••••• (Unchanged)" : "Enter Service Layer Password"}
                className="w-full pl-3.5 pr-10 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm font-mono transition-colors focus:outline-none focus:ring-2 focus:ring-[#0e1734]/20 focus:border-[#0e1734] placeholder:text-slate-400"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600 cursor-pointer transition-colors"
              >
                {showPassword ? (
                  <EyeOff className="w-4 h-4" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700 flex items-center gap-2">
              <Lock className="w-4 h-4 text-[#0e1734]" />
              Trusted SSL Certificate
            </label>

            {caCertificate ? (
              <div className="p-3.5 rounded-lg border border-emerald-200 bg-emerald-50/60 text-xs space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2 font-semibold text-emerald-800">
                    <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
                    Pinned certificate. Only this server certificate is trusted.
                  </div>
                  <button
                    type="button"
                    onClick={removeCertificate}
                    className="inline-flex items-center gap-1 text-slate-500 hover:text-rose-600 cursor-pointer transition-colors shrink-0"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Remove
                  </button>
                </div>
                {caInfo ? (
                  <CertificateDetails info={caInfo} />
                ) : (
                  <p className="text-slate-600">Pasted certificate. Details appear after saving.</p>
                )}
              </div>
            ) : (
              <p className="text-xs text-slate-500">
                Verified against public certificate authorities. If your Service Layer uses SAP&apos;s
                default self-signed certificate, fetch it from the server and trust it here.
              </p>
            )}

            {pendingCert && (
              <div className="p-3.5 rounded-lg border border-amber-200 bg-amber-50 text-xs space-y-3">
                <div className="flex items-start gap-2 font-medium text-amber-800">
                  <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  Before trusting this certificate, confirm its SHA-256 fingerprint with your SAP administrator.
                </div>
                <CertificateDetails info={pendingCert.info} />
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => trustCertificate(pendingCert)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#0e1734] hover:bg-[#16224c] text-white rounded-md font-semibold cursor-pointer transition-colors"
                  >
                    <ShieldCheck className="w-3.5 h-3.5" />
                    Trust Certificate
                  </button>
                  <button
                    type="button"
                    onClick={() => setPendingCert(null)}
                    className="px-3 py-1.5 rounded-md border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 font-medium cursor-pointer transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={handleFetchCertificate}
                disabled={fetchingCert || !canFetchCertificate}
                title={canFetchCertificate ? "Retrieve the certificate this server presents" : "Base URL must start with https://"}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 text-xs font-medium cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {fetchingCert ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Download className="w-3.5 h-3.5" />
                )}
                {caCertificate ? "Re-fetch from Server" : "Fetch Server Certificate"}
              </button>
              <button
                type="button"
                onClick={() => setShowPaste(!showPaste)}
                className="px-3 py-1.5 rounded-md text-xs font-medium text-slate-600 hover:text-slate-900 cursor-pointer transition-colors"
              >
                {showPaste ? "Hide" : "Paste PEM instead"}
              </button>
            </div>

            {showPaste && (
              <textarea
                value={caCertificate}
                onChange={(e) => {
                  handleFieldChange(setCaCertificate)(e.target.value);
                  setCaInfo(null);
                }}
                rows={6}
                spellCheck={false}
                placeholder={"-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----"}
                className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 bg-white text-slate-800 text-xs font-mono transition-colors focus:outline-none focus:ring-2 focus:ring-[#0e1734]/20 focus:border-[#0e1734] placeholder:text-slate-400"
              />
            )}
          </div>
        </div>

        {/* Diagnostic Action Bar */}
        <div className="pt-4 border-t border-slate-200 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleTestConnection}
              disabled={testing || !baseUrl || !companyDb || !username}
              className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 shadow-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                !isTestedAndValid
                  ? "bg-slate-100 hover:bg-slate-200 text-[#0e1734] border border-slate-300 font-semibold"
                  : "bg-white hover:bg-slate-50 text-slate-700 border border-slate-200"
              }`}
            >
              {testing ? (
                <Loader2 className="w-4 h-4 animate-spin text-[#0e1734]" />
              ) : (
                <Activity className="w-4 h-4 text-[#0e1734]" />
              )}
              Test Connection
            </button>

            {!isTestedAndValid && !testing && (
              <span className="text-xs text-amber-700 bg-amber-50 border border-amber-200 px-2.5 py-1 rounded-md flex items-center gap-1.5 font-medium">
                <ShieldAlert className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                Test connection before saving
              </span>
            )}

            {isTestedAndValid && (
              <span className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-md flex items-center gap-1.5 font-medium">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                Connection Verified
              </span>
            )}
          </div>

          <button
            type="submit"
            disabled={!isTestedAndValid || saving || testing}
            title={!isTestedAndValid ? "Please test the connection first to enable saving." : "Save Configuration"}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#0e1734] hover:bg-[#16224c] active:bg-[#080d21] text-white rounded-lg text-sm font-semibold shadow-sm transition-all duration-150 cursor-pointer disabled:opacity-40 disabled:bg-slate-300 disabled:text-slate-500 disabled:border-slate-300 disabled:cursor-not-allowed border border-transparent"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            Save Configuration
          </button>
        </div>
      </form>

      {/* Diagnostics Modal / Output Display */}
      {testResult && (
        <div className="m-6 p-5 bg-slate-50 rounded-xl border border-slate-200 text-slate-800 text-sm space-y-4 shadow-[inset_0_1px_2px_rgba(0,0,0,0.02)]">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <div className="flex items-center gap-2">
              {testResult.connected ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              ) : (
                <XCircle className="w-5 h-5 text-rose-600" />
              )}
              <span className="font-bold text-slate-900">
                {testResult.connected ? "Diagnostic Test Succeeded" : "Connection Failure Diagnostic"}
              </span>
            </div>

            {testResult.metadata?.latency_ms && (
              <span className="text-xs text-slate-600 flex items-center gap-1.5 font-mono bg-white border border-slate-200 px-2 py-0.5 rounded-md">
                <Clock className="w-3.5 h-3.5 text-slate-500" />
                {testResult.metadata.latency_ms} ms
              </span>
            )}
          </div>

          {testResult.steps && (
            <div className="space-y-2">
              {Object.entries(testResult.steps || {}).map(([stepKey, stepVal]) => (
                <div
                  key={stepKey}
                  className="flex items-start gap-2.5 text-xs font-mono p-3 rounded-lg bg-white border border-slate-200/60 shadow-[0_1px_2px_rgba(0,0,0,0.01)]"
                >
                  {stepVal?.status === "pass" ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
                  )}
                  <div>
                    <span className="font-bold text-slate-700 capitalize">{stepKey.replace(/_/g, " ")}: </span>
                    <span className="text-slate-600">{stepVal?.message}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {testResult.error_message && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs font-mono">
              {testResult.error_message}
            </div>
          )}

          {testResult.certificate_untrusted && canFetchCertificate && !pendingCert && (
            <button
              type="button"
              onClick={handleFetchCertificate}
              disabled={fetchingCert}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 text-xs font-medium cursor-pointer transition-colors disabled:opacity-50"
            >
              {fetchingCert ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Lock className="w-3.5 h-3.5" />}
              Review Server Certificate
            </button>
          )}

          {testResult.metadata && (
            <div className="grid grid-cols-2 gap-4 text-xs font-mono pt-3 border-t border-slate-200">
              <div>
                <span className="text-slate-500 block text-[10px] font-bold uppercase tracking-wider">System Version</span>
                <span className="text-slate-800 font-bold">{testResult.metadata.system_version}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px] font-bold uppercase tracking-wider">Connected Company</span>
                <span className="text-slate-800 font-bold">{testResult.metadata.company_name}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CertificateDetails({ info }: { info: CertificateInfo }) {
  const rows: [string, string][] = [
    ["Subject", info.subject],
    ["Issuer", info.is_self_signed ? "Self-signed" : info.issuer],
    ["Expires", new Date(info.not_valid_after).toLocaleDateString()],
    ["SHA-256", info.fingerprint_sha256],
  ];
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 font-mono text-[11px]">
      {rows.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-slate-500">{label}</dt>
          <dd className="text-slate-800 break-all">
            {value}
            {label === "Expires" && info.is_expired && (
              <span className="ml-2 text-rose-600 font-semibold">Expired</span>
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
