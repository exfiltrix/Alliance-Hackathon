"use client";

import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";
import { SealIcon } from "./icons";

export default function Footer() {
  const { t } = useLanguage();

  return (
    <footer className="border-t border-border/60 bg-background">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-10 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-foreground text-white">
            <SealIcon width={16} height={16} />
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
