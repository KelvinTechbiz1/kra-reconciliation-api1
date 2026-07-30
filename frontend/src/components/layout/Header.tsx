"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { removeToken, getToken, API_BASE_URL, fetchWithAuth } from "@/lib/api";
import { LogOut, KeyRound, ChevronDown, ShieldCheck, BadgeCheck } from "lucide-react";
import Image from "next/image";
import { UserRecord } from "@/types/company";
import { ChangePasswordModal } from "./ChangePasswordModal";

export function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const [currentUser, setCurrentUser] = useState<UserRecord | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [changePasswordOpen, setChangePasswordOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function loadUser() {
      try {
        const res = await fetchWithAuth("/auth/me");
        if (res.ok) {
          const user = await res.json();
          setCurrentUser(user);
        }
      } catch {
        // Silently fail if not authenticated
      }
    }
    loadUser();
  }, []);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = async () => {
    setDropdownOpen(false);
    const token = getToken();
    if (token) {
      try {
        await fetch(`${API_BASE_URL}/auth/logout`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({}),
        });
      } catch {
        // Proceed with local cleanup even if backend call fails
      }
    }
    removeToken();
    router.push("/login");
  };

  const isActive = (route: string) => {
    return pathname.startsWith(route);
  };

  const initials = currentUser
    ? (currentUser.full_name || currentUser.username)
      .trim()
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2)
    : "US";

  return (
    <>
      <header className="bg-white border-b border-slate-200 px-8 flex justify-between items-center sticky top-0 z-40 h-16">
        <div className="flex items-center gap-8 h-full">
          <div className="flex flex-col justify-center shrink-0">
            <Link href="/sales" className="flex items-center">
              <Image
                src="/ushuru-lens-logo.svg"
                alt="Ushuru Lens Logo"
                width={220}
                height={60}
                className="w-36 sm:w-40 md:w-44 h-auto object-contain"
                priority
              />
            </Link>
            <span className="text-[10px] text-slate-400 font-medium leading-none inline-flex items-center gap-1 -mt-0.5 pl-[30.8%] whitespace-nowrap">
              powered by{" "}
              <a
                href="https://www.techbizgroup.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="font-bold text-slate-600 hover:text-[#0e1734] transition-colors underline decoration-slate-300 underline-offset-2"
              >
                Techbiz Group
              </a>
            </span>
          </div>
          <nav className="flex h-full">
            {[
              { href: "/sales", label: "Sales" },
              { href: "/purchases", label: "Purchases" },
              { href: "/settings", label: "Settings" },
            ].map(({ href, label }) => {
              const active = isActive(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={`relative h-full flex items-center px-4 text-sm font-medium transition-colors ${active
                    ? "text-[#0e1734] font-semibold"
                    : "text-slate-500 hover:text-slate-800"
                    }`}
                >
                  {label}
                  {active && (
                    <span className="absolute bottom-0 left-4 right-4 h-[2px] bg-[#0e1734] rounded-t-full" />
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Profile Avatar & Dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setDropdownOpen((prev) => !prev)}
            className="flex items-center gap-2.5 p-1.5 rounded-full hover:bg-slate-100/80 transition-all cursor-pointer border border-transparent hover:border-slate-200"
            aria-label="User Profile Menu"
          >
            {/* Avatar Circle */}
            <div suppressHydrationWarning className="w-8 h-8 rounded-full bg-[#0e1734] text-white font-bold text-xs flex items-center justify-center shadow-sm shrink-0 border border-slate-700/30">
              {initials}
            </div>

            {currentUser && (
              <div suppressHydrationWarning className="hidden md:flex flex-col text-left">
                <span className="text-xs font-semibold text-slate-800 leading-tight">
                  {currentUser.full_name || currentUser.username}
                </span>
                <span className="text-[10px] text-slate-500 capitalize leading-tight font-medium">
                  {currentUser.role}
                </span>
              </div>
            )}

            <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-200 ${dropdownOpen ? "rotate-180" : ""}`} />
          </button>

          {/* Dropdown Menu Popover */}
          {dropdownOpen && (
            <div className="absolute right-0 mt-2 w-64 bg-white rounded-2xl shadow-xl border border-slate-200/80 py-2 z-50 animate-in fade-in zoom-in-95 duration-150">
              {/* User Header Summary */}
              {currentUser && (
                <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/50">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-[#0e1734] text-white font-bold text-xs flex items-center justify-center shrink-0">
                      {initials}
                    </div>
                    <div className="overflow-hidden">
                      <p className="text-xs font-bold text-slate-900 truncate">
                        {currentUser.full_name || currentUser.username}
                      </p>
                      <p className="text-[11px] text-slate-500 truncate font-mono">
                        @{currentUser.username} {currentUser.email ? `· ${currentUser.email}` : ""}
                      </p>
                      <div className="mt-1 flex items-center gap-1.5">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${currentUser.role === "admin"
                          ? "bg-violet-100 text-violet-800"
                          : currentUser.role === "company_admin"
                            ? "bg-amber-100 text-amber-800"
                            : "bg-blue-100 text-blue-800"
                          }`}>
                          {currentUser.role === "admin" ? (
                            <ShieldCheck className="w-2.5 h-2.5" />
                          ) : currentUser.role === "company_admin" ? (
                            <ShieldCheck className="w-2.5 h-2.5" />
                          ) : (
                            <BadgeCheck className="w-2.5 h-2.5" />
                          )}
                          <span className="capitalize">{currentUser.role}</span>
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Menu Actions */}
              <div className="py-1">
                <button
                  onClick={() => {
                    setDropdownOpen(false);
                    setChangePasswordOpen(true);
                  }}
                  className="w-full text-left px-4 py-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50 flex items-center gap-2.5 transition-colors cursor-pointer"
                >
                  <KeyRound className="w-4 h-4 text-slate-400" />
                  <span>Change Password</span>
                </button>

                <div className="my-1 border-t border-slate-100" />

                <button
                  onClick={handleLogout}
                  className="w-full text-left px-4 py-2.5 text-xs font-semibold text-rose-600 hover:bg-rose-50 flex items-center gap-2.5 transition-colors cursor-pointer"
                >
                  <LogOut className="w-4 h-4 text-rose-500" />
                  <span>Sign Out</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </header>

      <ChangePasswordModal
        isOpen={changePasswordOpen}
        onClose={() => setChangePasswordOpen(false)}
      />
    </>
  );
}
