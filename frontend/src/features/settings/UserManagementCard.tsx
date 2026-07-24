"use client";

import { useState, useEffect, Fragment } from "react";
import { createPortal } from "react-dom";
import { UserRecord, UserCreatePayload, UserUpdatePayload, UserRole, CompanyProfile } from "@/types/company";
import { fetchWithAuth } from "@/lib/api";
import { useToast } from "@/components/ToastProvider";
import {
  Users,
  UserPlus,
  ShieldCheck,
  Eye,
  Edit3,
  X,
  Save,
  Loader2,
  CheckCircle2,
  ShieldAlert,
  KeyRound,
  ToggleLeft,
  ToggleRight,
  BadgeCheck,
  Building2,
  Globe,
  Search,
} from "lucide-react";

import { validatePasswordPolicy } from "@/lib/passwordPolicy";
import { PasswordStrengthIndicator } from "@/components/common/PasswordStrengthIndicator";

interface UserManagementCardProps {
  users: UserRecord[];
  companies?: CompanyProfile[];
  currentUserId: number;
  onSaved: () => void;
}

const ROLE_META: Record<UserRole, { label: string; color: string; icon: React.ReactNode }> = {
  admin: {
    label: "Admin",
    color: "bg-violet-100 text-violet-800 border border-violet-200",
    icon: <ShieldCheck className="w-3 h-3" />,
  },
  checker: {
    label: "Checker",
    color: "bg-blue-100 text-blue-800 border border-blue-200",
    icon: <BadgeCheck className="w-3 h-3" />,
  },
};

