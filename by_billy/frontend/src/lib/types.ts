// Shapes mirror by_billy/docs/API.md — keep both in sync.

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
};

export type VerifyStatus = "authentic" | "tampered" | "unsigned" | "forged";

export type VerifyResponse = {
  status: VerifyStatus;
  uid?: string;
  device?: string;
  changed_tiles: [number, number][];
  preview_png: string;
  detective?: { probability: number; heatmap_png: string };
  shield: { attack_suspected: boolean; score: number; threshold: number };
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
  status: "running" | "done" | "error";
  progress: number;
  flip_rate: Record<string, number>;
  psnr: Record<string, number>;
  example?: {
    before_png: string;
    after_png: string;
    before_score: number;
    after_score: number;
  };
  robustness_score?: number;
};

export type Verdict = "allowed" | "conditional" | "not_allowed";

export type Passport = {
  id: number;
  model: AiModel;
  crash_test_id: number;
  robustness_score: number;
  flip_rate: Record<string, number>;
  shield_compatible: boolean;
  pipeline_protected: boolean;
  verdict: Verdict;
  conditions?: string;
  organisation: string;
  created_at: string;
};

export type Stats = {
  sealed: number;
  verified: number;
  tampered: number;
  unsigned: number;
  models_tested: number;
  avg_robustness: number;
};
