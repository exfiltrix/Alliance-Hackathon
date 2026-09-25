"use client";

import { useEffect, useId, useRef, useState, useSyncExternalStore } from "react";
import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";
import { updateA11y, useA11y, type A11ySettings } from "@/lib/a11y";
import { getVoicesSnapshot, speak, speechSupported, stopSpeech, subscribeVoices, voicePlan } from "@/lib/speech";
import { AccessibilityIcon, SpeakerIcon } from "./icons";

const d = dictionary.a11y;

const noop = () => () => {};
const NO_VOICES: SpeechSynthesisVoice[] = [];
const SPEEDS = [
  { key: "slow", rate: 0.8 },
  { key: "normal", rate: 0.95 },
  { key: "fast", rate: 1.15 },
] as const;

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

function useSpeechReader(enabled: boolean, rate: number, voiceURI: string | undefined) {
  const { lang } = useLanguage();

  useEffect(() => {
    if (!enabled || !speechSupported()) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let lastSpoken = "";

    // Wait until the user stops dragging the selection, then read it once.
    const onSelectionChange = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const text = window.getSelection()?.toString().trim() ?? "";
        if (!text) {
          lastSpoken = "";
          return;
        }
        if (text === lastSpoken) return;
        lastSpoken = text;
        speak(text, lang, { rate, voiceURI });
      }, 500);
    };

    document.addEventListener("selectionchange", onSelectionChange);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("selectionchange", onSelectionChange);
      stopSpeech();
    };
  }, [enabled, lang, rate, voiceURI]);
}

export default function AccessibilityPanel() {
  const { t, lang } = useLanguage();
  const settings = useA11y();
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const canSpeak = useSyncExternalStore(noop, speechSupported, () => false);

  const voices = useSyncExternalStore(subscribeVoices, getVoicesSnapshot, () => NO_VOICES);
  const plan = voicePlan(lang, voices);
  const voiceURI = settings.speechVoices[lang];

  useSpeechReader(settings.speech, settings.speechRate, voiceURI);

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
        className={`flex h-9 w-9 items-center justify-center rounded-full border transition-colors ${
          open ? "border-foreground bg-foreground text-white" : "border-border bg-white/70 hover:bg-white"
        }`}
      >
        <AccessibilityIcon width={18} height={18} />
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
                {settings.speech && (
                  <div className="mt-3 space-y-3 px-1">
                    <fieldset>
                      <legend className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted">{t(d.speed)}</legend>
                      <div className="flex gap-2">
                        {SPEEDS.map(({ key, rate }) => (
                          <button
                            key={key}
                            type="button"
                            aria-pressed={settings.speechRate === rate}
                            onClick={() => set({ speechRate: rate })}
                            className={optionClass(settings.speechRate === rate)}
                          >
                            {t(d.speeds[key])}
                          </button>
                        ))}
                      </div>
                    </fieldset>

                    {plan.voices.length > 0 ? (
                      <div>
                        <label htmlFor="a11y-voice" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-muted">
                          {t(d.voice)}
                        </label>
                        <select
                          id="a11y-voice"
                          value={voiceURI && plan.voices.some((v) => v.voiceURI === voiceURI) ? voiceURI : ""}
                          onChange={(e) =>
                            set({ speechVoices: { ...settings.speechVoices, [lang]: e.target.value || undefined } })
                          }
                          className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm outline-none focus:border-accent"
                        >
                          <option value="">
                            {t(d.voiceAuto)} — {plan.voices[0].name}
                          </option>
                          {plan.voices.map((v) => (
                            <option key={v.voiceURI} value={v.voiceURI}>
                              {v.name} ({v.lang})
                            </option>
                          ))}
                        </select>
                        {plan.mode === "translit" && <p className="mt-1.5 text-xs text-muted">{t(d.translitNote)}</p>}
                      </div>
                    ) : (
                      <p className="text-xs text-muted">{t(d.noVoice)}</p>
                    )}

                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => speak(t(d.testPhrase), lang, { rate: settings.speechRate, voiceURI })}
                        className="flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-foreground px-3 py-2 text-sm font-medium text-white hover:bg-foreground/90"
                      >
                        <SpeakerIcon width={16} height={16} />
                        {t(d.test)}
                      </button>
                      <button
                        type="button"
                        onClick={stopSpeech}
                        className="rounded-xl border border-border px-3 py-2 text-sm font-medium hover:bg-slate-100"
                      >
                        {t(d.stop)}
                      </button>
                    </div>
                    <p className="text-[11px] leading-snug text-muted">{t(d.betterVoices)}</p>
                  </div>
                )}
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
