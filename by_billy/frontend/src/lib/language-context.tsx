"use client";

import { createContext, useContext, useMemo, useSyncExternalStore, type ReactNode } from "react";
import { DEFAULT_LANG, LANGS, type Lang } from "./dictionary";
import { LANG_KEY } from "./a11y-init";

type Entry = Record<Lang, string>;

type LanguageContextValue = {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (entry: Entry) => string;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

const STORAGE_KEY = LANG_KEY;
const listeners = new Set<() => void>();
let memoryLang: Lang = DEFAULT_LANG;

function subscribe(cb: () => void) {
  listeners.add(cb);
  window.addEventListener("storage", cb);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", cb);
  };
}

function getSnapshot(): Lang {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (LANGS.some((l) => l.code === stored)) return stored as Lang;
  } catch {
    // storage blocked — fall back to in-memory value
  }
  return memoryLang;
}

function setLang(next: Lang) {
  memoryLang = next;
  try {
    window.localStorage.setItem(STORAGE_KEY, next);
  } catch {
    // ignore
  }
  document.documentElement.lang = next;
  listeners.forEach((l) => l());
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const lang = useSyncExternalStore(subscribe, getSnapshot, () => DEFAULT_LANG);

  const value = useMemo<LanguageContextValue>(
    () => ({ lang, setLang, t: (entry: Entry) => entry[lang] }),
    [lang]
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage must be used within LanguageProvider");
  return ctx;
}
