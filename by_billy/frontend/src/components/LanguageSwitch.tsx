"use client";

import { LANGS } from "@/lib/dictionary";
import { useLanguage } from "@/lib/language-context";

export default function LanguageSwitch() {
  const { lang, setLang } = useLanguage();

  return (
    <div className="flex items-center gap-1 rounded-full border border-border bg-white/70 p-1 text-xs font-medium">
      {LANGS.map(({ code, label }) => (
        <button
          key={code}
          onClick={() => setLang(code)}
          className={`rounded-full px-2.5 py-1 transition-colors ${
            lang === code
              ? "bg-foreground text-white"
              : "text-muted hover:text-foreground"
          }`}
          aria-pressed={lang === code}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
