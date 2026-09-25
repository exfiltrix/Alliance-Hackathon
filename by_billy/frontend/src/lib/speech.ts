import { LANGS, type Lang } from "./dictionary";

export const speechSupported = () =>
  typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;

function voiceFor(lang: Lang): SpeechSynthesisVoice | undefined {
  const prefix = lang.toLowerCase();
  return window.speechSynthesis
    .getVoices()
    .find((v) => v.lang.replace("_", "-").toLowerCase().startsWith(prefix));
}

// Browsers cut off long utterances, so read in sentence-sized chunks.
function chunks(text: string, max = 200): string[] {
  const parts = text
    .replace(/\s+/g, " ")
    .split(/(?<=[.!?:;…])\s+|\s+(?=•)/)
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

export function stopSpeech() {
  if (speechSupported()) window.speechSynthesis.cancel();
}

export function speak(text: string, lang: Lang) {
  if (!speechSupported() || !text.trim()) return;
  const synth = window.speechSynthesis;
  synth.cancel();
  const voice = voiceFor(lang);
  const speechLang = LANGS.find((l) => l.code === lang)!.speech;
  for (const part of chunks(text)) {
    const u = new SpeechSynthesisUtterance(part);
    u.lang = speechLang;
    if (voice) u.voice = voice;
    synth.speak(u);
  }
}
