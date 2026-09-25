// Demo data used when NEXT_PUBLIC_API_URL is not set. Mirrors the real API shapes.
import type { Api } from "./api";
import type { AiModel, CrashTestJob, InboxItem, Passport, VerifyResponse } from "./types";

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

const models: AiModel[] = [
  {
    id: 1,
    name: "torchxrayvision DenseNet121",
    version: "densenet121-res224-all",
    source: "torchxrayvision",
    intended_use: "Chest X-ray pathology screening",
  },
];

const sealedNames = new Set<string>();
const jobs = new Map<number, { started: number; modelId: number; n: number }>();
const passports = new Map<number, Passport>();
let nextId = 100;

const inbox: InboxItem[] = [];
const inboxResults = new Map<number, VerifyResponse>();

function mockInboxItem(fileName: string, r: VerifyResponse): InboxItem {
  const id = nextId++;
  inboxResults.set(id, r);
  const danger = r.status === "tampered" || r.status === "forged" || !!r.shield?.attack_suspected;
  const reasons: InboxItem["reasons"] = [];
  if (r.status === "tampered" || r.status === "forged") reasons.push(r.status);
  if (r.shield?.attack_suspected) reasons.push("attack_suspected");
  if (!danger && r.status === "unsigned") reasons.push("unsigned");
  return {
    id, file_name: fileName, source: "upload", received_at: new Date().toISOString(), status: r.status,
    severity: danger ? "danger" : r.status === "unsigned" ? "warning" : "ok", reasons, reviewed: false,
    device: r.device ?? null, changed_tiles: r.changed_tiles.length,
    detective_probability: r.detective?.probability ?? null, error: null,
  };
}

const FLIP = { "0.5": 0.12, "1": 0.48, "2": 0.9, "4": 1 };
const PSNR = { "0.5": 58.3, "1": 52.1, "2": 46.2, "4": 40.1 };

function mockPassport(id: number, model: AiModel, crashTestId: number): Passport {
  const now = new Date().toISOString();
  return {
    id,
    created_at: now,
    organisation: "Namangan viloyat shifoxonasi",
    model,
    robustness: {
      score: Math.round(10 * (1 - FLIP["1"]) * 10) / 10,
      formula: "10 × (1 − flip rate at eps = 1 px)",
      crash_test_id: crashTestId,
      tested_at: now,
      n_images: 50,
      method: "pgd",
      pathology: "Pneumonia",
      data: ["nih/normal"],
      flip_rate: FLIP,
      psnr: PSNR,
      example: null,
    },
    shield: {
      available: true,
      compatible: true,
      method: "median 3x3, L1 distance of DenseNet logits",
      threshold: 10.4,
      false_positive_rate: 0.009,
      detection_pgd_eps1: 1,
      detection_fgsm_eps1: 0.62,
    },
    pipeline: { devices_active: 2, seals: 128, verifications: 342, tampered_or_forged: 7, ledger_ok: true },
    verdict: "allowed_with_conditions",
    conditions: ["shield_required", "seal_required", "doctor_decides"],
    rules: { allow_score: 7, shield_min_detection: 0.9, shield_max_false_alarms: 0.02 },
    note: "Final decision is made by the doctor.",
  };
}

function canvas(w: number, h: number) {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  return [c, c.getContext("2d")!] as const;
}

function fakeXray(noise = 0): string {
  const [c, ctx] = canvas(224, 224);
  ctx.fillStyle = "#0b0b0f";
  ctx.fillRect(0, 0, 224, 224);
  for (const x of [72, 152]) {
    const g = ctx.createRadialGradient(x, 115, 10, x, 115, 70);
    g.addColorStop(0, "#3a3a44");
    g.addColorStop(1, "#bdbdc8");
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.ellipse(x, 115, 42, 78, 0, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.fillStyle = "#d9d9e0";
  ctx.fillRect(106, 20, 12, 190);
  if (noise) {
    const img = ctx.getImageData(0, 0, 224, 224);
    for (let i = 0; i < img.data.length; i += 4) {
      const n = (Math.random() - 0.5) * noise;
      img.data[i] += n;
      img.data[i + 1] += n;
      img.data[i + 2] += n;
    }
    ctx.putImageData(img, 0, 0);
  }
  return c.toDataURL("image/png");
}

async function fileToPreview(file: File, tiles: [number, number][]): Promise<string> {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image();
      el.onload = () => resolve(el);
      el.onerror = reject;
      el.src = url;
    });
    const scale = 512 / Math.max(img.width, img.height);
    const [c, ctx] = canvas(Math.round(img.width * scale), Math.round(img.height * scale));
    ctx.drawImage(img, 0, 0, c.width, c.height);
    ctx.strokeStyle = "#ef4444";
    ctx.lineWidth = 3;
    for (const [y, x] of tiles) ctx.strokeRect(x * scale, y * scale, 32 * scale, 32 * scale);
    return c.toDataURL("image/png");
  } catch {
    return fakeXray();
  } finally {
    URL.revokeObjectURL(url);
  }
}

