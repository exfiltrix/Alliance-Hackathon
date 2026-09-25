"use client";

import { USE_MOCK } from "@/lib/api";
import dictionary from "@/lib/dictionary";
import { useLanguage } from "@/lib/language-context";

export default function MockBanner() {
  const { t } = useLanguage();
  if (!USE_MOCK) return null;
  return (
    <p className="border-b border-amber-200 bg-amber-100 px-4 py-2 text-center text-xs font-medium text-amber-900 print:hidden">
      {t(dictionary.common.mockMode)}
    </p>
  );
}
