import type {
  AiModel,
  CrashTestJob,
  CrashTestRequest,
  Device,
  Passport,
  SealResponse,
  Stats,
  VerifyResponse,
} from "./types";
import { mockApi } from "./mock";

// Backend runs separately (no Docker). Leave NEXT_PUBLIC_API_URL unset to use mock data.
const RAW_BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
export const USE_MOCK = !RAW_BASE;

// With NEXT_PUBLIC_API_URL=http://localhost:8000/api the site also works when opened from another
// device (http://<laptop IP>:3000): the browser then talks to the backend on that same host.
function resolveBase(raw: string | undefined): string {
  if (!raw || typeof window === "undefined") return raw ?? "";
  const url = new URL(raw);
  if (["localhost", "127.0.0.1"].includes(url.hostname)) url.hostname = window.location.hostname;
  return url.toString().replace(/\/$/, "");
}

export const API_BASE_URL = resolveBase(RAW_BASE);

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isForm = init?.body instanceof FormData;
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: isForm ? init?.headers : { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, detailOf(text) || res.statusText);
  }
  return res.json() as Promise<T>;
}

// FastAPI errors are {"detail": "message"} or, for validation, {"detail": [{"msg": ...}, ...]}.
function detailOf(text: string): string {
  try {
    const { detail } = JSON.parse(text);
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((x) => x?.msg ?? String(x)).join("; ");
  } catch {
    // not JSON: show as is
  }
  return text;
}

const post = <T>(path: string, body: unknown) =>
  request<T>(path, {
    method: "POST",
    body: body instanceof FormData ? body : JSON.stringify(body),
  });

// download_url from the backend is absolute-path ("/api/seal/12/file").
export function backendUrl(path: string): string {
  if (USE_MOCK || /^https?:|^data:/.test(path)) return path;
  return new URL(path, API_BASE_URL).toString();
}

export function pngSrc(b64OrUrl: string): string {
  if (!b64OrUrl) return "";
  if (/^(data:|https?:|\/)/.test(b64OrUrl)) return b64OrUrl;
  return `data:image/png;base64,${b64OrUrl}`;
}

const realApi = {
  getDevices: () => request<Device[]>("/devices"),
  createDevice: (name: string, hospital: string) =>
    post<Device>("/devices", { name, hospital }),

  seal: (file: File, deviceId: number) => {
    const form = new FormData();
    form.append("file", file);
    form.append("device_id", String(deviceId));
    return post<SealResponse>("/seal", form);
  },

  verify: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return post<VerifyResponse>("/verify", form);
  },

  getModels: () => request<AiModel[]>("/models"),
  startCrashTest: (body: CrashTestRequest) =>
    post<{ job_id: number }>("/crash-test", body),
  getCrashTest: (jobId: number) => request<CrashTestJob>(`/crash-test/${jobId}`),

  createPassport: (modelId: number, crashTestId: number) =>
    post<Passport>("/passport", { model_id: modelId, crash_test_id: crashTestId }),
  getPassport: (id: number) => request<Passport>(`/passport/${id}`),
  // The backend PDF exists in Uzbek and Russian; English UI gets the Uzbek PDF.
  passportPdfUrl: (id: number, lang: "uz" | "ru" | "en") =>
    backendUrl(`${API_BASE_URL}/passport/${id}/pdf?lang=${lang === "ru" ? "ru" : "uz"}`),

  getStats: () => request<Stats>("/stats"),
};

export type Api = typeof realApi;

export const api: Api = USE_MOCK ? mockApi : realApi;
