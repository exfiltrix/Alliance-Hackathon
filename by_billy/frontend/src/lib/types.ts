// Shapes mirror /API.md in the repo root (the backend contract) — keep both in sync.

export type Device = {
  id: number;
  name: string;
  hospital: string;
  revoked?: boolean;
};

export type SealResponse = {
  seal_id: number;
  uid: string;
  device_id: number;
  tiles: number;
  root: string;
  created_at: string;
  download_url: string;
  check_token?: string; // patient QR check: /check/{check_token}
};

export type Severity = "danger" | "warning" | "ok";

export type InboxReason =
  | "tampered" | "forged" | "attack_suspected" | "unsigned" | "unreadable" | "device_revoked_later";

export type InboxItem = {
  id: number;
  file_name: string;
  source: "upload" | "folder";
  received_at: string;
  status: VerifyStatus | "error";
  severity: Severity;
  reasons: InboxReason[];
  reviewed: boolean;
  device: string | null;
  changed_tiles: number;
  detective_probability: number | null;
  error: string | null;
};

export type InboxListing = {
  counts: Record<Severity, number> & { total: number };
  items: InboxItem[];
};

export type AutomationStatus = {
  watching: boolean;
  scanner_dir: string;
  incoming_dir: string;
  interval_s: number;
  gateway: string;
  sealed: number;
  verified: number;
  failed: number;
  last_event: { at: string; text: string } | null;
  warmup: boolean;
};

export type CheckInfo = {
  status: "valid" | "warning" | "invalid";
  reason: string | null;
  hospital: string | null;
  device: string | null;
  sealed_at: string;
  shape: number[];
};

export type CheckFileResult = {
  status: VerifyStatus | "mismatch";
  reason?: string | null;
  changed_tiles?: number;
  preview_png?: string;
};

export type VerifyStatus = "authentic" | "tampered" | "unsigned" | "forged";

export type ForgedReason = "ledger_entry_modified" | "bad_signature" | "device_revoked" | "unknown_device";
// P0-5: appears on `tampered` too, when display metadata (RescaleIntercept, Laterality...)
// was edited without touching pixels.
export type TamperedReason = ForgedReason | "metadata_changed";

export type VerifyResponse = {
  status: VerifyStatus;
  uid?: string | null;
  device?: string | null;
  seal_id?: number | null;
  changed_tiles: [number, number][];
  tile?: number | null;
  reason?: TamperedReason;
  changed_meta?: string[]; // tag names, only with reason === "metadata_changed"
  // Non-fatal: the device was revoked AFTER this seal was made, so it is still trusted.
  warning?: "device_revoked_later";
  verify_ms?: number;
  preview_png: string;
  // null when the AI is off on the backend; the detective key only exists for unsigned images
  detective?: { probability: number; heatmap_png: string; experimental: boolean } | null;
  shield: { attack_suspected: boolean; score: number; threshold: number } | null;
  note: string;
};

export type AiModel = {
  id: number;
  name: string;
  version: string;
  source?: string;
  intended_use?: string;
};

export type AttackMethod = "fgsm" | "pgd";

export type CrashTestRequest = {
  model_id: number;
  n_images: number;
  eps: number[];
  method: AttackMethod;
};

export type CrashTestJob = {
  status: "queued" | "running" | "done" | "error";
  progress: number;
  error?: string;
  flip_rate?: Record<string, number>;
  psnr?: Record<string, number>;
  example?: {
    eps?: number;
    before_png: string;
    after_png: string;
    before_score: number;
    after_score: number;
  };
  robustness_score?: number;
};

export type Verdict = "allowed" | "allowed_with_conditions" | "not_allowed";

export type PassportCondition = "shield_required" | "seal_required" | "doctor_decides" | "retest_required";

export type Passport = {
  id: number;
  created_at: string;
  organisation: string;
  model: AiModel;
  robustness: {
    score: number;
    formula: string;
    crash_test_id: number;
    tested_at: string;
    n_images: number;
    method: AttackMethod;
    pathology: string;
    data: string[];
    flip_rate: Record<string, number>;
    psnr: Record<string, number>;
    example?: CrashTestJob["example"] | null;
  };
  shield: {
    available: boolean;
    compatible: boolean;
    method?: string;
    threshold?: number;
    false_positive_rate?: number;
    detection_pgd_eps1?: number | null;
    detection_fgsm_eps1?: number | null;
  };
  pipeline: {
    devices_active: number;
    seals: number;
    verifications: number;
    tampered_or_forged: number;
    ledger_ok: boolean;
  };
  verdict: Verdict;
  conditions: PassportCondition[];
  rules: { allow_score: number; shield_min_detection: number; shield_max_false_alarms: number };
  note: string;
};

export type Stats = {
  sealed: number;
  verified: number;
  authentic: number;
  tampered: number;
  unsigned: number;
  forged: number;
  models_tested: number;
  avg_robustness: number | null; // null until a crash test has run
};
