"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import { setToken, API_BASE_URL } from "@/lib/api";
import {
  User,
  Lock,
  Eye,
  EyeOff,
  ArrowRight,
  Loader2,
  ShieldAlert,
} from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        let errorMessage = "Invalid credentials. Please check your username and password.";
        try {
          const contentType = response.headers.get("content-type");
          if (contentType && contentType.includes("application/json")) {
            const data = await response.json();
            if (data?.detail) {
              errorMessage = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
            }
          }
        } catch {
          // Fall back to default error message if JSON parsing fails
        }
        throw new Error(errorMessage);
      }

      const data = await response.json();
      setToken(data.access_token);
      router.push("/");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unexpected network error occurred. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-slate-50 flex items-center justify-center p-4 sm:p-6 lg:p-8 relative overflow-hidden select-none">
      {/* Background Subtle Pattern */}
      <div className="absolute inset-0 bg-[radial-gradient(#e2e8f0_1px,transparent_1px)] [background-size:24px_24px] opacity-60 pointer-events-none" />

      <div className="w-full max-w-5xl bg-white rounded-2xl border border-slate-200 shadow-xl shadow-slate-200/50 overflow-hidden grid grid-cols-1 md:grid-cols-12 relative z-10">

        {/* Left Side: Simple Clean Login Form */}
        <div className="md:col-span-6 lg:col-span-5 p-6 sm:p-8 lg:p-10 bg-white flex flex-col justify-between">
          <div>
            <div className="mb-6 sm:mb-8 space-y-2">
              <Image
                src="/ushuru-lens-logo.svg"
                alt="Ushuru Lens Logo"
                width={400}
                height={108}
                className="w-full max-w-[260px] sm:max-w-[300px] md:max-w-[320px] h-auto object-contain -ml-1"
                priority
              />
              <p className="text-xs text-slate-500 font-medium">
                Sign in to your account
              </p>
            </div>

            {/* Error Banner */}
            {error && (
              <div className="mb-5 p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-xs flex items-start gap-2.5">
                <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <div className="font-medium">{error}</div>
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                  Username
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <User className="w-4 h-4" />
                  </div>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                    autoFocus
                    placeholder="Enter your username"
                    className="w-full pl-10 pr-4 py-2.5 h-11 rounded-xl border border-slate-200 bg-white text-slate-900 text-sm font-medium transition-all focus:outline-none focus:ring-4 focus:ring-[#0e1734]/10 focus:border-[#0e1734] placeholder:text-slate-400"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                    Password
                  </label>
                  <Link
                    href="/forgot-password"
                    className="text-xs font-semibold text-[#0e1734] hover:text-[#16224c] hover:underline transition-colors"
                  >
                    Forgot password?
                  </Link>
                </div>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    placeholder="••••••••"
                    className="w-full pl-10 pr-10 py-2.5 h-11 rounded-xl border border-slate-200 bg-white text-slate-900 text-sm font-medium transition-all focus:outline-none focus:ring-4 focus:ring-[#0e1734]/10 focus:border-[#0e1734] placeholder:text-slate-400 font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full h-11 bg-[#0e1734] hover:bg-[#16224c] active:bg-[#080d21] text-white rounded-xl font-semibold text-sm shadow-sm transition-all duration-150 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Signing in...</span>
                    </>
                  ) : (
                    <>
                      <span>Sign In</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>

          <div className="mt-8 pt-4 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
            <span>&copy; {new Date().getFullYear()} UshuruLens</span>
            <span className="text-slate-400 font-medium">
              Powered by{" "}
              <a
                href="https://www.techbizgroup.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="font-bold text-slate-600 hover:text-[#0e1734] underline decoration-slate-300 transition-colors"
              >
                Techbiz Group
              </a>
            </span>
          </div>
        </div>

        {/* Right Side: Image Only */}
        <div className="md:col-span-6 lg:col-span-7 min-h-[340px] md:min-h-[480px] relative overflow-hidden bg-[#131d25]">
          <Image
            src="/login2.png"
            alt="System Banner"
            fill
            priority
            className="object-cover object-left md:object-[8%_center]"
          />
        </div>

      </div>
    </div>
  );
}
