"use client";

import { useState } from "react";
import Link from "next/link";
import PageShell from "@/components/PageShell";
import UploadDropzone from "@/components/UploadDropzone";
import { Button, Card, ErrorBox, Field, Spinner, buttonClass, errorMessage } from "@/components/ui";
import { useLanguage } from "@/lib/language-context";
import dictionary, { localeOf } from "@/lib/dictionary";
import { api, backendUrl } from "@/lib/api";
import type { SealResponse } from "@/lib/types";
import { SealIcon } from "@/components/icons";

const d = dictionary.seal;

// The QR opens this site's public check page; built from the address the site is opened at,
// so a phone on the same Wi-Fi can scan it.
const checkPage = (token: string) => `${window.location.origin}/check/${token}`;

export default function SealPage() {
  const { t, lang } = useLanguage();
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SealResponse | null>(null);

  const submit = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await api.seal(file));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setResult(null);
    setFile(null);
  };

  return (
    <PageShell title={t(d.title)} subtitle={t(d.subtitle)} icon={SealIcon} step="seal">
      {result ? (
        <Card className="space-y-6">
          <div role="status" className="flex flex-wrap items-center justify-between gap-3">
            <span className="inline-flex items-center gap-2 rounded-full bg-ok/10 px-4 py-1.5 text-sm font-semibold text-ok">
              <svg aria-hidden width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12l5 5L20 7" />
              </svg>
              {t(d.sealed)}
            </span>
            <span className="text-xs text-muted">{t(dictionary.common.certain)}</span>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t(d.sealId)} value={`#${result.seal_id}`} />
            <Field label={t(d.time)} value={new Date(result.created_at).toLocaleString(localeOf(lang))} />
            <Field label={t(d.device)} value={`#${result.device_id}`} />
            <Field label={t(d.tiles)} value={result.tiles} />
            <Field label={t(d.uid)} value={result.uid} mono />
            <Field label={t(d.root)} value={`${result.root.slice(0, 16)}…`} mono />
          </div>

          {result.check_token && (
            <div className="flex flex-col items-center gap-4 rounded-2xl border border-border bg-white/60 p-4 sm:flex-row">
              {api.checkQrUrl(result.check_token, checkPage(result.check_token)) && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={api.checkQrUrl(result.check_token, checkPage(result.check_token))}
                  alt={t(dictionary.sealQr.title)}
                  width={144}
                  height={144}
                  className="h-36 w-36 rounded-lg bg-white"
                />
              )}
              <div className="space-y-2 text-center sm:text-left">
                <p className="text-sm font-semibold">{t(dictionary.sealQr.title)}</p>
                <p className="text-xs text-muted">{t(dictionary.sealQr.desc)}</p>
                <Link href={`/check/${result.check_token}`} target="_blank" className="text-sm font-medium text-accent">
                  {t(dictionary.sealQr.open)} →
                </Link>
              </div>
            </div>
          )}

          <div className="flex flex-col gap-3 sm:flex-row">
            <a href={backendUrl(result.download_url)} download={file?.name} className={buttonClass("dark")}>
              {t(d.download)}
            </a>
            <Link href="/verify" className={buttonClass("accent")}>
              {t(d.verifyNow)}
            </Link>
            <Button variant="ghost" onClick={reset}>
              {t(d.another)}
            </Button>
          </div>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <UploadDropzone file={file} onFile={setFile} disabled={loading} />

          <Card className="space-y-4">
            <Button onClick={submit} disabled={!file || loading} className="w-full">
              {loading && <Spinner />}
              {loading ? t(d.sealing) : t(d.submit)}
            </Button>

            <p className="text-xs text-muted">{t(d.gatewayNote)}</p>
          </Card>
        </div>
      )}

      {error && (
        <div className="mt-6">
          <ErrorBox message={error} />
        </div>
      )}
    </PageShell>
  );
}
