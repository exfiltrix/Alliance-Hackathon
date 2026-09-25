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
  ArrowRightIcon,
} from "@/components/icons";
import { FLOW } from "@/lib/flow";

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

      <main id="main" tabIndex={-1} className="flex-1 outline-none">
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
          <div className="glass relative mx-auto mt-14 max-w-4xl overflow-hidden rounded-[2rem] p-6 text-left shadow-2xl shadow-accent/15 sm:p-10">
            <div className="pointer-events-none absolute -left-16 top-10 h-64 w-64 rounded-full bg-accent/30 blur-3xl" />
            <div className="pointer-events-none absolute -right-10 -top-10 h-56 w-56 rounded-full bg-indigo-300/40 blur-3xl" />

            <div className="relative flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-foreground text-white">
                  <SealIcon width={16} height={16} />
                </span>
                <span className="text-sm font-semibold">MedSeal Gateway</span>
              </div>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-ok/10 px-3 py-1 text-xs font-medium text-ok">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ok" />
                {t(dictionary.home.mockBadgeSealed)}
              </span>
            </div>

            <p className="relative mt-8 text-6xl font-semibold tracking-tighter sm:text-8xl">
              MedSeal
            </p>

            <div className="relative mt-8 grid gap-3 sm:grid-cols-3">
              <div className="rounded-2xl bg-white/85 p-4 shadow-sm">
                <p className="text-xs text-muted">{t(dictionary.home.mockUid)}</p>
                <p className="mt-1 text-sm font-medium">{t(dictionary.home.mockTiles)}</p>
              </div>
              <div className="rounded-2xl bg-foreground p-4 text-white shadow-sm">
                <p className="text-xs text-white/60">SHA-256 → Merkle → Ed25519</p>
                <p className="mt-1 text-sm font-medium">&lt; 50 ms / 512×512</p>
              </div>
              <Link
                href="/verify"
                className="group flex items-center justify-between gap-3 rounded-2xl bg-white/85 p-4 shadow-sm transition-colors hover:bg-white"
              >
                <span>
                  <span className="block text-xs text-muted">{t(dictionary.nav.verify)}</span>
                  <span className="block text-sm font-medium text-ok">
                    {t(dictionary.verify.status.authentic.title)}
                  </span>
                </span>
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-white transition-transform group-hover:translate-x-0.5">
                  <ArrowRightIcon width={16} height={16} />
                </span>
              </Link>
            </div>
          </div>
        </section>

        {/* How it works */}
        <section className="mx-auto max-w-6xl px-6 pt-24">
          <div className="text-center">
            <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
              {t(dictionary.home.howTitle)}
            </h2>
            <p className="mx-auto mt-3 max-w-lg text-muted">{t(dictionary.home.howSubtitle)}</p>
          </div>

          <ol className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {FLOW.map((step, i) => {
              const Icon = step.icon;
              return (
                <li key={step.key}>
                  <Link
                    href={step.href}
                    className="group relative flex h-full flex-col rounded-2xl border border-white/70 bg-white/60 p-6 backdrop-blur transition-all hover:-translate-y-0.5 hover:bg-white hover:shadow-xl hover:shadow-accent/10"
                  >
                    <span className="flex items-center justify-between">
                      <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-foreground text-white">
                        <Icon />
                      </span>
                      <span className="text-4xl font-semibold text-accent/15">0{i + 1}</span>
                    </span>
                    <span className="mt-5 text-xs font-medium uppercase tracking-wide text-muted">
                      {t(dictionary.home.stepLabel)} {i + 1}
                    </span>
                    <span className="mt-1 text-lg font-semibold">
                      {t(dictionary.flow.steps[step.key].title)}
                    </span>
                    <span className="mt-1 flex-1 text-sm text-muted">
                      {t(dictionary.flow.steps[step.key].desc)}
                    </span>
                    <ArrowRightIcon className="mt-4 text-muted transition-transform group-hover:translate-x-1 group-hover:text-accent" />
                  </Link>
                </li>
              );
            })}
          </ol>
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
