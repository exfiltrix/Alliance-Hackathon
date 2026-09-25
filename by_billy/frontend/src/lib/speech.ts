import { LANGS, type Lang } from "./dictionary";

export const speechSupported = () =>
  typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;

// ---------- voices ----------

const EMPTY: SpeechSynthesisVoice[] = [];
let voicesCache: SpeechSynthesisVoice[] = EMPTY;
let voicesKey = "";

export function subscribeVoices(cb: () => void) {
  if (!speechSupported()) return () => {};
  const synth = window.speechSynthesis;
  synth.addEventListener("voiceschanged", cb);
  return () => synth.removeEventListener("voiceschanged", cb);
}

export function getVoicesSnapshot(): SpeechSynthesisVoice[] {
  if (!speechSupported()) return EMPTY;
  const list = window.speechSynthesis.getVoices();
  const key = list.map((v) => v.voiceURI).join("|");
  if (key !== voicesKey) {
    voicesKey = key;
    voicesCache = list;
  }
  return voicesCache;
}

// macOS ships joke / robotic voices that sound terrible for real text.
const NOVELTY =
  /^(albert|bad news|bahh|bells|boing|bubbles|cellos|good news|jester|organ|superstar|trinoids|whisper|wobble|zarvox|fred|junior|kathy|ralph|grandma|grandpa|eddy|flo|reed|rocko|sandy|shelley)\b/i;
const GOOD =
  /samantha|ava|allison|susan|zoe|evan|nathan|serena|daniel|kate|moira|milena|yuri|katya|madina|sardor|dariya|svetlana|dmitry|google|microsoft/i;

function quality(v: SpeechSynthesisVoice): number {
  const n = v.name.toLowerCase();
  let s = 0;
  if (/premium/.test(n)) s += 50;
  if (/enhanced|improved|улучшен/.test(n)) s += 40;
  if (/neural|natural|online/.test(n)) s += 35;
  if (/siri/.test(n)) s += 30;
  if (GOOD.test(n)) s += 10;
  if (v.localService) s += 2;
  if (v.default) s += 1;
  return s;
}

function voicesForCode(code: string, all: SpeechSynthesisVoice[]) {
  return all
    .filter((v) => v.lang.replace("_", "-").toLowerCase().startsWith(code) && !NOVELTY.test(v.name))
    .sort((a, b) => quality(b) - quality(a));
}

export type VoicePlan = {
  voices: SpeechSynthesisVoice[];
  speechLang: string;
  // "translit": no Uzbek voice on this device, so Uzbek text is converted to Cyrillic and read by a Russian voice.
  mode: "native" | "translit" | "none";
};

export function voicePlan(lang: Lang, all = getVoicesSnapshot()): VoicePlan {
  const native = voicesForCode(lang, all);
  if (native.length) return { voices: native, speechLang: LANGS.find((l) => l.code === lang)!.speech, mode: "native" };
  if (lang === "uz") {
    const ru = voicesForCode("ru", all);
    if (ru.length) return { voices: ru, speechLang: "ru-RU", mode: "translit" };
  }
  return { voices: [], speechLang: LANGS.find((l) => l.code === lang)!.speech, mode: "none" };
}

// ---------- text preparation ----------

