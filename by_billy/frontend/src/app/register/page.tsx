"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import PageShell from "@/components/PageShell";
import { Button, Card, Segmented, buttonClass } from "@/components/ui";
import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";

const d = dictionary.register;
const e = dictionary.register.errors;

type AccountType = "individual" | "legal";

type FormState = {
  fullName: string;
  phone: string;
  email: string;
  password: string;
  confirmPassword: string;
  orgName: string;
  stir: string;
  contactName: string;
  position: string;
};

const EMPTY: FormState = {
  fullName: "",
  phone: "",
  email: "",
  password: "",
  confirmPassword: "",
  orgName: "",
  stir: "",
  contactName: "",
  position: "",
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE_RE = /^[+\d][\d\s()-]{6,}$/;
const STIR_RE = /^\d{9}$/;

function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium">{label}</span>
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-muted">{hint}</span>}
      {error && <span className="mt-1 block text-xs text-danger">{error}</span>}
    </label>
  );
}

const inputClass = (invalid?: string) =>
  `mt-2 w-full rounded-xl border bg-white px-3 py-2.5 text-sm outline-none focus:border-accent ${
    invalid ? "border-danger" : "border-border"
  }`;

export default function RegisterPage() {
  const { t } = useLanguage();
  const [type, setType] = useState<AccountType>("individual");
  const [form, setForm] = useState<FormState>(EMPTY);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [submitting, setSubmitting] = useState(false);
  const [successOrg, setSuccessOrg] = useState<string | null>(null);

  const set = (key: keyof FormState) => (ev: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: ev.target.value }));

  const validate = (): boolean => {
    const next: Partial<Record<keyof FormState, string>> = {};
    const required: (keyof FormState)[] =
      type === "individual"
        ? ["fullName", "phone", "email", "password", "confirmPassword"]
        : ["orgName", "stir", "contactName", "position", "phone", "email", "password", "confirmPassword"];

    for (const key of required) {
      if (!form[key].trim()) next[key] = t(e.required);
    }
    if (!next.email && !EMAIL_RE.test(form.email)) next.email = t(e.email);
    if (!next.phone && !PHONE_RE.test(form.phone)) next.phone = t(e.phone);
    if (type === "legal" && !next.stir && !STIR_RE.test(form.stir)) next.stir = t(e.stir);
    if (!next.password && form.password.length < 8) next.password = t(e.passwordShort);
    if (!next.confirmPassword && form.password !== form.confirmPassword) {
      next.confirmPassword = t(e.passwordMismatch);
    }

    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const submit = async (ev: FormEvent) => {
    ev.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    // Demo only: no auth endpoint exists in docs/API.md yet, so this just simulates a request.
    await new Promise((r) => setTimeout(r, 600));
    setSubmitting(false);
    setSuccessOrg(type === "legal" ? form.orgName : "");
  };

  const reset = () => {
    setForm(EMPTY);
    setErrors({});
    setSuccessOrg(null);
  };

  if (successOrg !== null) {
    const message =
      type === "legal" ? t(d.successLegal).replace("{org}", successOrg) : t(d.successIndividual);
    return (
      <PageShell title={t(d.title)} subtitle={t(d.subtitle)}>
        <Card className="max-w-lg space-y-4 text-center">
          <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-ok/10 text-ok">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12l5 5L20 7" />
            </svg>
          </span>
          <h2 className="text-xl font-semibold">{t(d.successTitle)}</h2>
          <p className="text-sm text-muted">{message}</p>
          <div className="flex flex-col gap-3 pt-2 sm:flex-row sm:justify-center">
            <Link href="/seal" className={buttonClass("dark")}>
              {t(d.goSeal)}
            </Link>
            <Button variant="ghost" onClick={reset}>
              {t(d.again)}
            </Button>
          </div>
        </Card>
      </PageShell>
    );
  }

  return (
    <PageShell title={t(d.title)} subtitle={t(d.subtitle)}>
      <form onSubmit={submit} noValidate className="max-w-lg space-y-6">
        <div>
          <p className="mb-2 text-sm font-medium">{t(d.typeLabel)}</p>
          <Segmented
            label={t(d.typeLabel)}
            value={type}
            onChange={setType}
            options={[
              { value: "individual", label: t(d.individual) },
              { value: "legal", label: t(d.legal) },
            ]}
          />
          <p className="mt-2 text-xs text-muted">{t(type === "individual" ? d.individualHint : d.legalHint)}</p>
        </div>

        <Card className="space-y-4">
          {type === "legal" && (
            <>
              <Field label={t(d.orgName)} hint={t(d.orgNameHint)} error={errors.orgName}>
                <input value={form.orgName} onChange={set("orgName")} className={inputClass(errors.orgName)} />
              </Field>
              <Field label={t(d.stir)} error={errors.stir}>
                <input
                  value={form.stir}
                  onChange={set("stir")}
                  inputMode="numeric"
                  maxLength={9}
                  className={inputClass(errors.stir)}
                />
              </Field>
              <Field label={t(d.contactName)} error={errors.contactName}>
                <input value={form.contactName} onChange={set("contactName")} className={inputClass(errors.contactName)} />
              </Field>
              <Field label={t(d.position)} error={errors.position}>
                <input value={form.position} onChange={set("position")} className={inputClass(errors.position)} />
              </Field>
            </>
          )}

          {type === "individual" && (
            <Field label={t(d.fullName)} error={errors.fullName}>
              <input value={form.fullName} onChange={set("fullName")} className={inputClass(errors.fullName)} />
            </Field>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t(d.phone)} error={errors.phone}>
              <input
                value={form.phone}
                onChange={set("phone")}
                type="tel"
                placeholder="+998 90 123 45 67"
                className={inputClass(errors.phone)}
              />
            </Field>
            <Field label={t(d.email)} error={errors.email}>
              <input value={form.email} onChange={set("email")} type="email" className={inputClass(errors.email)} />
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t(d.password)} error={errors.password}>
              <input
                value={form.password}
                onChange={set("password")}
                type="password"
                autoComplete="new-password"
                className={inputClass(errors.password)}
              />
            </Field>
            <Field label={t(d.confirmPassword)} error={errors.confirmPassword}>
              <input
                value={form.confirmPassword}
                onChange={set("confirmPassword")}
                type="password"
                autoComplete="new-password"
                className={inputClass(errors.confirmPassword)}
              />
            </Field>
          </div>
        </Card>

        <p className="text-xs text-muted">{t(d.demoNote)}</p>

        <Button type="submit" disabled={submitting} className="w-full sm:w-auto">
          {submitting ? t(d.submitting) : t(d.submit)}
        </Button>
      </form>
    </PageShell>
  );
}
