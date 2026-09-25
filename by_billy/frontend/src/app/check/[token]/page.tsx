"use client";

import { use, useEffect, useState } from "react";
import PageShell from "@/components/PageShell";
import UploadDropzone from "@/components/UploadDropzone";
import { Card, Field, Spinner, errorMessage } from "@/components/ui";
import { useLanguage } from "@/lib/language-context";
import dictionary, { localeOf } from "@/lib/dictionary";
import { ApiError, api, pngSrc } from "@/lib/api";
import type { CheckFileResult, CheckInfo } from "@/lib/types";
import { VerifyIcon } from "@/components/icons";

const d = dictionary.check;

// Public page behind the QR code: no login, big and simple, phone-first.
export default function CheckPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const { t, lang } = useLanguage();
  const [info, setInfo] = useState<CheckInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileResult, setFileResult] = useState<CheckFileResult | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    api
      .getCheck(token)
      .then(setInfo)
      .catch((e) => setError(e instanceof ApiError && e.status === 404 ? t(d.notFound) : errorMessage(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const compare = async (f: File) => {
    setFile(f);
    setFileResult(null);
    setChecking(true);
    try {
      setFileResult(await api.checkFile(token, f));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setChecking(false);
    }
  };

  const good = info?.status === "valid" || info?.status === "warning";
  const fileText: Record<CheckFileResult["status"], { text: string; ok: boolean }> = {
    authentic: { text: t(d.fileAuthentic), ok: true },
    tampered: { text: t(d.fileTampered), ok: false },
    mismatch: { text: t(d.fileMismatch), ok: false },
    unsigned: { text: t(d.fileUnsigned), ok: false },
    forged: { text: t(d.fileForged), ok: false },
  };

  return (
    <PageShell title={t(d.title)} subtitle={t(d.subtitle)} icon={VerifyIcon}>
      <div className="mx-auto max-w-xl space-y-5">
        {error && <Card className="border-danger/40 bg-danger/5 text-center text-lg font-semibold text-danger">{error}</Card>}

        {!info && !error && (
          <p role="status" className="flex items-center justify-center gap-2 text-sm text-muted">
            <Spinner /> {t(dictionary.common.loading)}
          </p>
        )}

        {info && (
          <div
            role="status"
            className={`rounded-3xl border p-6 text-center ${good ? "border-ok/30 bg-ok/10 text-ok" : "border-danger/30 bg-danger/10 text-danger"}`}
          >
            <p className="text-5xl" aria-hidden>{good ? "✓" : "✕"}</p>
            <p className="mt-2 text-2xl font-semibold">
              {info.status === "valid" ? t(d.valid) : info.status === "warning" ? t(d.warning) : t(d.invalid)}
            </p>
            <p className="mt-2 text-sm opacity-90">{good ? t(d.validDesc) : t(d.invalidDesc)}</p>
            <span className="mt-3 inline-block rounded-full bg-white/70 px-3 py-1 text-xs font-medium">
              {t(dictionary.common.certain)}
            </span>
          </div>
        )}

        {info && (
          <Card className="grid gap-4 sm:grid-cols-3">
            <Field label={t(d.hospital)} value={info.hospital ?? "—"} />
            <Field label={t(d.device)} value={info.device ?? "—"} />
            <Field label={t(d.sealedAt)} value={new Date(info.sealed_at).toLocaleString(localeOf(lang))} />
          </Card>
        )}

        {info && good && (
          <Card className="space-y-3">
            <p className="text-sm font-semibold">{t(d.compareTitle)}</p>
            <p className="text-xs text-muted">{t(d.compareDesc)}</p>
            <UploadDropzone file={file} onFile={compare} disabled={checking} />
            {checking && (
              <p className="flex items-center gap-2 text-sm text-muted">
                <Spinner /> {t(dictionary.inbox.checking)}
              </p>
            )}
            {fileResult && (
              <div className="space-y-3">
                <p className={`text-lg font-semibold ${fileText[fileResult.status].ok ? "text-ok" : "text-danger"}`}>
                  {fileText[fileResult.status].text}
                </p>
                {fileResult.preview_png && fileResult.status === "tampered" && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={pngSrc(fileResult.preview_png)} alt={fileText.tampered.text} className="w-full rounded-xl bg-black" />
                )}
              </div>
            )}
          </Card>
        )}

        <p className="text-center text-xs text-muted">{t(d.privacy)}</p>
      </div>
    </PageShell>
  );
}
