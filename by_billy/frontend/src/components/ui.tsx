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

export function Button({ variant, className = "", type = "button", ...props }: ButtonProps) {
  return <button type={type} {...props} className={`${buttonClass(variant)} ${className}`} />;
}

export function Segmented<T extends string | number>({
  options,
  value,
  onChange,
  disabled,
  label,
}: {
  label: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
  disabled?: boolean;
}) {
  return (
    <div role="group" aria-label={label} className="flex gap-1 rounded-xl bg-slate-100 p-1">
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          aria-pressed={value === o.value}
          disabled={disabled}
          onClick={() => onChange(o.value)}
          className={`flex-1 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
            value === o.value ? "bg-white text-foreground shadow-sm" : "text-muted hover:text-foreground"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function ProgressBar({ value, label, color = "bg-accent" }: { value: number; label: string; color?: string }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      className="h-2 overflow-hidden rounded-full bg-slate-100"
    >
      <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Spinner() {
  return (
    <span aria-hidden className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useLanguage();
  return (
    <div role="alert" className="rounded-2xl border border-danger/30 bg-danger/5 p-4 text-sm text-danger">
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
      <svg aria-hidden width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
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
