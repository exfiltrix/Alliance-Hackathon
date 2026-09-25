"use client";

import { useSyncExternalStore } from "react";
import { A11Y_KEY } from "./a11y-init";

export type A11ySettings = {
  font: 0 | 1 | 2;
  contrast: "normal" | "high" | "invert";
  grayscale: boolean;
  spacing: boolean;
  links: boolean;
  reduceMotion: boolean;
  speech: boolean;
};

export const DEFAULT_A11Y: A11ySettings = {
  font: 0,
  contrast: "normal",
  grayscale: false,
  spacing: false,
  links: false,
  reduceMotion: false,
  speech: false,
};

function applyA11y(s: A11ySettings) {
  const d = document.documentElement.dataset;
  const set = (key: string, on: boolean, value = "1") => {
    if (on) d[key] = value;
    else delete d[key];
  };
  set("font", s.font > 0, String(s.font));
  set("contrast", s.contrast !== "normal", s.contrast);
  set("gray", s.grayscale);
  set("spacing", s.spacing);
  set("links", s.links);
  set("reduceMotion", s.reduceMotion);
}

const listeners = new Set<() => void>();
let memoryRaw: string | null = null;
let cache: { raw: string | null; value: A11ySettings } = { raw: null, value: DEFAULT_A11Y };

function readRaw(): string | null {
  try {
    return window.localStorage.getItem(A11Y_KEY);
  } catch {
    return memoryRaw;
  }
}

function getSnapshot(): A11ySettings {
  const raw = readRaw();
  if (raw !== cache.raw) {
    let value = DEFAULT_A11Y;
    try {
      value = { ...DEFAULT_A11Y, ...(raw ? JSON.parse(raw) : {}) };
    } catch {
      // corrupted value — fall back to defaults
    }
    cache = { raw, value };
  }
  return cache.value;
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  window.addEventListener("storage", cb);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", cb);
  };
}

export function updateA11y(patch: Partial<A11ySettings> | null) {
  const next = patch ? { ...getSnapshot(), ...patch } : DEFAULT_A11Y;
  const raw = JSON.stringify(next);
  memoryRaw = raw;
  try {
    window.localStorage.setItem(A11Y_KEY, raw);
  } catch {
    // storage blocked — memoryRaw keeps the setting for this visit
  }
  applyA11y(next);
  listeners.forEach((l) => l());
}

export function useA11y(): A11ySettings {
  return useSyncExternalStore(subscribe, getSnapshot, () => DEFAULT_A11Y);
}
