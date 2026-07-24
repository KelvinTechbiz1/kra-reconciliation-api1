"use client";

import { Check, X, ShieldAlert } from "lucide-react";
import { validatePasswordPolicy } from "@/lib/passwordPolicy";

interface PasswordStrengthIndicatorProps {
  password: string;
  showDetails?: boolean;
}

export function PasswordStrengthIndicator({
  password,
  showDetails = true,
}: PasswordStrengthIndicatorProps) {
  const { checks, isValid } = validatePasswordPolicy(password);

  const totalPassed = Object.values(checks).filter(Boolean).length;
  const progressPercent = (totalPassed / 5) * 100;

  const getStrengthColor = () => {
    if (totalPassed <= 1) return "bg-rose-500";
    if (totalPassed <= 3) return "bg-amber-500";
    if (totalPassed === 4) return "bg-blue-500";
    return "bg-emerald-500";
  };

  const getStrengthLabel = () => {
    if (password.length === 0) return "Enter password";
    if (totalPassed <= 1) return "Weak";
    if (totalPassed <= 3) return "Fair";
    if (totalPassed === 4) return "Good";
    return "Strong (Policy Compliant)";
  };

  const rules = [
    { key: "length", label: "Minimum 8 characters", met: checks.length },
    { key: "uppercase", label: "At least 1 uppercase letter (A-Z)", met: checks.uppercase },
    { key: "lowercase", label: "At least 1 lowercase letter (a-z)", met: checks.lowercase },
    { key: "number", label: "At least 1 number (0-9)", met: checks.number },
    { key: "special", label: "At least 1 special character (!@#$%^&*)", met: checks.special },
  ];

  return (
    <div className="space-y-2 mt-2 select-none">
      {/* Strength Bar */}
      <div className="space-y-1">
        <div className="flex justify-between items-center text-[11px]">
          <span className="font-semibold text-slate-500">Password Policy Strength</span>
          <span
            className={`font-bold ${
              totalPassed <= 1
                ? "text-rose-600"
                : totalPassed <= 3
                ? "text-amber-600"
                : totalPassed === 4
                ? "text-blue-600"
                : "text-emerald-600"
            }`}
          >
            {getStrengthLabel()}
          </span>
        </div>
        <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
          <div
            className={`h-full transition-all duration-300 ${getStrengthColor()}`}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Rules Checklist */}
      {showDetails && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 pt-1 text-[11px]">
          {rules.map((rule) => (
            <div
              key={rule.key}
              className={`flex items-center gap-1.5 transition-colors ${
                rule.met ? "text-emerald-700 font-medium" : "text-slate-500"
              }`}
            >
              {rule.met ? (
                <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
              ) : (
                <X className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              )}
              <span>{rule.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