function heatmap(): string {
  const [c, ctx] = canvas(224, 224);
  const g = ctx.createRadialGradient(150, 100, 5, 150, 100, 60);
  g.addColorStop(0, "rgba(239,68,68,0.85)");
  g.addColorStop(1, "rgba(239,68,68,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 224, 224);
  return c.toDataURL("image/png");
}

export const mockApi: Api = {
  async seal(file) {
    await wait(600);
    sealedNames.add(file.name);
    const id = nextId++;
    return {
      seal_id: id,
      uid: `1.3.6.1.4.1.${Date.now()}`,
      device_id: 1,
      tiles: 256,
      root: Array.from({ length: 64 }, () => "0123456789abcdef"[Math.floor(Math.random() * 16)]).join(""),
      created_at: new Date().toISOString(),
      download_url: URL.createObjectURL(file),
      check_token: `demo${id}`,
    };
  },

  async verify(file) {
    await wait(900);
    const name = file.name.toLowerCase();
    const attacked = /attack|adv/.test(name);
    const shield = {
      attack_suspected: attacked,
      score: attacked ? 0.34 : 0.03,
      threshold: 0.11,
    };
    const note = "Final decision is made by the doctor.";
    let res: VerifyResponse;
    if (/fake|tamper/.test(name)) {
      const tiles: [number, number][] = [[96, 288], [96, 320], [128, 288], [128, 320]];
      res = {
        status: "tampered",
        uid: "1.3.6.1.4.1.9328",
        device: "KT-01",
        changed_tiles: tiles,
        preview_png: await fileToPreview(file, tiles),
        shield,
        note,
      };
    } else if (/forged/.test(name)) {
      res = { status: "forged", uid: "1.3.6.1.4.1.9328", device: "KT-01", changed_tiles: [], preview_png: await fileToPreview(file, []), shield, note };
    } else if (sealedNames.has(file.name) || /sealed|muhr/.test(name)) {
      res = { status: "authentic", uid: "1.3.6.1.4.1.9328", device: "KT-01", changed_tiles: [], preview_png: await fileToPreview(file, []), shield, note };
    } else {
      res = {
        status: "unsigned",
        changed_tiles: [],
        preview_png: await fileToPreview(file, []),
        detective: { probability: 0.87, heatmap_png: heatmap(), experimental: false },
        shield,
        note,
      };
    }
    return res;
  },

  async getModels() {
    await wait(200);
    return [...models];
  },
  async startCrashTest(body) {
    await wait(300);
    const id = nextId++;
    jobs.set(id, { started: Date.now(), modelId: body.model_id, n: body.n_images });
    return { job_id: id };
  },
  async getCrashTest(jobId) {
    await wait(150);
    const job = jobs.get(jobId);
    const progress = job ? Math.min(1, (Date.now() - job.started) / 6000) : 1;
    const done = progress >= 1;
    const res: CrashTestJob = {
      status: done ? "done" : "running",
      progress,
      flip_rate: done ? FLIP : {},
      psnr: done ? PSNR : {},
    };
    if (done) {
      res.example = { before_png: fakeXray(), after_png: fakeXray(6), before_score: 0.08, after_score: 0.93 };
      res.robustness_score = Math.round(10 * (1 - FLIP["1"]) * 10) / 10;
    }
    return res;
  },

  async createPassport(modelId, crashTestId) {
    await wait(400);
    const id = nextId++;
    const p = mockPassport(id, models.find((m) => m.id === modelId) ?? models[0], crashTestId);
    passports.set(id, p);
    return p;
  },
  async getPassport(id) {
    await wait(300);
    return passports.get(id) ?? mockPassport(id, models[0], 1);
  },
  passportPdfUrl: () => "",

  async uploadToInbox(files) {
    await wait(700);
    const added = await Promise.all(files.map((f) => mockApi.verify(f).then((r) => mockInboxItem(f.name, r))));
    inbox.unshift(...added);
    return added;
  },
  async getInbox() {
    await wait(200);
    const rank = { danger: 0, warning: 1, ok: 2 } as const;
    const items = [...inbox].sort((a, b) => Number(a.reviewed) - Number(b.reviewed) || rank[a.severity] - rank[b.severity] || b.id - a.id);
    const open = inbox.filter((i) => !i.reviewed);
    return {
      counts: {
        danger: open.filter((i) => i.severity === "danger").length,
        warning: open.filter((i) => i.severity === "warning").length,
        ok: open.filter((i) => i.severity === "ok").length,
        total: inbox.length,
      },
      items,
    };
  },
  async getInboxItem(id) {
    await wait(150);
    const item = inbox.find((i) => i.id === id);
    if (!item) throw new Error("Inbox item not found");
    return { ...item, result: inboxResults.get(id)! };
  },
  async reviewInboxItem(id) {
    const item = inbox.find((i) => i.id === id)!;
    item.reviewed = true;
    return item;
  },
  async getAutomation() {
    return {
      watching: false, scanner_dir: "data/watch/scanner", incoming_dir: "data/watch/incoming", interval_s: 2,
      gateway: "Shlyuz-Auto", sealed: 0, verified: inbox.length, failed: 0, last_event: null, warmup: false,
    };
  },
  async runAutomation() {
    return { sealed: 0, verified: 0 };
  },
  async getCheck() {
    await wait(300);
    return {
      status: "valid", reason: null, hospital: "Namangan viloyat shifoxonasi", device: "KT-01",
      sealed_at: new Date().toISOString(), shape: [512, 512],
    };
  },
  async checkFile(_token, file) {
    const r = await mockApi.verify(file);
    return { status: r.status, changed_tiles: r.changed_tiles.length, preview_png: r.preview_png };
  },
  checkQrUrl: () => "",

  async getStats() {
    await wait(250);
    return {
      sealed: 128, verified: 342, authentic: 290, tampered: 7, unsigned: 41, forged: 4, models_tested: 3, avg_robustness: 5.8,
    };
  },
};