function clean(text: string): string {
  return text
    .replace(/(\d)\s*[–—]\s*(\d)/g, "$1-$2")
    .replace(/[→⟶⇒]/g, ", ")
    .replace(/[·•|]/g, ", ")
    .replace(/\s[–—]\s/g, ", ")
    .replace(/\s*\/\s*/g, ", ")
    .replace(/…/g, ".")
    .replace(/[“”«»"#*_~]/g, "")
    .replace(/\s*,\s*(,\s*)+/g, ", ")
    .replace(/\s+/g, " ")
    .trim();
}

const UZ_SPECIAL: Record<string, string> = {
  medseal: "МедСил",
  ai: "Эй-Ай",
};

const UZ_LETTERS: Record<string, string> = {
  a: "а", b: "б", c: "ц", d: "д", e: "е", f: "ф", g: "г", h: "х", i: "и", j: "ж", k: "к", l: "л", m: "м",
  n: "н", o: "о", p: "п", q: "к", r: "р", s: "с", t: "т", u: "у", v: "в", w: "в", x: "х", y: "й", z: "з",
};
const APOS = "'ʻʼ‘’`";
const VOWELS = "aeiouаеиоуэ";

function uzWord(word: string): string {
  const special = UZ_SPECIAL[word.toLowerCase()];
  if (special) return special;
  // Keep acronyms (DICOM, PNG, SHA) and anything with digits as-is.
  if (/\d/.test(word) || (word.length > 1 && word === word.toUpperCase())) return word;

  const lower = word.toLowerCase();
  let out = "";
  for (let i = 0; i < lower.length; i++) {
    const c = lower[i];
    const next = lower[i + 1] ?? "";
    if ((c === "o" || c === "g") && APOS.includes(next)) {
      out += c === "o" ? "у" : "г";
      i++;
    } else if (c === "s" && next === "h") {
      out += "ш";
      i++;
    } else if (c === "c" && next === "h") {
      out += "ч";
      i++;
    } else if (c === "y" && "oaue".includes(next) && next) {
      out += { o: "ё", a: "я", u: "ю", e: "е" }[next as "o" | "a" | "u" | "e"];
      i++;
    } else if (c === "e" && (i === 0 || VOWELS.includes(lower[i - 1]))) {
      out += "э";
    } else if (APOS.includes(c)) {
      out += "ъ";
    } else {
      out += UZ_LETTERS[c] ?? c;
    }
  }
  return word[0] !== word[0].toLowerCase() ? out[0].toUpperCase() + out.slice(1) : out;
}

export function uzToCyrillic(text: string): string {
  // A trailing apostrophe is a closing quote, not part of the word.
  return text.replace(/[A-Za-z][A-Za-z'ʻʼ‘’`]*/g, (w) => uzWord(w.replace(/['ʻʼ‘’`]+$/, "")));
}

// Browsers cut off long utterances, so read in sentence-sized chunks.
export function chunks(text: string, max = 220): string[] {
  const parts = text
    .split(/(?<=[.!?:;])\s+/)
    .map((p) => p.trim())
    .filter(Boolean);
  const out: string[] = [];
  let cur = "";
  for (const p of parts) {
    if ((cur + " " + p).trim().length > max && cur) {
      out.push(cur);
      cur = p;
    } else {
      cur = (cur + " " + p).trim();
    }
  }
  if (cur) out.push(cur);
  const hardSplit = new RegExp(`.{1,${max}}(?:\\s|$)|.{1,${max}}`, "g");
  return out.flatMap((c) => (c.length > max ? (c.match(hardSplit) ?? [c]).map((s) => s.trim()) : [c]));
}

// ---------- speaking ----------

export function stopSpeech() {
  if (speechSupported()) window.speechSynthesis.cancel();
}

export function speak(text: string, lang: Lang, opts: { rate?: number; voiceURI?: string } = {}) {
  if (!speechSupported()) return;
  const plan = voicePlan(lang);
  let prepared = clean(text);
  if (plan.mode === "translit") prepared = uzToCyrillic(prepared);
  if (!prepared) return;

  const voice = plan.voices.find((v) => v.voiceURI === opts.voiceURI) ?? plan.voices[0];
  const synth = window.speechSynthesis;
  synth.cancel();
  // Safari drops an utterance queued in the same tick as cancel().
  setTimeout(() => {
    for (const part of chunks(prepared)) {
      const u = new SpeechSynthesisUtterance(part);
      u.lang = voice?.lang ?? plan.speechLang;
      if (voice) u.voice = voice;
      u.rate = opts.rate ?? 0.95;
      u.pitch = 1;
      synth.speak(u);
    }
  }, 60);
}
