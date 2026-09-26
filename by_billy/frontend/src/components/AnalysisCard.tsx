"use client";

import { Card, ProgressBar } from "@/components/ui";
import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";
import type { Analysis } from "@/lib/types";

const d = dictionary.verify.analysis;
const URGENCY_CLASS = {
  urgent: "bg-danger/10 text-danger",
  soon: "bg-amber-100 text-amber-800",
  routine: "bg-slate-100 text-muted",
} as const;
export const RISK_CLASS = {
  high: "border-danger/40 bg-danger/10 text-danger",
  medium: "border-amber-300 bg-amber-50 text-amber-900",
  none: "border-ok/30 bg-ok/10 text-ok",
} as const;

/** AI reading + referral (API.md "analysis"). Probabilities, never a diagnosis — the doctor decides. */
export default function AnalysisCard({ analysis }: { analysis: Analysis | null | undefined }) {
  const { t } = useLanguage();
  if (!analysis) return null;
  const name = (p: string) => (d.pathology[p] ? t(d.pathology[p]) : p);

  if (analysis.status === "blocked") {
    return (
      <Card className="border-danger/40 bg-danger/5">
        <p className="text-sm font-semibold">{t(d.blockedTitle)}</p>
        <p className="mt-2 text-sm text-danger">{t(d.blocked[analysis.reason])}</p>
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold">{t(d.title)}</p>
        <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">
          {t(dictionary.verify.warning)}
        </span>
      </div>

      <div role="status" className={`mt-3 rounded-xl border px-4 py-3 ${RISK_CLASS[analysis.risk]}`}>
        <p className="text-xs font-medium opacity-80">{t(d.riskTitle)}</p>
        <p className="mt-0.5 text-base font-semibold">{t(d.risk[analysis.risk].title)}</p>
        <p className="mt-1 text-sm">{t(d.risk[analysis.risk].text)}</p>
      </div>

      <p className="mt-4 text-xs font-medium text-muted">{t(d.findingsTitle)}</p>
      {analysis.findings.length === 0 ? (
        <p className="mt-1 font-semibold text-ok">{t(d.noFindings)}</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {analysis.findings.map((f) => (
            <li key={f.pathology}>
              <div className="flex justify-between text-sm">
                <span>{name(f.pathology)}</span>
                <span className="font-medium tabular-nums">{Math.round(f.probability * 100)}%</span>
              </div>
              <ProgressBar value={f.probability} label={name(f.pathology)} color="bg-amber-500" />
            </li>
          ))}
        </ul>
      )}
      <p className="mt-1 text-xs text-muted">
        {t(d.shownAbove)} {Math.round(analysis.threshold * 100)}%
      </p>

      <p className="mt-4 text-xs font-medium text-muted">{t(d.referralTitle)}</p>
      <ul className="mt-2 space-y-2">
        {analysis.referrals.map((r) => (
          <li key={r.specialty} className="rounded-lg border border-border px-3 py-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold">{t(d.specialty[r.specialty])}</span>
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${URGENCY_CLASS[r.urgency]}`}>
                {t(d.urgency[r.urgency])}
              </span>
            </div>
            {r.pathologies.length > 0 && (
              <p className="mt-1 text-xs text-muted">{r.pathologies.map(name).join(", ")}</p>
            )}
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-muted">{t(d.experimental)}</p>
    </Card>
  );
}
