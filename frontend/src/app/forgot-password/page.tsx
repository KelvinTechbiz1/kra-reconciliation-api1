"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { API_BASE_URL } from "@/lib/api";
import {
  Mail,
  ArrowLeft,
  ArrowRight,
  Loader2,
  CheckCircle2,
  ShieldAlert,
} from "lucide-react";

export default function ForgotPasswordPage() {
  const [identifier, setIdentifier] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/auth/forgot-password`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ identifier: identifier.trim() }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to process request. Please try again.");
      }

      setSubmitted(true);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unexpected error occurred. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-slate-50 flex items-center justify-center p-4 sm:p-6 lg:p-8 relative overflow-hidden select-none">
      {/* Background Pattern */}
      <div className="absolute inset-0 bg-[radial-gradient(#e2e8f0_1px,transparent_1px)] [background-size:24px_24px] opacity-60 pointer-events-none" />

      <div className="w-full max-w-md bg-white rounded-2xl border border-slate-200 shadow-xl shadow-slate-200/50 overflow-hidden p-8 sm:p-10 relative z-10">

        {/* Logo */}
        <div className="mb-6 space-y-2">
          <Image
            src="/ushuru-lens-logo.svg"
            alt="Ushuru Lens Logo"
            width={400}
            height={108}
            className="w-full max-w-[280px] h-auto object-contain -ml-1"
            priority
          />
          <h2 className="text-lg font-bold text-slate-900 pt-2">
            Reset Your Password
          </h2>
          <p className="text-xs text-slate-500 font-medium leading-relaxed">
            Enter your username or email address below and we will send you a link to reset your password.
          </p>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mb-6 p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-xs flex items-start gap-2.5">
            <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <div className="font-medium">{error}</div>
          </div>
        )}

        {submitted ? (
          <div className="space-y-6 text-center animate-in fade-in zoom-in-95 duration-200">
            <div className="mx-auto w-12 h-12 bg-emerald-100 rounded-2xl flex items-center justify-center text-emerald-600">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div className="space-y-2">
              <h3 className="text-sm font-bold text-slate-900">Check Your Email</h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                If an account matching <strong className="text-slate-900">{identifier}</strong> exists, a password reset link has been dispatched to your registered email address.
              </p>
            </div>
            <div className="pt-2">
              <Link
                href="/login"
                className="w-full h-11 bg-[#0e1734] hover:bg-[#16224c] text-white rounded-xl font-semibold text-sm shadow-sm transition-all duration-150 flex items-center justify-center gap-2"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Return to Sign In</span>
              </Link>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                Username or Email Address *
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  required
                  autoFocus
                  placeholder="e.g. john.doe or john@company.com"
                  className="w-full pl-10 pr-4 py-2.5 h-11 rounded-xl border border-slate-200 bg-white text-slate-900 text-sm font-medium transition-all focus:outline-none focus:ring-4 focus:ring-[#0e1734]/10 focus:border-[#0e1734] placeholder:text-slate-400"
                />
              </div>
            </div>

            <div className="pt-2 space-y-3">
              <button
                type="submit"
                disabled={loading || !identifier.trim()}
                className="w-full h-11 bg-[#0e1734] hover:bg-[#16224c] active:bg-[#080d21] text-white rounded-xl font-semibold text-sm shadow-sm transition-all duration-150 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Sending Reset Link...</span>
                  </>
                ) : (
                  <>
                    <span>Send Reset Email</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>

              <Link
                href="/login"
                className="w-full h-11 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-xl font-semibold text-sm transition-all flex items-center justify-center gap-2"
              >
                <ArrowLeft className="w-4 h-4 text-slate-500" />
                <span>Back to Sign In</span>
              </Link>
            </div>
          </form>
        )}

        <div className="mt-8 pt-4 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
          <span>&copy; {new Date().getFullYear()} UshuruLens</span>
          <span className="text-slate-400 font-medium">Powered by Techbiz Group</span>
        </div>

      </div>
    </div>
  );
}
