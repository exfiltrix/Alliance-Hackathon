"use client";

import type { ComponentType, ReactNode, SVGProps } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Header from "./Header";
import Footer from "./Footer";
import { FlowSteps, NextStepCard } from "./FlowSteps";
import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";
import { USE_MOCK } from "@/lib/api";
import type { FlowKey } from "@/lib/flow";

export default function PageShell({
  title,
  subtitle,
  icon: Icon,
  step,
  backHref = "/",
  children,
}: {
  title: string;
  subtitle?: string;
  icon?: ComponentType<SVGProps<SVGSVGElement>>;
  step?: FlowKey;
  backHref?: string;
  children?: ReactNode;
}) {
  const router = useRouter();
  const { t } = useLanguage();

  const goBack = () => {
    if (window.history.length > 1) router.back();
    else router.push(backHref);
  };

  return (
    <div className="flex flex-1 flex-col">
      <Header />
      <main id="main" tabIndex={-1} className="flex-1 outline-none">
        <section className="mx-auto max-w-5xl px-4 py-6 sm:px-6 sm:py-10">
          <div className="flex flex-wrap items-center gap-3 print:hidden">
            <button
              onClick={goBack}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-white/70 py-1.5 pl-2.5 pr-3.5 text-sm font-medium text-muted transition-colors hover:bg-white hover:text-foreground"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M15 18l-6-6 6-6" />
              </svg>
              {t(dictionary.common.back)}
            </button>
            <nav aria-label={t(dictionary.common.breadcrumb)} className="flex items-center gap-1.5 text-sm text-muted">
              <Link href="/" className="hover:text-foreground">
                {t(dictionary.nav.home)}
              </Link>
              <span>/</span>
              <span aria-current="page" className="text-foreground">{title}</span>
            </nav>
          </div>

          {step && (
            <div className="mt-6">
              <FlowSteps current={step} />
            </div>
          )}

          <div className="mt-8 flex items-start gap-4">
            {Icon && (
              <span className="hidden h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-foreground text-white shadow-lg shadow-foreground/10 sm:flex">
                <Icon width={26} height={26} />
              </span>
            )}
            <div>
              <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
              {subtitle && <p className="mt-2 max-w-2xl text-muted">{subtitle}</p>}
            </div>
          </div>

          {USE_MOCK && (
            <p className="mt-4 inline-flex items-center gap-2 rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800 print:hidden">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
              {t(dictionary.common.mockMode)}
            </p>
          )}

          <div className="fade-up mt-8">{children}</div>

          {step && <NextStepCard current={step} />}
        </section>
      </main>
      <Footer />
    </div>
  );
}
