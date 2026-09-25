"use client";

import Link from "next/link";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";
import {
  SealIcon,
  VerifyIcon,
  DetectiveIcon,
  CrashTestIcon,
  ShieldIcon,
  PassportIcon,
} from "@/components/icons";

const services = [
  { key: "seal", icon: SealIcon, href: "/seal" },
  { key: "verify", icon: VerifyIcon, href: "/verify" },
  { key: "detective", icon: DetectiveIcon, href: "/verify" },
  { key: "crashTest", icon: CrashTestIcon, href: "/crash-test" },
  { key: "shield", icon: ShieldIcon, href: "/verify" },
  { key: "passport", icon: PassportIcon, href: "/crash-test" },
] as const;

export default function Home() {
  const { t } = useLanguage();

  return (
    <div className="flex flex-1 flex-col">
      <Header />

      <main className="flex-1">
        {/* Hero */}
        <section className="mx-auto max-w-6xl px-6 pt-16 text-center sm:pt-24">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-white/70 px-4 py-1.5 text-xs font-medium text-muted">
            {t(dictionary.home.badge)}
          </span>

          <h1 className="mx-auto mt-6 max-w-3xl text-4xl font-semibold leading-tight tracking-tight sm:text-6xl">
            {t(dictionary.home.heroTitle)}
          </h1>

          <p className="mx-auto mt-5 max-w-xl text-base text-muted sm:text-lg">
            {t(dictionary.home.heroSubtitle)}
          </p>

          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/seal"
              className="w-full rounded-full bg-foreground px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-foreground/90 sm:w-auto"
            >
              {t(dictionary.home.ctaPrimary)}
            </Link>
            <Link
              href="/verify"
              className="w-full rounded-full bg-accent px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-accent/90 sm:w-auto"
            >
              {t(dictionary.home.ctaSecondary)}
            </Link>
          </div>

          {/* Glass mock card */}
          <div className="glass relative mx-auto mt-14 max-w-4xl rounded-3xl p-6 text-left shadow-xl shadow-accent/10 sm:p-10">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-foreground text-xs font-bold text-white">
                  M
                </span>
                <span className="text-sm font-semibold">MedSeal Gateway</span>
              </div>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-ok/10 px-3 py-1 text-xs font-medium text-ok">
                <span className="h-1.5 w-1.5 rounded-full bg-ok" />
                {t(dictionary.home.mockBadgeSealed)}
              </span>
            </div>

            <p className="mt-8 text-5xl font-semibold tracking-tight sm:text-7xl">
              Muhr
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl bg-white/80 p-4">
                <p className="text-xs text-muted">{t(dictionary.home.mockUid)}</p>
                <p className="mt-1 text-sm font-medium">
                  {t(dictionary.home.mockTiles)}
                </p>
              </div>
              <div className="rounded-2xl bg-white/80 p-4">
                <p className="text-xs text-muted">SHA-256 → Merkle → Ed25519</p>
                <p className="mt-1 text-sm font-medium">&lt; 50 ms / 512×512</p>
              </div>
            </div>
          </div>
        </section>

        {/* Services */}
        <section className="mx-auto max-w-6xl px-6 py-24">
          <div className="text-center">
            <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
              {t(dictionary.home.servicesTitle)}
            </h2>
            <p className="mx-auto mt-3 max-w-lg text-muted">
              {t(dictionary.home.servicesSubtitle)}
            </p>
          </div>

          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {services.map(({ key, icon: Icon, href }) => {
              const entry = dictionary.services[key];
              return (
                <Link
                  key={key}
                  href={href}
                  className="group flex flex-col rounded-2xl border border-border bg-surface p-6 transition-shadow hover:shadow-lg hover:shadow-accent/10"
                >
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-soft text-accent">
                    <Icon />
                  </span>
                  <h3 className="mt-4 text-base font-semibold">
                    {t(entry.title)}
                  </h3>
                  <p className="mt-2 flex-1 text-sm text-muted">{t(entry.desc)}</p>
                  <span className="mt-4 text-sm font-medium text-accent group-hover:underline">
                    {t(dictionary.home.open)} →
                  </span>
                </Link>
              );
            })}
          </div>

          <p className="mx-auto mt-12 max-w-2xl text-center text-sm text-muted">
            {t(dictionary.home.disclaimer)}
          </p>
        </section>
      </main>

      <Footer />
    </div>
  );
}
