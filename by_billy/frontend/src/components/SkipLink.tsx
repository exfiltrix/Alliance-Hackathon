"use client";

import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";

export default function SkipLink() {
  const { t } = useLanguage();
  return (
    <a
      href="#main"
      className="sr-only rounded-full bg-foreground px-4 py-2 text-sm font-medium text-white focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60]"
    >
      {t(dictionary.nav.skip)}
    </a>
  );
}
