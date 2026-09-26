"use client";

import { use, useEffect, useState } from "react";
import PageShell from "@/components/PageShell";
import { Button, Card, DoctorNote, ErrorBox, Field, PdfLangPicker, Spinner, buttonClass, errorMessage, usePdfLang } from "@/components/ui";
import { useLanguage } from "@/lib/language-context";
import dictionary, { localeOf } from "@/lib/dictionary";
import { api } from "@/lib/api";
import type { Passport, Verdict } from "@/lib/types";
import { PassportIcon } from "@/components/icons";

const d = dictionary.passport;

const verdictStyle: Record<Verdict, string> = {
  allowed: "bg-ok/10 text-ok border-ok/30",
  allowed_with_conditions: "bg-amber-50 text-amber-700 border-amber-300",
  not_allowed: "bg-danger/10 text-danger border-danger/30",
};

const pct = (v: number | null | undefined, digits = 0) => (v == null ? "—" : `${(v * 100).toFixed(digits)}%`);

export default function PassportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { t, lang } = useLanguage();
  const [passport, setPassport] = useState<Passport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pdfLang, setPdfLang] = usePdfLang();

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

  const pdfUrl = passport ? api.passportPdfUrl(passport.id, pdfLang) : "";
  const r = passport?.robustness;

  return (
    <PageShell title={t(d.title)} subtitle={t(d.subtitle)} icon={PassportIcon} step="passport" backHref="/crash-test">
      {error && <ErrorBox message={error} onRetry={retry} />}

      {!passport && !error && (
        <p role="status" className="flex items-center gap-2 text-sm text-muted">
          <Spinner /> {t(dictionary.common.loading)}
        </p>
      )}

      {passport && r && (
        <div className="space-y-6">
          <Card className="space-y-6 print:border-0 print:p-0">
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-6">
              <div>
                <p className="text-xs text-muted">MedSeal · № {passport.id}</p>
                <p className="mt-1 text-2xl font-semibold">{passport.model.name}</p>
                <p className="text-sm text-muted">{passport.model.version}</p>
              </div>
              <div className={`rounded-2xl border px-4 py-3 text-right ${verdictStyle[passport.verdict]}`}>
                <p className="text-xs opacity-80">{t(d.verdictLabel)}</p>
                <p className="text-lg font-semibold">{t(d.verdicts[passport.verdict])}</p>
              </div>
            </div>

            {passport.conditions.length > 0 && (
              <div className="rounded-xl bg-amber-50 p-4 text-sm text-amber-800">
                <p className="font-semibold">{t(d.conditions)}</p>
                <ul className="mt-2 list-disc space-y-1 pl-5">
                  {passport.conditions.map((c) => (
                    <li key={c}>{t(d.conditionTexts[c])}</li>
                  ))}
                </ul>
                <p className="mt-3 text-xs opacity-80">
                  {t(d.rule).replaceAll("{allow}", String(passport.rules.allow_score))}
                </p>
              </div>
            )}

            <div className="grid gap-6 sm:grid-cols-[200px_1fr]">
              <div>
                <p className="text-xs text-muted">{t(d.robustness)}</p>
                <p className="text-5xl font-semibold tracking-tight">
                  {r.score.toFixed(1)}
                  <span className="text-xl text-muted"> / 10</span>
                </p>
                <p className="mt-2 text-xs text-muted">{t(dictionary.crash.scoreFormula)}</p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                {passport.model.intended_use && (
                  <Field label={t(d.intendedUse)} value={passport.model.intended_use} />
                )}
                {passport.organisation && <Field label={t(d.organisation)} value={passport.organisation} />}
                <Field label={t(d.fingerprint)} value={passport.fingerprint} mono />
                <Field label={t(d.verifyPath)} value={passport.verify_url} mono />
                <Field label={t(d.shieldCompatible)} value={yesNo(passport.shield.compatible)} />
                {passport.shield.available && (
                  <>
                    <Field label={t(d.shieldDetection)} value={pct(passport.shield.detection_pgd_eps1)} />
                    <Field label={t(d.shieldFalseAlarms)} value={pct(passport.shield.false_positive_rate, 1)} />
                    {passport.shield.confidence_intervals && (
                      <>
                        <Field
                          label={t(d.shieldCi)}
                          value={`${pct(passport.shield.confidence_intervals.detection_pgd_eps1.lower)} / ${pct(passport.shield.confidence_intervals.detection_pgd_eps1.upper)}`}
                        />
                        <Field
                          label={t(d.shieldFalseAlarms)}
                          value={`${pct(passport.shield.confidence_intervals.false_positive_rate.lower, 2)} / ${pct(passport.shield.confidence_intervals.false_positive_rate.upper, 2)}`}
                        />
                      </>
                    )}
                    <p className="col-span-full text-xs text-amber-800">{t(d.adaptiveNote)}</p>
                  </>
                )}
                <Field label={t(d.activeDevices)} value={passport.pipeline.devices_active} />
                <Field label={t(d.sealsCount)} value={passport.pipeline.seals} />
                <Field label={t(d.ledgerIntegrity)} value={passport.pipeline.ledger_ok ? t(dictionary.common.yes) : t(dictionary.common.no)} />
                <Field label={t(d.crashTest)} value={`${r.crash_test_id} · ${r.method.toUpperCase()}`} />
                <Field label={t(d.imagesRequested)} value={r.n_requested} />
                <Field label={t(d.imagesLoaded)} value={r.n_images} />
                <Field label={t(d.protocolLabel)} value={t(d.protocolValue)} />
                <Field
                  label={t(d.date)}
                  value={new Date(passport.created_at).toLocaleDateString(localeOf(lang))}
                />
              </div>
            </div>

            {Object.keys(r.flip_rate).length > 0 && (
              <div>
                <p className="text-xs text-muted">{t(dictionary.crash.chartTitle)}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {Object.entries(r.flip_rate)
                    .sort(([a], [b]) => Number(a) - Number(b))
                    .map(([eps, v]) => (
                      <span key={eps} className="rounded-lg bg-slate-100 px-3 py-1.5 text-xs">
                        eps {eps}: <b>{Math.round(v * 100)}%</b>
                      </span>
                    ))}
                </div>
              </div>
            )}

            <DoctorNote />
          </Card>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center print:hidden">
            {pdfUrl && <PdfLangPicker value={pdfLang} onChange={setPdfLang} />}
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
