"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import PageShell from "@/components/PageShell";
import { Button, Card, Segmented } from "@/components/ui";
import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";
import { login, type AccountType } from "@/lib/auth";

const d = dictionary.login;
const r = dictionary.register;

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LoginPage() {
  const { t } = useLanguage();
  const router = useRouter();
  const [type, setType] = useState<AccountType>("individual");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ name?: string; email?: string; password?: string }>({});
  const [submitting, setSubmitting] = useState(false);

  const submit = async (ev: FormEvent) => {
    ev.preventDefault();
    const next: typeof errors = {};
    if (!name.trim()) next.name = t(r.errors.required);
    if (!EMAIL_RE.test(email)) next.email = t(r.errors.email);
    if (!password.trim()) next.password = t(r.errors.required);
    setErrors(next);
    if (Object.keys(next).length) return;

    setSubmitting(true);
    // Demo only: no user database yet, so this can't verify a password — see dictionary.login.demoNote.
    await new Promise((res) => setTimeout(res, 400));
    setSubmitting(false);
    login(type === "legal" ? { type: "legal", name: name.trim(), org: name.trim() } : { type: "individual", name: name.trim() });
    // A doctor's home is the inbox: images arrive already checked, only red ones need a look.
    router.push(type === "legal" ? "/dashboard" : "/inbox");
  };

  return (
    <PageShell title={t(d.title)} subtitle={t(d.subtitle)} publicPage>
      <form onSubmit={submit} noValidate className="max-w-md space-y-6">
        <Segmented
          label={t(r.typeLabel)}
          value={type}
          onChange={setType}
          options={[
            { value: "individual", label: t(r.individual) },
            { value: "legal", label: t(r.legal) },
          ]}
        />

        <Card className="space-y-4">
          <label className="block">
            <span className="text-sm font-medium">{type === "legal" ? t(r.orgName) : t(d.nameLabel)}</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={`mt-2 w-full rounded-xl border bg-white px-3 py-2.5 text-sm outline-none focus:border-accent ${errors.name ? "border-danger" : "border-border"}`}
            />
            {errors.name && <span className="mt-1 block text-xs text-danger">{errors.name}</span>}
          </label>

          <label className="block">
            <span className="text-sm font-medium">{t(r.email)}</span>
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              className={`mt-2 w-full rounded-xl border bg-white px-3 py-2.5 text-sm outline-none focus:border-accent ${errors.email ? "border-danger" : "border-border"}`}
            />
            {errors.email && <span className="mt-1 block text-xs text-danger">{errors.email}</span>}
          </label>

          <label className="block">
            <span className="text-sm font-medium">{t(r.password)}</span>
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              autoComplete="current-password"
              className={`mt-2 w-full rounded-xl border bg-white px-3 py-2.5 text-sm outline-none focus:border-accent ${errors.password ? "border-danger" : "border-border"}`}
            />
            {errors.password && <span className="mt-1 block text-xs text-danger">{errors.password}</span>}
          </label>
        </Card>

        <p className="text-xs text-muted">{t(d.demoNote)}</p>

        <div className="flex flex-wrap items-center gap-4">
          <Button type="submit" disabled={submitting}>
            {submitting ? t(d.submitting) : t(d.submit)}
          </Button>
          <span className="text-sm text-muted">
            {t(d.noAccount)}{" "}
            <Link href="/register" className="font-medium text-accent">
              {t(r.title)}
            </Link>
          </span>
        </div>
      </form>
    </PageShell>
  );
}
