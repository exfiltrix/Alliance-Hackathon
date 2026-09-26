// Shapes mirror docs/API.md in the repo root (the backend contract) — keep both in sync.

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
  // AI reading's overall advice; null when the image was not read (not trusted, AI off).
  risk?: Risk | null;
  error: string | null;
};

export type InboxListing = {
  counts: Record<Severity, number> & { total: number };
  // Raw activity counts (any severity) for the doctor's summary tiles, independent of "counts"
  // above (which is unreviewed-only, danger/warning/ok).
  volume: { today: number; week: number; all: number };
  items: InboxItem[];
};

// GET /inbox query params (docs/API.md "Inbox (doctor)"). since/until are plain "YYYY-MM-DD".
export type InboxQuery = {
  limit?: number;
  offset?: number;
  severity?: Severity;
  reviewed?: boolean;
  since?: string;
  until?: string;
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

// CRY-02: the device has no valid root-signed certificate (a forged device row, or a swapped
// public key) — checked before the hash chain, so it wins over ledger_entry_modified.
export type ForgedReason =
  | "ledger_entry_modified"
  | "bad_signature"
  | "device_revoked"
  | "unknown_device"
  | "untrusted_device"
  | "blockchain_mismatch"; // our database no longer matches the root anchored on-chain
// P0-5: appears on `tampered` too, when display metadata (RescaleIntercept, Laterality...)
// was edited without touching pixels. P1-03: appears when the seal was found by content, not
// by ID, and something about the matched image differs. CRY-01: patient_mismatch means every
// tile and pixel is untouched, but the DICOM PatientID hashes to a different seal record.
export type TamperedReason = ForgedReason | "metadata_changed" | "seal_id_removed" | "patient_mismatch";

export type Specialty =
  | "pulmonology"
  | "cardiology"
  | "oncology"
  | "thoracic_surgery"
  | "traumatology"
  | "surgery"
  | "general_practice";
export type Risk = "high" | "medium" | "none";
export type Analysis =
  | { status: "blocked"; reason: "tampered" | "forged" | "unsigned" | "attack_suspected" | "shield_unavailable" }
  | {
      status: "done";
      risk: Risk;
      experimental: boolean;
      threshold: number;
      findings: { pathology: string; probability: number }[];
      referrals: { specialty: Specialty; urgency: "urgent" | "soon" | "routine"; pathologies: string[] }[];
    };

export type VerifyResponse = {
  status: VerifyStatus;
  uid?: string | null;
  device?: string | null;
  seal_id?: number | null;
  changed_tiles: [number, number][];
  tile?: number | null;
  // P1-03: how the ledger record was found — by the image's own ID, or (ID missing/stripped/
  // replaced) by comparing pixel content against every previously sealed image. null only for
  // "unsigned" (no match at all).
  matched_by?: "uid" | "content" | null;
  reason?: TamperedReason;
  changed_meta?: string[]; // tag names, only with reason === "metadata_changed"
  // Non-fatal: the device was revoked AFTER this seal was made, so it is still trusted.
  // CRY-02: device_not_certified only appears when MEDSEAL_REQUIRE_DEVICE_CERT=0 (migration mode).
  warning?: "device_revoked_later" | "seal_id_missing" | "device_not_certified";
  // CRY-01: whether the upload's DICOM PatientID matches the seal's patient_ref. not_available
  // covers no PatientID on the upload, no MEDSEAL_PATIENT_SALT configured, or a pre-CRY-01 row.
  patient_check?: "matched" | "mismatch" | "not_available";
  // IMG-03: the DICOM declares BurnedInAnnotation=YES; pixels may show identifying text that
  // de-identification cannot remove.
  phi_warning?: "burned_in_annotation";
  verify_ms?: number;
  sealed_at?: string; // on authentic/tampered: when and (device) by whom the image was sealed
  // null when anchoring is off on the backend or the image is unsigned. See API.md.
  blockchain?: BlockchainCheck | null;
  preview_png: string;
  // null when the AI is off on the backend; the public API intentionally omits Grad-CAM output.
  detective?: { probability: number; experimental: boolean } | null;
  shield: { attack_suspected: boolean; score: number; threshold: number } | null;
  // AI reading + referral, only for a trusted image (authentic + shield quiet). null when the AI
  // is off or not applicable. See API.md.
  analysis?: Analysis | null;
  ai_note?: "not_applicable";
  note: string;
};

export type BlockchainCheck = {
  status: "anchored" | "pending" | "mismatch" | "unavailable";
  detail?: "proof_missing" | "anchor_record_missing";
  block?: number;
  time?: string; // on-chain block time of the batch
  tx_hash?: string;
  tx_url?: string | null; // block explorer link; null on a local chain
  chain_id?: number;
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
  n_requested?: number; // how many images were asked for; n_images (below) may be fewer
  n_images?: number;
  // P1-04: only method=pgd, n_images>=50 and eps including 1 satisfies the passport protocol.
  protocol_compliant?: boolean;
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

export type PassportCondition = "shield_required" | "seal_required" | "doctor_decides" | "retest_required" | "clinical_validation_required";

export type Passport = {
  id: number;
  created_at: string;
  organisation: string;
  fingerprint: string;
  verify_url: string;
  model: AiModel;
  robustness: {
    score: number;
    formula: string;
    crash_test_id: number;
    tested_at: string;
    n_requested: number;
    n_images: number;
    method: AttackMethod;
    pathology: string;
    data: string[];
    flip_rate: Record<string, number>;
    psnr: Record<string, number>;
    example?: CrashTestJob["example"] | null;
  };
  clinical_validation: { dataset: string; n: number; auc: number; sensitivity: number; specificity: number } | null;
  shield: {
    available: boolean;
    compatible: boolean;
    method?: string;
    threshold?: number;
    false_positive_rate?: number;
    detection_pgd_eps1?: number | null;
    detection_fgsm_eps1?: number | null;
    confidence_intervals?: {
      detection_pgd_eps1: { successes: number; n: number; lower: number; upper: number };
      false_positive_rate: { successes: number; n: number; lower: number; upper: number };
    };
    adaptive_attack_tested?: boolean;
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
  protocol: { method: AttackMethod; min_images: number; eps_required: number[] };
  note: string;
};

// Client (hospital/clinic) cabinet — docs/API.md "Client cabinet". Strictly scoped server-side to
// one organisation by MEDSEAL_CLIENT_TOKEN; the frontend never chooses which hospital it sees.
export type ClientDevice = {
  id: number;
  name: string;
  revoked: boolean;
  certified: boolean;
  created_at: string;
  last_seal_at: string | null;
  seal_count: number;
};

export type ClientStats = {
  hospital: string;
  devices: { total: number; active: number; revoked: number; certified: number };
  seals: { today: number; "7d": number; total: number };
  verifications: { total: number; by_result: Partial<Record<VerifyStatus, number>> };
};

export type ClientAlert = {
  at: string;
  seal_id: number;
  uid: string | null;
  device: string | null;
  result: VerifyStatus;
  shield_flag: boolean | null;
};

// GET /client/passports and GET /passports share this summary shape (see routers/passport.py).
export type PassportSummary = {
  id: number;
  created_at: string;
  organisation: string;
  verdict: Verdict;
  conditions: PassportCondition[];
  model: AiModel;
  robustness_score: number;
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
