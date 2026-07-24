"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken, removeToken, API_BASE_URL } from "@/lib/api";
import { Header } from "@/components/layout/Header";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    fetch(`${API_BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) {
          removeToken();
          router.replace("/login");
        } else {
          setAuthorized(true);
        }
      })
      .catch(() => {
        removeToken();
        router.replace("/login");
      });
  }, [router]);

  if (!authorized) {
    return (
      <div suppressHydrationWarning className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div suppressHydrationWarning className="relative w-10 h-10">
          <div suppressHydrationWarning className="absolute inset-0 rounded-full border-4 border-slate-100"></div>
          <div suppressHydrationWarning className="absolute inset-0 rounded-full border-4 border-blue-600 border-t-transparent animate-spin"></div>
        </div>
      </div>
    );
  }

  return (
    <div suppressHydrationWarning className="h-screen bg-slate-50 flex flex-col overflow-hidden">
      <Header />
      <main className="flex-1 w-full px-8 py-4 flex flex-col min-h-0 overflow-hidden">
        {children}
      </main>
    </div>
  );
}
