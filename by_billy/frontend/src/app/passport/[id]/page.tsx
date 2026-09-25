"use client";

import { use, useEffect, useState } from "react";
import PageShell from "@/components/PageShell";
import { Button, Card, DoctorNote, ErrorBox, Field, Spinner, buttonClass, errorMessage } from "@/components/ui";
import { useLanguage } from "@/lib/language-context";
import dictionary, { localeOf } from "@/lib/dictionary";
import { api } from "@/lib/api";
import type { Passport, Verdict } from "@/lib/types";
import { PassportIcon } from "@/components/icons";

const d = dictionary.passport;

const verdictStyle: Record<Verdict, string> = {
  allowed: "bg-ok/10 text-ok border-ok/30",
  conditional: "bg-amber-50 text-amber-700 border-amber-300",
  not_allowed: "bg-danger/10 text-danger border-danger/30",
};

export default function PassportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { t, lang } = useLanguage();
  const [passport, setPassport] = useState<Passport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    api
      .getPassport(Number(id))
      .then(setPassport)
      .catch((e) => setError(errorMessage(e)));

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const retry = () => {
    setError(null);
    load();
  };

  const yesNo = (v: boolean) => (
    <span className={v ? "text-ok" : "text-danger"}>
      {v ? t(dictionary.common.yes) : t(dictionary.common.no)}
    </span>
  );

  const pdfUrl = passport ? api.passportPdfUrl(passport.id) : "";

  return (
    <PageShell title={t(d.title)} subtitle={t(d.subtitle)} icon={PassportIcon} step="passport" backHref="/crash-test">
      {error && <ErrorBox message={error} onRetry={retry} />}

      {!passport && !error && (
        <p role="status" className="flex items-center gap-2 text-sm text-muted">
          <Spinner /> {t(dictionary.common.loading)}
        </p>
      )}

      {passport && (
        <div className="space-y-6">
          <Card className="space-y-6 print:border-0 print:p-0">
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-6">
              <div>
                <p className="text-xs text-muted">MedSeal · № {passport.id}</p>
                <p className="mt-1 text-2xl font-semibold">{passport.model.name}</p>
                <p className="text-sm text-muted">{passport.model.version}</p>
              </div>
              <div className={`rounded-2xl border px-4 py-3 text-right ${verdictStyle[passport.verdict]}`}>
                <p className="text-xs opacity-80">{t(d.verdict)}</p>
                <p className="text-lg font-semibold">{t(d.verdicts[passport.verdict])}</p>
              </div>
            </div>

            <div className="grid gap-6 sm:grid-cols-[200px_1fr]">
              <div>
                <p className="text-xs text-muted">{t(d.robustness)}</p>
                <p className="text-5xl font-semibold tracking-tight">
                  {passport.robustness_score.toFixed(1)}
                  <span className="text-xl text-muted"> / 10</span>
                </p>
                <p className="mt-2 text-xs text-muted">{t(dictionary.crash.scoreFormula)}</p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                {passport.model.intended_use && (
                  <Field label={t(d.intendedUse)} value={passport.model.intended_use} />
                )}
                <Field label={t(d.organisation)} value={passport.organisation} />
                <Field label={t(d.shieldCompatible)} value={yesNo(passport.shield_compatible)} />
                <Field label={t(d.pipelineProtected)} value={yesNo(passport.pipeline_protected)} />
                <Field label={t(d.crashTest)} value={passport.crash_test_id} />
                <Field
                  label={t(d.date)}
                  value={new Date(passport.created_at).toLocaleDateString(localeOf(lang))}
                />
              </div>
            </div>

            {Object.keys(passport.flip_rate).length > 0 && (
              <div>
                <p className="text-xs text-muted">{t(dictionary.crash.chartTitle)}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {Object.entries(passport.flip_rate)
                    .sort(([a], [b]) => Number(a) - Number(b))
                    .map(([eps, v]) => (
                      <span key={eps} className="rounded-lg bg-slate-100 px-3 py-1.5 text-xs">
                        eps {eps}: <b>{Math.round(v * 100)}%</b>
                      </span>
                    ))}
                </div>
              </div>
            )}

            {passport.conditions && (
              <div className="rounded-xl bg-amber-50 p-4 text-sm text-amber-800">
                <p className="font-semibold">{t(d.conditions)}</p>
                <p className="mt-1">{passport.conditions}</p>
              </div>
            )}

            <DoctorNote />
          </Card>

          <div className="flex flex-col gap-3 sm:flex-row print:hidden">
            {pdfUrl && (
              <a href={pdfUrl} target="_blank" rel="noopener noreferrer" className={buttonClass("dark")}>
                {t(d.downloadPdf)}
              </a>
            )}
            <Button variant={pdfUrl ? "ghost" : "dark"} onClick={() => window.print()}>
              {t(d.print)}
            </Button>
          </div>
        </div>
      )}
    </PageShell>
  );
}
