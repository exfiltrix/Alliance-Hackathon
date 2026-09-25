"use client";

import { useEffect, useId, useRef, useState, useSyncExternalStore } from "react";
import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";
import { updateA11y, useA11y, type A11ySettings } from "@/lib/a11y";
import { speak, speechSupported, stopSpeech } from "@/lib/speech";
import { AccessibilityIcon, SpeakerIcon } from "./icons";

const d = dictionary.a11y;

const noop = () => () => {};

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium hover:bg-slate-100"
    >
      {label}
      <span
        aria-hidden
        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${checked ? "bg-accent" : "bg-slate-300"}`}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${checked ? "left-[22px]" : "left-0.5"}`}
        />
      </span>
    </button>
  );
}

function useSpeechReader(enabled: boolean) {
  const { lang } = useLanguage();

  useEffect(() => {
    if (!enabled || !speechSupported()) return;
    let lastPointer = 0;

    const textOf = (el: Element | null) => {
      if (!el) return "";
      const labelled = el.closest("[aria-label]")?.getAttribute("aria-label");
      const node = el.closest("a, button, h1, h2, h3, p, li, label, td, th, [role=switch]") ?? el;
      const text = (node as HTMLElement).innerText?.trim() || labelled || "";
      return text.slice(0, 600);
    };

    const onPointerDown = () => {
      lastPointer = Date.now();
    };
    const onClick = (e: MouseEvent) => {
      const selection = window.getSelection()?.toString().trim();
      speak(selection || textOf(e.target as Element), lang);
    };
    const onFocus = (e: FocusEvent) => {
      if (Date.now() - lastPointer < 600) return;
      speak(textOf(e.target as Element), lang);
    };

    document.addEventListener("pointerdown", onPointerDown, true);
    document.addEventListener("click", onClick, true);
    document.addEventListener("focusin", onFocus, true);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown, true);
      document.removeEventListener("click", onClick, true);
      document.removeEventListener("focusin", onFocus, true);
      stopSpeech();
    };
  }, [enabled, lang]);
}