function RoleBadge({ role }: { role: UserRole }) {
  const meta = ROLE_META[role] || ROLE_META.checker;
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${meta.color}`}>
      {meta.icon}
      {meta.label}
    </span>
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return "Never";
  return new Date(iso).toLocaleDateString("en-KE", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

// --- Create User Modal ---
interface CreateUserModalProps {
  companies: CompanyProfile[];
  onClose: () => void;
  onCreated: () => void;
}

function CreateUserModal({ companies, onClose, onCreated }: CreateUserModalProps) {
  const [mounted, setMounted] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<UserRole>("checker");
  const [companyId, setCompanyId] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const { notify } = useToast();

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();

    const policy = validatePasswordPolicy(password);
    if (!policy.isValid) {
      notify("Password does not meet complexity requirements. Please satisfy all policy conditions.", "error");
      return;
    }

    setSaving(true);
    try {
      const payload: UserCreatePayload = {
        username,
        password,
        email: email || undefined,
        full_name: fullName || undefined,
        role,
        company_id: companyId ? parseInt(companyId, 10) : undefined,
      };
      const res = await fetchWithAuth("/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json();
        const detailMsg = Array.isArray(err.detail)
          ? err.detail.map((d: { msg?: string }) => d.msg).join(", ")
          : err.detail;
        throw new Error(detailMsg || "Failed to create user.");
      }
      onCreated();
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      notify(msg || "An error occurred.", "error");
    } finally {
      setSaving(false);
    }
  };

  if (!mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <UserPlus className="w-5 h-5 text-blue-600" />
            <h3 className="font-bold text-slate-900 text-sm">Create New Team Account</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>
        <form onSubmit={handleCreate} className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5 col-span-2">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Username *</label>
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="john.doe"
                className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-900 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium placeholder:text-slate-400"
              />
            </div>
            <div className="space-y-1.5 col-span-2">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Full Name</label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="John Doe"
                className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-900 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 placeholder:text-slate-400"
              />
            </div>
            <div className="space-y-1.5 col-span-2">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Email Address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="john@company.com"
                className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-900 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 placeholder:text-slate-400"
              />
            </div>
            <div className="space-y-1.5 col-span-2">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Password *</label>
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="SecureP@ss123"
                className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-900 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 placeholder:text-slate-400 font-mono"
              />
              <PasswordStrengthIndicator password={password} />
            </div>
            <div className="space-y-1.5 col-span-2">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Role Access *</label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as UserRole)}
                className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm font-medium cursor-pointer transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              >
                <option value="checker">Checker</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            {/* Company Scope Selection */}
            <div className="space-y-1.5 col-span-2">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5 text-slate-500" />
                Assigned Company Entity Scope
              </label>
              <select
                value={companyId}
                onChange={(e) => setCompanyId(e.target.value)}
                className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm font-medium cursor-pointer transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              >
                <option value="">Global Enterprise Scope (All Companies)</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} {c.kra_pin ? `(${c.kra_pin})` : ""}
                  </option>
                ))}
              </select>
              <span className="text-[11px] text-slate-500 block">
                Assigning a specific company restricts user activity to that entity only.
              </span>
            </div>
          </div>
          <div className="pt-3 flex justify-end gap-3 border-t border-slate-100">
            <button type="button" onClick={onClose} className="px-4 py-2.5 text-slate-600 hover:text-slate-900 text-sm font-medium transition-colors cursor-pointer">
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#0e1734] hover:bg-[#16224c] active:bg-[#080d21] text-white rounded-lg text-sm font-semibold shadow-sm transition-all duration-150 cursor-pointer disabled:opacity-50"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" />}
              Create Account
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}

// --- Reset Password Modal ---
interface ResetPasswordModalProps {
  user: UserRecord;
  onClose: () => void;
  onReset: () => void;
}

function ResetPasswordModal({ user, onClose, onReset }: ResetPasswordModalProps) {
  const [mounted, setMounted] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const { notify } = useToast();

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();

    const policy = validatePasswordPolicy(newPassword);
    if (!policy.isValid) {
      notify("Password does not meet complexity requirements. Please satisfy all policy conditions.", "error");
      return;
    }

    setSaving(true);
    try {
      const res = await fetchWithAuth(`/users/${user.id}/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_password: newPassword }),
      });
      if (!res.ok) {
        const err = await res.json();
        const detailMsg = Array.isArray(err.detail)
          ? err.detail.map((d: { msg?: string }) => d.msg).join(", ")
          : err.detail;
        throw new Error(detailMsg || "Failed to reset password.");
      }
      setSuccess(true);
      onReset();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      notify(msg || "An error occurred.", "error");
    } finally {
      setSaving(false);
    }
  };

  if (!mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <KeyRound className="w-5 h-5 text-amber-500" />
            <h3 className="font-bold text-slate-900 text-sm">Reset Password — @{user.username}</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>
        <form onSubmit={handleReset} className="p-6 space-y-4">
          {success && (
            <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 text-sm flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" /> Password reset successfully.
            </div>
          )}
          {!success && (
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">New Password *</label>
              <input
                type="password"
                required
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="SecureP@ss123"
                className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-900 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 placeholder:text-slate-400 font-mono"
              />
              <PasswordStrengthIndicator password={newPassword} />
            </div>
          )}
          <div className="pt-2 flex justify-end gap-3">
            <button type="button" onClick={onClose} className="px-4 py-2.5 text-slate-600 hover:text-slate-900 text-sm font-medium cursor-pointer">
              {success ? "Close" : "Cancel"}
            </button>
            {!success && (
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2.5 bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-white rounded-lg text-sm font-semibold flex items-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
                Reset Password
              </button>
            )}
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}

// --- Edit User Inline Row ---
interface EditUserRowProps {
  user: UserRecord;
  companies: CompanyProfile[];
  onSaved: () => void;
  onCancel: () => void;
}

