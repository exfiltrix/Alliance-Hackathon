// Demo data used when NEXT_PUBLIC_API_URL is not set. Mirrors the real API shapes.
import type { Api } from "./api";
import type { AiModel, CrashTestJob, Device, Passport, VerifyResponse } from "./types";

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

const devices: Device[] = [
  { id: 1, name: "KT-01", hospital: "Namangan viloyat shifoxonasi" },
  { id: 2, name: "RG-02", hospital: "Toshkent shahar klinikasi" },
];

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

const FLIP = { "0.5": 0.12, "1": 0.48, "2": 0.9, "4": 1 };

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
  async getDevices() {
    await wait(200);
    return [...devices];
  },
  async createDevice(name, hospital) {
    await wait(300);
    const d = { id: devices.length + 1, name, hospital };
    devices.push(d);
    return d;
  },

  async seal(file, deviceId) {
    await wait(600);
    sealedNames.add(file.name);
    const id = nextId++;
    return {
      seal_id: id,
      uid: `1.3.6.1.4.1.${Date.now()}`,
      device_id: deviceId,
      tiles: 256,
      root: Array.from({ length: 64 }, () => "0123456789abcdef"[Math.floor(Math.random() * 16)]).join(""),
      created_at: new Date().toISOString(),
      download_url: URL.createObjectURL(file),
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
        detective: { probability: 0.87, heatmap_png: heatmap() },
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
      psnr: done ? { "0.5": 58.3, "1": 52.1, "2": 46.2, "4": 40.1 } : {},
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
    const score = Math.round(10 * (1 - FLIP["1"]) * 10) / 10;
    const p: Passport = {
      id,
      model: models.find((m) => m.id === modelId) ?? models[0],
      crash_test_id: crashTestId,
      robustness_score: score,
      flip_rate: FLIP,
      shield_compatible: true,
      pipeline_protected: true,
      verdict: "conditional",
      conditions: "Faqat MedSeal Shield yoqilgan holda ishlatilsin.",
      organisation: "Namangan viloyat shifoxonasi",
      created_at: new Date().toISOString(),
    };
    passports.set(id, p);
    return p;
  },
  async getPassport(id) {
    await wait(300);
    return (
      passports.get(id) ?? {
        id,
        model: models[0],
        crash_test_id: 1,
        robustness_score: 5.2,
        flip_rate: FLIP,
        shield_compatible: true,
        pipeline_protected: true,
        verdict: "conditional",
        conditions: "Faqat MedSeal Shield yoqilgan holda ishlatilsin.",
        organisation: "Namangan viloyat shifoxonasi",
        created_at: new Date().toISOString(),
      }
    );
  },
  passportPdfUrl: () => "",

  async getStats() {
    await wait(250);
    return { sealed: 128, verified: 342, tampered: 7, unsigned: 41, models_tested: 3, avg_robustness: 5.8 };
  },
};
