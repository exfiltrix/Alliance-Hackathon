"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import PageShell from "@/components/PageShell";
import FlipRateChart from "@/components/FlipRateChart";
import { Button, Card, DoctorNote, ErrorBox, ProgressBar, Segmented, Spinner, errorMessage } from "@/components/ui";
import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";
import { api, pngSrc } from "@/lib/api";
import type { AiModel, AttackMethod, CrashTestJob } from "@/lib/types";
import { CrashTestIcon } from "@/components/icons";

const d = dictionary.crash;
const EPS = [0.5, 1, 2, 4];
const IMAGE_COUNTS = [10, 25, 50];

export default function CrashTestPage() {
  const { t } = useLanguage();
  const router = useRouter();
  const [models, setModels] = useState<AiModel[]>([]);
  const [modelId, setModelId] = useState<number | null>(null);
  const [nImages, setNImages] = useState(50);
  const [method, setMethod] = useState<AttackMethod>("fgsm");
  const [jobId, setJobId] = useState<number | null>(null);
  const [job, setJob] = useState<CrashTestJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    api
      .getModels()
      .then((list) => {
        setModels(list);
        setModelId(list[0]?.id ?? null);
      })
      .catch((e) => setError(errorMessage(e)));
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  const poll = (id: number) => {
    api
      .getCrashTest(id)
      .then((res) => {
        setJob(res);
        if (res.status === "queued" || res.status === "running") timer.current = setTimeout(() => poll(id), 1000);
        if (res.status === "error") {
          setJob(null);
          setError(res.error ?? t(dictionary.common.error));
        }
      })
      .catch((e) => setError(errorMessage(e)));
  };

  const start = async () => {
    if (modelId == null) return;
    setError(null);
    setJob({ status: "running", progress: 0, flip_rate: {}, psnr: {} });
    try {
      const { job_id } = await api.startCrashTest({ model_id: modelId, n_images: nImages, eps: EPS, method });
      setJobId(job_id);
      poll(job_id);
    } catch (e) {
      setJob(null);
      setError(errorMessage(e));
    }
  };

  const createPassport = async () => {
    if (modelId == null || jobId == null) return;
    setCreating(true);
    try {
      const p = await api.createPassport(modelId, jobId);
      router.push(`/passport/${p.id}`);
    } catch (e) {
      setError(errorMessage(e));
      setCreating(false);
    }
  };

  const running = job?.status === "queued" || job?.status === "running";
  const done = job?.status === "done";

  return (
    <PageShell title={t(d.title)} subtitle={t(d.subtitle)} icon={CrashTestIcon} step="crash">
      {!done && (
        <Card className="space-y-5">
          <div>
            <label htmlFor="model" className="text-sm font-medium">
              {t(d.model)}
            </label>
            <select
              id="model"
              value={modelId ?? ""}
              onChange={(e) => setModelId(Number(e.target.value))}
              disabled={running}
              className="mt-2 w-full rounded-xl border border-border bg-white px-3 py-2.5 text-sm outline-none focus:border-accent"
            >
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} · {m.version}
                </option>
              ))}
            </select>
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <p className="mb-2 text-sm font-medium">{t(d.images)}</p>
              <Segmented
                label={t(d.images)}
                options={IMAGE_COUNTS.map((n) => ({ value: n, label: String(n) }))}
                value={nImages}
                onChange={setNImages}
                disabled={running}
              />
            </div>
            <div>
              <p className="mb-2 text-sm font-medium">{t(d.method)}</p>
              <Segmented<AttackMethod>
                label={t(d.method)}
                options={[
                  { value: "fgsm", label: t(d.fgsm) },
                  { value: "pgd", label: t(d.pgd) },
                ]}
                value={method}
                onChange={setMethod}
                disabled={running}
              />
            </div>
          </div>

          {running ? (
            <div>
              <p role="status" className="flex items-center gap-2 text-sm text-muted">
                <Spinner /> {t(d.running)} {Math.round((job?.progress ?? 0) * 100)}%
              </p>
              <div className="mt-2">
                <ProgressBar value={job?.progress ?? 0} label={t(d.running)} />
              </div>
            </div>
          ) : (
            <Button onClick={start} disabled={modelId == null} className="w-full sm:w-auto">
              {t(d.start)}
            </Button>
          )}
        </Card>
      )}

      {error && (
        <div className="mt-6">
          <ErrorBox message={error} />
        </div>
      )}

      {done && job && (
        <div role="region" aria-live="polite" aria-label={t(d.scoreTitle)} className="space-y-6">
          {job.example && (
            <Card>
              <p className="text-sm font-semibold">{t(d.beforeAfter)}</p>
              <div className="mt-4 grid grid-cols-2 gap-3 sm:gap-6">
                {[
                  { src: job.example.before_png, label: t(d.before), score: job.example.before_score },
                  { src: job.example.after_png, label: t(d.after), score: job.example.after_score },
                ].map((x, i) => (
                  <div key={i}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={pngSrc(x.src)} alt={x.label} className="aspect-square w-full rounded-xl bg-black object-contain" />
                    <p className="mt-2 text-xs text-muted">{x.label}</p>
                    <p className="text-xs text-muted">{t(d.pneumonia)}</p>
                    <p className={`text-2xl font-semibold ${i === 1 ? "text-danger" : ""}`}>
                      {Math.round(x.score * 100)}%
                    </p>
                  </div>
                ))}
              </div>
              <p className="mt-4 text-sm text-muted">{t(d.invisible)}</p>
            </Card>
          )}

          <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
            <Card>
              <p className="text-sm font-semibold">{t(d.chartTitle)}</p>
              <p className="mb-6 text-xs text-muted">{t(d.chartAxis)}</p>
              <FlipRateChart flipRate={job.flip_rate ?? {}} psnr={job.psnr ?? {}} psnrLabel={t(d.psnr)} caption={t(d.chartTitle)} epsLabel={t(d.attackStrength)} />
            </Card>

            <Card className="flex flex-col">
              <p className="text-sm font-semibold">{t(d.scoreTitle)}</p>
              <p className="mt-4 text-6xl font-semibold tracking-tight">
                {job.robustness_score?.toFixed(1)}
                <span className="text-2xl text-muted"> / 10</span>
              </p>
              <p className="mt-3 text-xs text-muted">{t(d.scoreFormula)}</p>
              <div className="mt-auto space-y-2 pt-6">
                <Button onClick={createPassport} disabled={creating} className="w-full">
                  {creating && <Spinner />}
                  {t(d.createPassport)}
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setJob(null);
                    setJobId(null);
                  }}
                  className="w-full"
                >
                  {t(d.restart)}
                </Button>
              </div>
            </Card>
          </div>

          <DoctorNote />
        </div>
      )}
    </PageShell>
  );
}
