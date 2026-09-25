"use client";

import { useSyncExternalStore } from "react";

// Demo-only client-side session: no auth endpoint exists in docs/API.md yet
// (see register/page.tsx). Gates which nav links and pages are reachable and
// which interface (individual vs legal entity) is shown.
export type AccountType = "individual" | "legal";

export type AuthSession = {
  type: AccountType;
  name: string; // full name (individual) or contact person (legal)
  org?: string; // legal entity name, only for type "legal"
};

const KEY = "medseal-auth";
const listeners = new Set<() => void>();
let memorySession: AuthSession | null = null;

function subscribe(cb: () => void) {
  listeners.add(cb);
  window.addEventListener("storage", cb);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", cb);
  };
}

// useSyncExternalStore requires getSnapshot to return the SAME reference when nothing changed;
// JSON.parse-ing on every call would return a new object each render and loop forever, so cache
// by the raw string (same pattern as src/lib/a11y.ts).
let cache: { raw: string | null; value: AuthSession | null } = { raw: null, value: null };

function getSnapshot(): AuthSession | null {
  let raw: string | null;
  try {
    raw = window.localStorage.getItem(KEY);
  } catch {
    return memorySession;
  }
  if (raw !== cache.raw) {
    let value: AuthSession | null = null;
    try {
      value = raw ? (JSON.parse(raw) as AuthSession) : null;
    } catch {
      value = null;
    }
    cache = { raw, value };
  }
  return cache.value;
}

export function login(session: AuthSession) {
  memorySession = session;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(session));
  } catch {
    // storage blocked — memorySession keeps it for this tab only
  }
  listeners.forEach((l) => l());
}

export function logout() {
  memorySession = null;
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    // ignore
  }
  listeners.forEach((l) => l());
}

export function useAuth(): AuthSession | null {
  return useSyncExternalStore(subscribe, getSnapshot, () => null);
}
