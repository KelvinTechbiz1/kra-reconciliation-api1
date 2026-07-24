"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { API_BASE_URL } from "@/lib/api";
import { validatePasswordPolicy } from "@/lib/passwordPolicy";
import { PasswordStrengthIndicator } from "@/components/common/PasswordStrengthIndicator";
import {
  Lock,
  Eye,
  EyeOff,
  ArrowLeft,
  ArrowRight,
  Loader2,
  CheckCircle2,
  ShieldAlert,
  KeyRound,
} from "lucide-react";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [verifying, setVerifying] = useState(true);
  const [tokenValid, setTokenValid] = useState(false);
  const [username, setUsername] = useState("");
  
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) {
      setVerifying(false);
      setTokenValid(false);
      setError("Password reset token is missing from URL.");
      return;
    }

    const verifyToken = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/auth/verify-reset-token`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });

        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.detail || "Password reset link is invalid or has expired.");
        }

        const data = await response.json();
        setTokenValid(true);
        if (data.username) {
          setUsername(data.username);
        }
      } catch (err: unknown) {
        setTokenValid(false);
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Password reset link is invalid or has expired.");
        }
      } finally {
        setVerifying(false);
      }
    };

    verifyToken();
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (newPassword !== confirmPassword) {
      setError("Passwords do not match. Please re-enter your password.");
      return;
    }

    const policy = validatePasswordPolicy(newPassword);
    if (!policy.isValid) {
      setError("Password does not satisfy complexity rules. Please see requirements below.");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token,
          new_password: newPassword,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to reset password.");
      }

      setSuccess(true);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An error occurred while resetting your password.");
      }
    } finally {
      setLoading(false);
    }
  };

  if (verifying) {
    return (
      <div className="py-12 text-center space-y-4">
        <Loader2 className="w-8 h-8 text-[#0e1734] animate-spin mx-auto" />
        <p className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
          Verifying security token...
        </p>
      </div>
    );
  }

  if (!tokenValid) {
    return (
      <div className="space-y-6 text-center animate-in fade-in zoom-in-95 duration-200">
        <div className="mx-auto w-12 h-12 bg-rose-100 rounded-2xl flex items-center justify-center text-rose-600">
          <ShieldAlert className="w-6 h-6" />
        </div>
        <div className="space-y-2">
          <h3 className="text-base font-bold text-slate-900">Invalid or Expired Link</h3>
          <p className="text-xs text-slate-600 leading-relaxed max-w-xs mx-auto">
            {error || "This password reset link is invalid or has expired. Please request a new one."}
          </p>
        </div>
        <div className="pt-2 space-y-2">
          <Link
            href="/forgot-password"
            className="w-full h-11 bg-[#0e1734] hover:bg-[#16224c] text-white rounded-xl font-semibold text-sm shadow-sm transition-all duration-150 flex items-center justify-center gap-2"
          >
            <span>Request New Reset Link</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            href="/login"
            className="w-full h-11 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-xl font-semibold text-sm transition-all flex items-center justify-center gap-2"
          >
            <ArrowLeft className="w-4 h-4 text-slate-500" />
            <span>Return to Sign In</span>
          </Link>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="space-y-6 text-center animate-in fade-in zoom-in-95 duration-200">
        <div className="mx-auto w-12 h-12 bg-emerald-100 rounded-2xl flex items-center justify-center text-emerald-600">
          <CheckCircle2 className="w-6 h-6" />
        </div>
        <div className="space-y-2">
          <h3 className="text-base font-bold text-slate-900">Password Reset Complete</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            Your password for <strong className="text-slate-900">@{username}</strong> has been updated successfully. You can now log in using your new credentials.
          </p>
        </div>
        <div className="pt-2">
          <Link
            href="/login"
            className="w-full h-11 bg-[#0e1734] hover:bg-[#16224c] text-white rounded-xl font-semibold text-sm shadow-sm transition-all duration-150 flex items-center justify-center gap-2"
          >
            <span>Proceed to Sign In</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-xs flex items-start gap-2.5">
          <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
          <div className="font-medium">{error}</div>
        </div>
      )}

      {username && (
        <div className="p-3 bg-blue-50/60 border border-blue-100 rounded-xl text-xs text-blue-900 flex items-center gap-2 font-medium">
          <KeyRound className="w-4 h-4 text-blue-600 shrink-0" />
          <span>Resetting password for user: <strong>@{username}</strong></span>
        </div>
      )}

      <div className="space-y-1.5">
        <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
          New Password *
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
            <Lock className="w-4 h-4" />
          </div>
          <input
            type={showPassword ? "text" : "password"}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            autoFocus
            minLength={8}
            placeholder="Enter new password"
            className="w-full pl-10 pr-10 py-2.5 h-11 rounded-xl border border-slate-200 bg-white text-slate-900 text-sm font-medium transition-all focus:outline-none focus:ring-4 focus:ring-[#0e1734]/10 focus:border-[#0e1734] font-mono"
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
          >
            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
        <PasswordStrengthIndicator password={newPassword} />
      </div>

      <div className="space-y-1.5 pt-1">
        <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
          Confirm New Password *
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
            <Lock className="w-4 h-4" />
          </div>
          <input
            type={showPassword ? "text" : "password"}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            minLength={8}
            placeholder="Confirm new password"
            className="w-full pl-10 pr-10 py-2.5 h-11 rounded-xl border border-slate-200 bg-white text-slate-900 text-sm font-medium transition-all focus:outline-none focus:ring-4 focus:ring-[#0e1734]/10 focus:border-[#0e1734] font-mono"
          />
        </div>
      </div>

      <div className="pt-3">
        <button
          type="submit"
          disabled={loading || !newPassword || !confirmPassword}
          className="w-full h-11 bg-[#0e1734] hover:bg-[#16224c] active:bg-[#080d21] text-white rounded-xl font-semibold text-sm shadow-sm transition-all duration-150 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Updating Password...</span>
            </>
          ) : (
            <>
              <span>Save & Update Password</span>
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </div>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen w-full bg-slate-50 flex items-center justify-center p-4 sm:p-6 lg:p-8 relative overflow-hidden select-none">
      <div className="absolute inset-0 bg-[radial-gradient(#e2e8f0_1px,transparent_1px)] [background-size:24px_24px] opacity-60 pointer-events-none" />

      <div className="w-full max-w-md bg-white rounded-2xl border border-slate-200 shadow-xl shadow-slate-200/50 overflow-hidden p-8 sm:p-10 relative z-10">
        <div className="mb-6 space-y-2">
          <Image
            src="/ushuru-lens-logo.svg"
            alt="Ushuru Lens Logo"
            width={400}
            height={108}
            className="w-full max-w-[280px] h-auto object-contain -ml-1"
            priority
          />
          <h2 className="text-lg font-bold text-slate-900 pt-2">Set New Password</h2>
          <p className="text-xs text-slate-500 font-medium leading-relaxed">
            Please enter your new account password below.
          </p>
        </div>

        <Suspense
          fallback={
            <div className="py-12 text-center space-y-4">
              <Loader2 className="w-8 h-8 text-[#0e1734] animate-spin mx-auto" />
              <p className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Loading password reset...
              </p>
            </div>
          }
        >
          <ResetPasswordForm />
        </Suspense>

        <div className="mt-8 pt-4 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
          <span>&copy; {new Date().getFullYear()} UshuruLens</span>
          <span className="text-slate-400 font-medium">Powered by Techbiz</span>
        </div>
      </div>
    </div>
  );
}
