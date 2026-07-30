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
  EyeOff,
  Edit3,
  X,
  Save,
  Loader2,
  CheckCircle2,
  ShieldAlert,
  KeyRound,
  Mail,
  ToggleLeft,
  ToggleRight,
  BadgeCheck,
  Building2,
  Globe,
  Search,
  Copy,
  Check,
  RefreshCw,
  Trash2,
} from "lucide-react";

import { validatePasswordPolicy, generateAutoPassword } from "@/lib/passwordPolicy";
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
  company_admin: {
    label: "Company Admin",
    color: "bg-amber-100 text-amber-800 border border-amber-200",
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
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<UserRole>("checker");
  const [companyId, setCompanyId] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [createdUser, setCreatedUser] = useState<{ username: string; email?: string } | null>(null);
  const { notify } = useToast();

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();

    setSaving(true);
    try {
      const payload: UserCreatePayload = {
        username,
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
      const data = await res.json();

      setCreatedUser({ username: data.username, email: data.email });
      notify(`User account @${username} created successfully.`, "success");
      onCreated();
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
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-lg max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 shrink-0">
              <UserPlus className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-sm">
                {createdUser ? "Account Created Successfully" : "Create New Team Account"}
              </h3>
              <p className="text-xs text-slate-500">Provision credentials and scope permissions</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1 rounded-lg transition-colors cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>

        {createdUser ? (
          <div className="p-6 space-y-5 text-center flex-1 overflow-y-auto">
            <div className="w-12 h-12 bg-emerald-100 border border-emerald-200 text-emerald-600 rounded-full flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-7 h-7" />
            </div>
            <div>
              <h4 className="font-bold text-slate-900 text-base">Account @{createdUser.username} Provisioned</h4>
              <p className="text-xs text-slate-600 mt-2 leading-relaxed">
                {createdUser.email ? (
                  <>
                    A secure password has been automatically generated and sent via email to{" "}
                    <span className="font-semibold text-slate-900">{createdUser.email}</span>.
                  </>
                ) : (
                  <>The user account has been successfully created in the system.</>
                )}
              </p>
            </div>

            <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 text-left space-y-2">
              <div className="flex justify-between items-center text-xs">
                <span className="text-slate-500 font-medium uppercase tracking-wider">Username</span>
                <span className="font-mono font-bold text-slate-900">@{createdUser.username}</span>
              </div>
              {createdUser.email && (
                <div className="flex justify-between items-center text-xs border-t border-slate-200/60 pt-2">
                  <span className="text-slate-500 font-medium uppercase tracking-wider">Recipient Email</span>
                  <span className="font-medium text-slate-800">{createdUser.email}</span>
                </div>
              )}
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={onClose}
                className="w-full sm:w-auto px-6 py-2.5 bg-[#0e1734] hover:bg-[#16224c] text-white rounded-lg text-sm font-semibold cursor-pointer transition-colors"
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          <>
            <form onSubmit={handleCreate} id="create-user-form" className="p-6 space-y-4 flex-1 overflow-y-auto text-xs">
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

                {/* Password Automated Email Notice */}
                <div className="space-y-1.5 col-span-2 bg-blue-50/60 p-3.5 rounded-xl border border-blue-100">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-blue-600 shrink-0" />
                    <h4 className="text-xs font-semibold text-slate-800">Automated Secure Password</h4>
                  </div>
                  <p className="text-[12px] text-slate-600 leading-relaxed">
                    A secure password will be automatically generated and emailed directly to the user upon account creation.
                  </p>
                </div>

                <div className="space-y-1.5 col-span-2">
                  <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Role Access *</label>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value as UserRole)}
                    className="w-full px-3.5 py-2.5 h-10 rounded-lg border border-slate-200 bg-white text-slate-800 text-sm font-medium cursor-pointer transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  >
                    <option value="checker">Checker</option>
                    <option value="company_admin">Company Admin</option>
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
            </form>
            <div className="px-6 py-4 border-t border-slate-100 flex justify-end gap-3 bg-slate-50/50 shrink-0">
              <button type="button" onClick={onClose} className="px-4 py-2.5 text-slate-600 hover:text-slate-900 text-sm font-medium transition-colors cursor-pointer">
                Cancel
              </button>
              <button
                type="submit"
                form="create-user-form"
                disabled={saving}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#0e1734] hover:bg-[#16224c] active:bg-[#080d21] text-white rounded-lg text-sm font-semibold shadow-sm transition-all duration-150 cursor-pointer disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" />}
                Create Account
              </button>
            </div>
          </>
        )}
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

  const handleAutoGenerate = () => {
    const pwd = generateAutoPassword();
    setNewPassword(pwd);
    notify("Auto-generated compliant password.", "info");
  };

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
      notify(`Password reset successfully for @${user.username}.`, "success");
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
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-md max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-600 shrink-0">
              <KeyRound className="w-5 h-5 text-amber-500" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-sm">Reset Password — @{user.username}</h3>
              <p className="text-xs text-slate-500">Update account access credentials</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1 rounded-lg transition-colors cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>
        <form onSubmit={handleReset} id="reset-password-form" className="p-6 space-y-4 flex-1 overflow-y-auto text-xs">
          {success && (
            <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 text-sm flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" /> Password reset successfully.
            </div>
          )}
          {!success && (
            <div className="space-y-1.5">
              <div className="flex justify-between items-center">
                <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">New Password *</label>
                <button
                  type="button"
                  onClick={handleAutoGenerate}
                  className="text-xs text-amber-600 hover:text-amber-800 font-semibold flex items-center gap-1 cursor-pointer transition-colors"
                >
                  <RefreshCw className="w-3 h-3" /> Auto-Generate
                </button>
              </div>
              <input
                type="text"
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
        </form>
        <div className="px-6 py-4 border-t border-slate-100 flex justify-end gap-3 bg-slate-50/50 shrink-0">
          <button type="button" onClick={onClose} className="px-4 py-2.5 text-slate-600 hover:text-slate-900 text-sm font-medium cursor-pointer">
            {success ? "Close" : "Cancel"}
          </button>
          {!success && (
            <button
              type="submit"
              form="reset-password-form"
              disabled={saving}
              className="px-4 py-2.5 bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-white rounded-lg text-sm font-semibold flex items-center gap-2 cursor-pointer disabled:opacity-50"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
              Reset Password
            </button>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}

// --- Delete User Confirmation Modal ---
interface DeleteUserModalProps {
  user: UserRecord;
  onClose: () => void;
  onDeleted: () => void;
}

function DeleteUserModal({ user, onClose, onDeleted }: DeleteUserModalProps) {
  const [mounted, setMounted] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const { notify } = useToast();

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      const res = await fetchWithAuth(`/users/${user.id}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to delete user.");
      }
      notify(`User account @${user.username} deleted successfully.`, "success");
      onDeleted();
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      notify(msg || "An error occurred while deleting account.", "error");
    } finally {
      setDeleting(false);
    }
  };

  if (!mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-md max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-rose-50 border border-rose-100 flex items-center justify-center text-rose-600 shrink-0">
              <Trash2 className="w-5 h-5 text-rose-600" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-sm">Delete User Account</h3>
              <p className="text-xs text-slate-500">Revoke permissions and remove user profile</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1 rounded-lg transition-colors cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-6 space-y-4 flex-1 overflow-y-auto text-xs">
          <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 text-xs text-rose-900 space-y-2">
            <div className="font-bold flex items-center gap-1.5 text-rose-700">
              <ShieldAlert className="w-4 h-4 shrink-0" /> Permanent Action Warning
            </div>
            <p className="leading-relaxed">
              Are you sure you want to permanently delete user <span className="font-bold font-mono text-slate-900">@{user.username}</span>? This action cannot be undone and will remove their access profile.
            </p>
          </div>

          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 text-xs space-y-1.5">
            <div className="flex justify-between">
              <span className="text-slate-500 font-medium">User Name:</span>
              <span className="font-semibold text-slate-900">{user.full_name || user.username}</span>
            </div>
            {user.email && (
              <div className="flex justify-between">
                <span className="text-slate-500 font-medium">Email:</span>
                <span className="font-medium text-slate-800">{user.email}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-slate-500 font-medium">Role Access:</span>
              <span className="font-semibold text-slate-800 capitalize">{user.role}</span>
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-slate-100 flex justify-end gap-3 bg-slate-50/50 shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2.5 text-slate-600 hover:text-slate-900 text-sm font-medium cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            className="px-4 py-2.5 bg-rose-600 hover:bg-rose-700 active:bg-rose-800 text-white rounded-lg text-sm font-semibold flex items-center gap-2 cursor-pointer disabled:opacity-50 transition-colors shadow-sm"
          >
            {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
            Delete Account
          </button>
        </div>
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
      notify(`User profile @${username} updated successfully.`, "success");
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
  const [deleteUserId, setDeleteUserId] = useState<number | null>(null);
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [sendingEmailId, setSendingEmailId] = useState<number | null>(null);

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

  const { notify } = useToast();

  const handleSendResetEmail = async (user: UserRecord) => {
    if (!user.email) {
      notify(`User @${user.username} does not have an email address configured. Please set an email first.`, "error");
      return;
    }
    setSendingEmailId(user.id);
    try {
      const res = await fetchWithAuth(`/users/${user.id}/send-reset-email`, {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to send reset email.");
      }
      notify(`Password reset link successfully sent to ${user.email} .`, "success");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      notify(msg || "An error occurred while sending email.", "error");
    } finally {
      setSendingEmailId(null);
    }
  };

  const handleToggleActive = async (user: UserRecord) => {
    if (user.id === currentUserId) return;
    setTogglingId(user.id);
    try {
      const res = await fetchWithAuth(`/users/${user.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !user.is_active }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to update user status.");
      }
      notify(`User @${user.username} ${user.is_active ? "deactivated" : "activated"} successfully.`, "success");
      onSaved();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      notify(msg || "An error occurred while updating status.", "error");
    } finally {
      setTogglingId(null);
    }
  };

  const resetUser = users.find((u) => u.id === resetUserId);
  const deleteUser = users.find((u) => u.id === deleteUserId);

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
      {deleteUser && (
        <DeleteUserModal
          user={deleteUser}
          onClose={() => setDeleteUserId(null)}
          onDeleted={onSaved}
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
                              : user.role === "company_admin"
                                ? "bg-amber-100 text-amber-800"
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
                            onClick={() => handleSendResetEmail(user)}
                            disabled={sendingEmailId === user.id}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition-colors cursor-pointer disabled:opacity-50"
                            title="Send Password Reset Email"
                          >
                            {sendingEmailId === user.id ? (
                              <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
                            ) : (
                              <Mail className="w-4 h-4" />
                            )}
                          </button>
                          <button
                            onClick={() => setResetUserId(user.id)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-amber-600 hover:bg-amber-50 transition-colors cursor-pointer"
                            title="Manual password override"
                          >
                            <KeyRound className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setDeleteUserId(user.id)}
                            disabled={user.id === currentUserId}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                            title={user.id === currentUserId ? "You cannot delete your own account" : "Delete user account"}
                          >
                            <Trash2 className="w-4 h-4" />
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
