"use client";

import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import Header from "./Header";
import Footer from "./Footer";
import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";
import { USE_MOCK } from "@/lib/api";

export default function PageShell({
  title,
  subtitle,
  backHref = "/",
  children,
}: {
  title: string;
  subtitle?: string;
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
      <main className="flex-1">
        <section className="mx-auto max-w-5xl px-4 py-8 sm:px-6 sm:py-12">
          <button
            onClick={goBack}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-white/70 px-3.5 py-1.5 text-sm font-medium text-muted transition-colors hover:text-foreground print:hidden"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <path d="M15 18l-6-6 6-6" />
            </svg>
            {t(dictionary.common.back)}
          </button>

          <h1 className="mt-6 text-3xl font-semibold tracking-tight sm:text-4xl">
            {title}
          </h1>
          {subtitle && <p className="mt-3 max-w-2xl text-muted">{subtitle}</p>}

          {USE_MOCK && (
            <p className="mt-4 inline-block rounded-lg bg-amber-100 px-3 py-1.5 text-xs font-medium text-amber-800 print:hidden">
              {t(dictionary.common.mockMode)}
            </p>
          )}

          <div className="mt-8">{children}</div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
