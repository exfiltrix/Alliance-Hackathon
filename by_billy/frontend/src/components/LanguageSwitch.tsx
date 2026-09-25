"use client";

import { LANGS } from "@/lib/dictionary";
import dictionary from "@/lib/dictionary";
import { useLanguage } from "@/lib/language-context";

export default function LanguageSwitch() {
  const { lang, setLang, t } = useLanguage();

  return (
    <div
      role="group"
      aria-label={t(dictionary.nav.language)}
      className="flex items-center gap-0.5 rounded-full border border-border bg-white/70 p-1 text-xs font-semibold"
    >
      {LANGS.map(({ code, label, name }) => (
        <button
          key={code}
          type="button"
          lang={code}
          onClick={() => setLang(code)}
          aria-pressed={lang === code}
          aria-label={name}
          title={name}
          className={`rounded-full px-2 py-1 transition-colors ${
            lang === code ? "bg-foreground text-white" : "text-muted hover:text-foreground"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
