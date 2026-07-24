"use client";

import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  useEffect,
  ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";

type ToastVariant = "error" | "success" | "info";

interface Toast {
  id: number;
  message: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  notify: (message: string, variant?: ToastVariant) => void;
  dismiss: (id: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [mounted, setMounted] = useState(false);
  const nextId = useRef(1);

  useEffect(() => {
    setMounted(true);
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const notify = useCallback((message: string, variant: ToastVariant = "error") => {
    const id = nextId.current++;
    setToasts((prev) => [...prev, { id, message, variant }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  }, []);

  return (
    <ToastContext.Provider value={{ notify, dismiss }}>
      {children}
      {mounted &&
        createPortal(
          <div
            suppressHydrationWarning
            className="fixed top-5 right-5 z-[9999] flex flex-col gap-2.5 w-96 max-w-[calc(100vw-2.5rem)] pointer-events-none"
          >
            {toasts.map((t) => {
              const isError = t.variant === "error";
              const isSuccess = t.variant === "success";

              return (
                <div
                  key={t.id}
                  className={`pointer-events-auto flex items-start gap-3 p-4 rounded-xl shadow-2xl border transition-all duration-200 animate-in fade-in slide-in-from-top-3 bg-white ${
                    isError
                      ? "border-red-200 text-red-950 ring-1 ring-red-500/10"
                      : isSuccess
                      ? "border-emerald-200 text-emerald-950 ring-1 ring-emerald-500/10"
                      : "border-slate-200 text-slate-900 ring-1 ring-slate-500/10"
                  }`}
                >
                  <div className="shrink-0 mt-0.5">
                    {isError && <AlertCircle className="w-5 h-5 text-red-600" />}
                    {isSuccess && <CheckCircle2 className="w-5 h-5 text-emerald-600" />}
                    {!isError && !isSuccess && <Info className="w-5 h-5 text-blue-600" />}
                  </div>

                  <div className="flex-1 text-xs font-medium leading-relaxed break-words">
                    {t.message}
                  </div>

                  <button
                    onClick={() => dismiss(t.id)}
                    className="shrink-0 text-slate-400 hover:text-slate-600 p-0.5 rounded-md hover:bg-slate-100 transition-colors cursor-pointer"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              );
            })}
          </div>,
          document.body
        )}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}