function EditUserRow({ user, companies, onSaved, onCancel }: EditUserRowProps) {
  const [username, setUsername] = useState(user.username);
  const [role, setRole] = useState<UserRole>(user.role as UserRole);
  const [email, setEmail] = useState(user.email || "");
  const [fullName, setFullName] = useState(user.full_name || "");
  const [companyId, setCompanyId] = useState<string>(user.company_id ? String(user.company_id) : "");
  const [saving, setSaving] = useState(false);
  const { notify } = useToast();

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload: UserUpdatePayload = {
        username: username.trim() || undefined,
        role,
        email: email || undefined,
        full_name: fullName || undefined,
        company_id: companyId ? parseInt(companyId, 10) : undefined,
      };
      const res = await fetchWithAuth(`/users/${user.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to save.");
      }
      onSaved();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      notify(msg || "An error occurred.", "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <tr className="bg-blue-50/40 border-t border-blue-100">
      <td className="px-5 py-4" colSpan={6}>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 mb-3">
          <div className="space-y-1">
            <label className="text-[10px] font-semibold text-slate-600 uppercase">Username *</label>
            <input
              type="text"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-1.5 h-9 rounded-md border border-slate-200 bg-white text-xs font-semibold text-slate-900 focus:outline-none focus:border-blue-500 font-mono"
            />
          </div>
          <div className="space-y-1">
            <label className="text-[10px] font-semibold text-slate-600 uppercase">Full Name</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full px-3 py-1.5 h-9 rounded-md border border-slate-200 bg-white text-xs font-medium text-slate-900 focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="space-y-1">
            <label className="text-[10px] font-semibold text-slate-600 uppercase">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-1.5 h-9 rounded-md border border-slate-200 bg-white text-xs text-slate-900 focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="space-y-1">
            <label className="text-[10px] font-semibold text-slate-600 uppercase">Role Access</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              className="w-full px-3 py-1.5 h-9 rounded-md border border-slate-200 bg-white text-xs text-slate-800 font-medium cursor-pointer focus:outline-none focus:border-blue-500"
            >
              <option value="checker">Checker</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-[10px] font-semibold text-slate-600 uppercase">Company Entity Scope</label>
            <select
              value={companyId}
              onChange={(e) => setCompanyId(e.target.value)}
              className="w-full px-3 py-1.5 h-9 rounded-md border border-slate-200 bg-white text-xs text-slate-800 font-medium cursor-pointer focus:outline-none focus:border-blue-500"
            >
              <option value="">Global Enterprise Scope</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-3.5 py-1.5 bg-[#0e1734] hover:bg-[#16224c] text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            Save Account
          </button>
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-slate-600 hover:text-slate-900 text-xs font-medium rounded-lg border border-slate-200 bg-white hover:bg-slate-50 cursor-pointer"
          >
            Cancel
          </button>
        </div>
      </td>
    </tr>
  );
}

// --- Main User Management Workspace Component ---
export function UserManagementCard({ users, companies = [], currentUserId, onSaved }: UserManagementCardProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCompanyFilter, setSelectedCompanyFilter] = useState<string>("all");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [resetUserId, setResetUserId] = useState<number | null>(null);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  const companyMap = new Map<number, CompanyProfile>();
  companies.forEach((c) => companyMap.set(c.id, c));

  const filteredUsers = users.filter((u) => {
    const matchesSearch =
      u.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (u.full_name && u.full_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (u.email && u.email.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesCompany =
      selectedCompanyFilter === "all"
        ? true
        : selectedCompanyFilter === "global"
          ? !u.company_id
          : u.company_id === parseInt(selectedCompanyFilter, 10);

    return matchesSearch && matchesCompany;
  });

  const handleToggleActive = async (user: UserRecord) => {
    if (user.id === currentUserId) return;
    setTogglingId(user.id);
    try {
      await fetchWithAuth(`/users/${user.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !user.is_active }),
      });
      onSaved();
    } catch {
      // stay silent on network error; parent refresh handles update
    } finally {
      setTogglingId(null);
    }
  };

  const resetUser = users.find((u) => u.id === resetUserId);

  return (
    <>
      {showCreateModal && (
        <CreateUserModal
          companies={companies}
          onClose={() => setShowCreateModal(false)}
          onCreated={onSaved}
        />
      )}
      {resetUser && (
        <ResetPasswordModal
          user={resetUser}
          onClose={() => setResetUserId(null)}
          onReset={onSaved}
        />
      )}

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden space-y-0">
        {/* Workspace Header */}
        <div className="px-6 py-5 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center text-[#0e1734] shrink-0">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-900">Multi-Company Team Access</h2>
                <span suppressHydrationWarning className="px-2 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-200">
                  {users.length} Active User{users.length !== 1 ? "s" : ""}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">Manage member credentials, role scopes, and multi-entity access rights</p>
            </div>
          </div>

          <button
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-[#0e1734] hover:bg-[#16224c] active:bg-[#080d21] text-white rounded-lg text-sm font-semibold shadow-sm transition-all duration-150 cursor-pointer"
          >
            <UserPlus className="w-4 h-4" /> Invite Team Member
          </button>
        </div>

        {/* Search & Company Filter Controls Bar */}
        <div className="p-4 bg-slate-50/70 border-b border-slate-200 flex flex-col sm:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search users by name, username, or email..."
              className="w-full pl-10 pr-4 py-2 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 placeholder:text-slate-400"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto shrink-0">
            <Building2 className="w-4 h-4 text-slate-400 shrink-0 hidden sm:block" />
            <select
              value={selectedCompanyFilter}
              onChange={(e) => setSelectedCompanyFilter(e.target.value)}
              className="w-full sm:w-56 px-3 py-2 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm font-medium cursor-pointer transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            >
              <option suppressHydrationWarning value="all">All Entity Scopes ({users.length})</option>
              <option value="global">Global Enterprise Scope</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Directory Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">User Account</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Role Access</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Company Scope</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Status</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Last Activity</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredUsers.map((user) => {
                const assignedCompany = user.company_id ? companyMap.get(user.company_id) : null;

                return (
                  <Fragment key={user.id}>
                    <tr
                      className={`hover:bg-slate-50/70 transition-colors ${!user.is_active ? "opacity-60" : ""}`}
                    >
                      {/* User Column */}
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-3">
                          <div
                            className={`w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${user.role === "admin"
                                ? "bg-violet-100 text-violet-800"
                                : user.role === "checker"
                                  ? "bg-blue-100 text-blue-800"
                                  : "bg-slate-100 text-slate-700"
                              }`}
                          >
                            {(user.full_name || user.username)[0].toUpperCase()}
                          </div>
                          <div>
                            <div className="font-semibold text-slate-900 text-sm flex items-center gap-1.5">
                              {user.full_name || user.username}
                              {user.id === currentUserId && (
                                <span className="text-[10px] font-bold bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full">
                                  You
                                </span>
                              )}
                            </div>
                            <div className="text-xs text-slate-500 font-mono">
                              @{user.username} {user.email ? `· ${user.email}` : ""}
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Role Column */}
                      <td className="px-5 py-3.5">
                        <RoleBadge role={user.role as UserRole} />
                      </td>

                      {/* Company Scope Column */}
                      <td className="px-5 py-3.5">
                        {assignedCompany ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-blue-50 text-blue-800 border border-blue-200">
                            <Building2 className="w-3 h-3 text-blue-600 shrink-0" />
                            {assignedCompany.name}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
                            <Globe className="w-3 h-3 text-slate-500 shrink-0" />
                            All
                          </span>
                        )}
                      </td>

                      {/* Status Column */}
                      <td className="px-5 py-3.5">
                        <button
                          onClick={() => handleToggleActive(user)}
                          disabled={user.id === currentUserId || togglingId === user.id}
                          title={user.id === currentUserId ? "You cannot deactivate your own account" : undefined}
                          className="flex items-center gap-1.5 text-xs font-medium cursor-pointer disabled:cursor-not-allowed disabled:opacity-50 transition-opacity"
                        >
                          {togglingId === user.id ? (
                            <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
                          ) : user.is_active ? (
                            <ToggleRight className="w-5 h-5 text-emerald-500" />
                          ) : (
                            <ToggleLeft className="w-5 h-5 text-slate-400" />
                          )}
                          <span className={user.is_active ? "text-emerald-700 font-medium" : "text-slate-500"}>
                            {user.is_active ? "Active" : "Inactive"}
                          </span>
                        </button>
                      </td>

                      {/* Last Login Column */}
                      <td suppressHydrationWarning className="px-5 py-3.5 text-xs text-slate-500">
                        {formatDate(user.last_login_at)}
                      </td>

                      {/* Actions Column */}
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => setEditingId(editingId === user.id ? null : user.id)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition-colors cursor-pointer"
                            title="Edit account scope and role"
                          >
                            {editingId === user.id ? <X className="w-4 h-4" /> : <Edit3 className="w-4 h-4" />}
                          </button>
                          <button
                            onClick={() => setResetUserId(user.id)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-amber-600 hover:bg-amber-50 transition-colors cursor-pointer"
                            title="Reset password"
                          >
                            <KeyRound className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>

                    {/* Inline Edit Row */}
                    {editingId === user.id && (
                      <EditUserRow
                        key={`edit-${user.id}`}
                        user={user}
                        companies={companies}
                        onSaved={() => {
                          setEditingId(null);
                          onSaved();
                        }}
                        onCancel={() => setEditingId(null)}
                      />
                    )}
                  </Fragment>
                );
              })}

              {filteredUsers.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-12 text-center text-slate-400 text-sm">
                    No team accounts found matching your filter criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
