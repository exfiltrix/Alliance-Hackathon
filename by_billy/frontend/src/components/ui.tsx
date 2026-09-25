"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";
import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-border bg-surface p-5 sm:p-6 ${className}`}>
      {children}
    </div>
  );
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "dark" | "accent" | "ghost";
};

export const buttonClass = (variant: ButtonProps["variant"] = "dark") =>
  `inline-flex items-center justify-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
    variant === "dark"
      ? "bg-foreground text-white hover:bg-foreground/90"
      : variant === "accent"
        ? "bg-accent text-white hover:bg-accent/90"
        : "border border-border bg-white text-foreground hover:bg-accent-soft/50"
  }`;

export function Button({ variant, className = "", ...props }: ButtonProps) {
  return <button {...props} className={`${buttonClass(variant)} ${className}`} />;
}

export function Spinner() {
  return (
    <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useLanguage();
  return (
    <div className="rounded-2xl border border-danger/30 bg-danger/5 p-4 text-sm text-danger">
      <p className="font-semibold">{t(dictionary.common.error)}</p>
      <p className="mt-1 break-words text-danger/80">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-3 font-medium underline">
          {t(dictionary.common.retry)}
        </button>
      )}
    </div>
  );
}

export function DoctorNote() {
  const { t } = useLanguage();
  return (
    <p className="flex items-center gap-2 text-sm text-muted">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 8v4M12 16h.01" />
      </svg>
      {t(dictionary.common.doctorDecides)}
    </p>
  );
}

export function Field({ label, value, mono }: { label: string; value: ReactNode; mono?: boolean }) {
  return (
    <div>
      <p className="text-xs text-muted">{label}</p>
      <p className={`mt-0.5 break-all text-sm font-medium ${mono ? "font-mono" : ""}`}>{value}</p>
    </div>
  );
}

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
