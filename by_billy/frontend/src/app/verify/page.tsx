"use client";

import { useState } from "react";
import PageShell from "@/components/PageShell";
import UploadDropzone from "@/components/UploadDropzone";
import { Button, Card, DoctorNote, ErrorBox, Field, ProgressBar, Spinner, errorMessage } from "@/components/ui";
import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";
import { USE_MOCK, api, pngSrc } from "@/lib/api";
import type { VerifyResponse, VerifyStatus } from "@/lib/types";
import { VerifyIcon } from "@/components/icons";

const d = dictionary.verify;

const statusStyle: Record<VerifyStatus, string> = {
  authentic: "border-ok/30 bg-ok/10 text-ok",
  tampered: "border-danger/30 bg-danger/10 text-danger",
  forged: "border-danger/30 bg-danger/10 text-danger",
  unsigned: "border-border bg-slate-100 text-slate-600",
};

export default function VerifyPage() {
  const { t } = useLanguage();
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerifyResponse | null>(null);

  const submit = async (f: File) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.verify(f));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  const onFile = (f: File) => {
    setFile(f);
    submit(f);
  };

  const reset = () => {
    setFile(null);
    setResult(null);
    setError(null);
  };

  return (
    <PageShell title={t(d.title)} subtitle={t(d.subtitle)} icon={VerifyIcon} step="verify">
      {!result && (
        <div className="space-y-4">
          <UploadDropzone file={file} onFile={onFile} disabled={loading} />
          {loading && (
            <p role="status" className="flex items-center gap-2 text-sm text-muted">
              <Spinner /> {t(d.checking)}
            </p>
          )}
          {USE_MOCK && <p className="text-xs text-muted">{t(d.demoHint)}</p>}
        </div>
      )}

      {error && (
        <div className="mt-6">
          <ErrorBox message={error} onRetry={file ? () => submit(file) : undefined} />
        </div>
      )}

      {result && (
        <div className="space-y-6">
          <div role="status" className={`rounded-2xl border p-5 ${statusStyle[result.status]}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xl font-semibold">{t(d.status[result.status].title)}</p>
              {result.status !== "unsigned" && (
                <span className="rounded-full bg-white/70 px-3 py-1 text-xs font-medium">
                  {t(dictionary.common.certain)}
                </span>
              )}
            </div>
            <p className="mt-1 text-sm opacity-90">{t(d.status[result.status].desc)}</p>
            {result.status === "forged" && result.reason && (
              <p className="mt-1 text-sm font-medium">{t(d.forgedReasons[result.reason])}</p>
            )}
          </div>

          <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
            <Card>
              <p className="mb-3 text-sm font-medium">{t(d.preview)}</p>
              <div className="flex justify-center overflow-hidden rounded-xl bg-black">
                <div className="relative">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={pngSrc(result.preview_png)}
                    alt={`${t(d.preview)}: ${t(d.status[result.status].title)}`}
                    className="block max-h-[480px] w-auto max-w-full"
                  />
                </div>
              </div>
            </Card>

            <div className="space-y-4">
              {(result.uid || result.device || result.status === "tampered") && (
                <Card className="grid gap-4">
                  {result.device && <Field label={t(d.device)} value={result.device} />}
                  {result.uid && <Field label="UID" value={result.uid} mono />}
                  {result.status === "tampered" && (
                    <Field label={t(d.changedTiles)} value={result.changed_tiles.length} />
                  )}
                </Card>
              )}

              {result.detective && (
                <Card>
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-semibold">{t(d.detectiveTitle)}</p>
                    <div className="flex gap-1">
                      {result.detective.experimental && (
                        <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
                          {t(d.experimental)}
                        </span>
                      )}
                      <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">
                        {t(dictionary.common.probability)}
                      </span>
                    </div>
                  </div>
                  <p className="mt-3 text-xs text-muted">{t(d.detectiveLabel)}</p>
                  <p className="text-3xl font-semibold">
                    {Math.round(result.detective.probability * 100)}%
                  </p>
                  <div className="mt-2">
                    <ProgressBar value={result.detective.probability} label={t(d.detectiveLabel)} color="bg-amber-500" />
                  </div>
                  <p className="mt-3 text-xs text-muted">{t(d.detectiveNote)}</p>
                </Card>
              )}

              <Card
                className={result.shield?.attack_suspected ? "border-danger/40 bg-danger/5" : ""}
              >
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold">{t(d.shieldTitle)}</p>
                  {/* the shield score is a distance, not a percentage: show it as a warning */}
                  <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">
                    {t(d.warning)}
                  </span>
                </div>
                {result.shield ? (
                  <>
                    <p
                      className={`mt-3 font-semibold ${
                        result.shield.attack_suspected ? "text-danger" : "text-ok"
                      }`}
                    >
                      {result.shield.attack_suspected ? t(d.shieldFlag) : t(d.shieldClean)}
                    </p>
                    {result.shield.attack_suspected && (
                      <p className="mt-1 text-xs text-danger/80">{t(d.shieldFlagNote)}</p>
                    )}
                    <p className="mt-2 text-xs text-muted">
                      {t(d.shieldScore)}: {result.shield.score.toFixed(2)} ({t(d.threshold)}{" "}
                      {result.shield.threshold.toFixed(2)})
                    </p>
                  </>
                ) : (
                  <p className="mt-3 text-sm text-muted">{t(d.aiOff)}</p>
                )}
              </Card>

              <DoctorNote />
              <Button variant="ghost" onClick={reset} className="w-full">
                {t(d.another)}
              </Button>
            </div>
          </div>
        </div>
      )}
    </PageShell>
  );
}
