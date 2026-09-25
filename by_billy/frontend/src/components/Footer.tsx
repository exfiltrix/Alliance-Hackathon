"use client";

import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";

export default function Footer() {
  const { t } = useLanguage();

  return (
    <footer className="border-t border-border/60 bg-background">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-10 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-foreground text-xs font-bold text-white">
            M
          </span>
          <div>
            <p className="text-sm font-semibold">MedSeal</p>
            <p className="text-xs text-muted">{t(dictionary.home.footerTagline)}</p>
          </div>
        </div>
        <p className="text-xs text-muted">
          National AI Hackathon · Namangan 2026 · Task №6
        </p>
      </div>
    </footer>
  );
}