export default function AccessibilityPanel() {
  const { t, lang } = useLanguage();
  const settings = useA11y();
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const canSpeak = useSyncExternalStore(noop, speechSupported, () => false);

  useSpeechReader(settings.speech);

  useEffect(() => {
    if (!open) return;
    panelRef.current?.querySelector<HTMLElement>("button")?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    const onDown = (e: PointerEvent) => {
      const target = e.target as Node;
      if (!panelRef.current?.contains(target) && !triggerRef.current?.contains(target)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onDown);
    };
  }, [open]);

  const set = (patch: Partial<A11ySettings>) => updateA11y(patch);

  const close = () => {
    setOpen(false);
    triggerRef.current?.focus();
  };

  const readPage = () => {
    const main = document.getElementById("main");
    if (main) speak(main.innerText, lang);
  };

  const optionClass = (active: boolean) =>
    `flex-1 rounded-xl border-2 px-2 py-2 text-sm font-semibold transition-colors ${
      active ? "border-accent bg-accent-soft text-accent" : "border-transparent bg-slate-100 text-foreground hover:bg-slate-200"
    }`;

  return (
    <div className="relative">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={t(d.open)}
        title={t(d.open)}
        className={`flex h-9 items-center gap-2 rounded-full border px-2.5 text-sm font-medium transition-colors ${
          open ? "border-foreground bg-foreground text-white" : "border-border bg-white/70 hover:bg-white"
        }`}
      >
        <AccessibilityIcon width={18} height={18} />
        <span className="hidden xl:inline">{t(d.open)}</span>
      </button>

      {open && (
        <div
          ref={panelRef}
          role="dialog"
          aria-labelledby={titleId}
          className="fixed inset-x-3 top-16 z-50 max-h-[calc(100dvh-5rem)] overflow-y-auto rounded-2xl border border-border bg-white p-4 text-foreground shadow-2xl sm:absolute sm:inset-x-auto sm:right-0 sm:top-full sm:mt-2 sm:w-[22rem]"
        >
          <div className="flex items-center justify-between">
            <h2 id={titleId} className="text-base font-semibold">
              {t(d.title)}
            </h2>
            <button
              type="button"
              onClick={close}
              aria-label={t(d.close)}
              className="flex h-8 w-8 items-center justify-center rounded-full hover:bg-slate-100"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>
          </div>

          <fieldset className="mt-4">
            <legend className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{t(d.fontSize)}</legend>
            <div className="flex gap-2">
              {([0, 1, 2] as const).map((size) => (
                <button
                  key={size}
                  type="button"
                  aria-pressed={settings.font === size}
                  aria-label={t(d.fontSizes[size])}
                  onClick={() => set({ font: size })}
                  className={optionClass(settings.font === size)}
                >
                  <span style={{ fontSize: `${0.875 + size * 0.2}rem` }}>A{"+".repeat(size)}</span>
                </button>
              ))}
            </div>
          </fieldset>

          <fieldset className="mt-4">
            <legend className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{t(d.colors)}</legend>
            <div className="flex gap-2">
              {(
                [
                  ["normal", "bg-[#eef1fb] text-[#12131a]"],
                  ["high", "bg-white text-black ring-2 ring-black"],
                  ["invert", "bg-black text-white"],
                ] as const
              ).map(([mode, swatch]) => (
                <button
                  key={mode}
                  type="button"
                  aria-pressed={settings.contrast === mode}
                  onClick={() => set({ contrast: mode })}
                  className={`${optionClass(settings.contrast === mode)} flex flex-col items-center gap-1.5`}
                >
                  <span aria-hidden className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${swatch}`}>
                    A
                  </span>
                  <span className="text-xs leading-tight">{t(d.contrast[mode])}</span>
                </button>
              ))}
            </div>
          </fieldset>

          <div className="mt-4 space-y-0.5 border-t border-border pt-3">
            <Toggle label={t(d.grayscale)} checked={settings.grayscale} onChange={(v) => set({ grayscale: v })} />
            <Toggle label={t(d.spacing)} checked={settings.spacing} onChange={(v) => set({ spacing: v })} />
            <Toggle label={t(d.links)} checked={settings.links} onChange={(v) => set({ links: v })} />
            <Toggle label={t(d.motion)} checked={settings.reduceMotion} onChange={(v) => set({ reduceMotion: v })} />
          </div>

          <div className="mt-3 border-t border-border pt-3">
            {canSpeak ? (
              <>
                <Toggle
                  label={t(d.speech)}
                  checked={settings.speech}
                  onChange={(v) => {
                    if (!v) stopSpeech();
                    set({ speech: v });
                  }}
                />
                <p className="px-3 text-xs text-muted">{t(d.speechHint)}</p>
                <div className="mt-3 flex gap-2 px-1">
                  <button
                    type="button"
                    onClick={readPage}
                    className="flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-foreground px-3 py-2 text-sm font-medium text-white hover:bg-foreground/90"
                  >
                    <SpeakerIcon width={16} height={16} />
                    {t(d.readPage)}
                  </button>
                  <button
                    type="button"
                    onClick={stopSpeech}
                    className="rounded-xl border border-border px-3 py-2 text-sm font-medium hover:bg-slate-100"
                  >
                    {t(d.stop)}
                  </button>
                </div>
              </>
            ) : (
              <p className="px-3 text-xs text-muted">{t(d.speechUnsupported)}</p>
            )}
          </div>

          <button
            type="button"
            onClick={() => {
              stopSpeech();
              updateA11y(null);
            }}
            className="mt-4 w-full rounded-xl border border-border px-3 py-2 text-sm font-medium hover:bg-slate-100"
          >
            {t(d.reset)}
          </button>
        </div>
      )}
    </div>
  );
}
