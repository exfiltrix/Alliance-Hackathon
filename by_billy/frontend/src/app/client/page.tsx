"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import PageShell from "@/components/PageShell";
import { Card, ErrorBox, Spinner, errorMessage } from "@/components/ui";
import { useLanguage } from "@/lib/language-context";
import dictionary, { localeOf } from "@/lib/dictionary";
import { api } from "@/lib/api";
import type { ClientAlert, ClientDevice, ClientStats, PassportSummary, VerifyStatus } from "@/lib/types";
import { ChartIcon } from "@/components/icons";

const d = dictionary.client;

const VERDICT_TONE: Record<PassportSummary["verdict"], string> = {
  allowed: "bg-ok/10 text-ok",
  allowed_with_conditions: "bg-amber-100 text-amber-800",
  not_allowed: "bg-danger/10 text-danger",
};

const RESULT_TONE: Record<VerifyStatus, string> = {
  authentic: "text-ok",
  tampered: "text-danger",
  forged: "text-danger",
  unsigned: "text-amber-700",
};

export default function ClientCabinetPage() {
  const { t, lang } = useLanguage();
  const [devices, setDevices] = useState<ClientDevice[] | null>(null);
  const [stats, setStats] = useState<ClientStats | null>(null);
  const [alerts, setAlerts] = useState<ClientAlert[] | null>(null);
  const [passports, setPassports] = useState<PassportSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    api.getClientDevices().then(setDevices).catch((e) => setError(errorMessage(e)));
    api.getClientStats().then(setStats).catch((e) => setError(errorMessage(e)));
    api.getClientAlerts().then(setAlerts).catch((e) => setError(errorMessage(e)));
    api.getClientPassports().then(setPassports).catch((e) => setError(errorMessage(e)));
  };

  useEffect(() => {
    load();
  }, []);

  const retry = () => {
    setError(null);
    load();
  };

  const loading = !devices && !stats && !alerts && !passports && !error;

  return (
    <PageShell title={t(d.title)} subtitle={t(d.subtitle)} icon={ChartIcon}>
      <div className="space-y-8">
        {error && <ErrorBox message={error} onRetry={retry} />}
        {loading && (
          <p role="status" className="flex items-center gap-2 text-sm text-muted">
            <Spinner /> {t(dictionary.common.loading)}
          </p>
        )}

        {stats && (
          <section>
            <h2 className="mb-3 text-lg font-semibold tracking-tight">{t(d.statsTitle)}</h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Card>
                <p className="text-xs text-muted">{t(d.sealsToday)}</p>
                <p className="mt-1 text-3xl font-semibold tracking-tight">{stats.seals.today}</p>
              </Card>
              <Card>
                <p className="text-xs text-muted">{t(d.seals7d)}</p>
                <p className="mt-1 text-3xl font-semibold tracking-tight">{stats.seals["7d"]}</p>
              </Card>
              <Card>
                <p className="text-xs text-muted">{t(d.sealsTotal)}</p>
                <p className="mt-1 text-3xl font-semibold tracking-tight">{stats.seals.total}</p>
              </Card>
              <Card>
                <p className="text-xs text-muted">{t(d.verificationsTotal)}</p>
                <p className="mt-1 text-3xl font-semibold tracking-tight">{stats.verifications.total}</p>
              </Card>
            </div>
          </section>
        )}

        {devices && (
          <section>
            <h2 className="mb-3 text-lg font-semibold tracking-tight">{t(d.devices)}</h2>
            {devices.length === 0 ? (
              <Card className="text-sm text-muted">—</Card>
            ) : (
              <Card className="overflow-x-auto p-0">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-border text-xs text-muted">
                    <tr>
                      <th className="px-4 py-3 font-medium">{t(d.deviceName)}</th>
                      <th className="px-4 py-3 font-medium">{t(d.deviceStatus)}</th>
                      <th className="px-4 py-3 font-medium">{t(d.deviceLastSeal)}</th>
                      <th className="px-4 py-3 font-medium">{t(d.deviceSealCount)}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {devices.map((dev) => (
                      <tr key={dev.id} className="border-b border-border last:border-0">
                        <td className="px-4 py-3 font-medium">{dev.name}</td>
                        <td className="px-4 py-3">
                          <span className={dev.revoked ? "text-danger" : "text-ok"}>
                            {dev.revoked ? t(d.deviceRevoked) : t(d.deviceActive)}
                          </span>
                          <span className="mx-1.5 text-muted">·</span>
                          <span className={dev.certified ? "text-ok" : "text-amber-700"}>
                            {dev.certified ? t(d.deviceCertified) : t(d.deviceNotCertified)}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-muted">
                          {dev.last_seal_at ? new Date(dev.last_seal_at).toLocaleString(localeOf(lang)) : t(d.never)}
                        </td>
                        <td className="px-4 py-3">{dev.seal_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            )}
          </section>
        )}

        {alerts && (
          <section>
            <h2 className="mb-3 text-lg font-semibold tracking-tight">{t(d.alertsTitle)}</h2>
            {alerts.length === 0 ? (
              <Card className="text-sm text-muted">{t(d.alertsEmpty)}</Card>
            ) : (
              <ul className="space-y-2">
                {alerts.map((a, i) => (
                  <li key={i} className="glass flex flex-wrap items-center justify-between gap-2 rounded-xl border-l-4 border-l-danger px-4 py-3 text-sm">
                    <span className="font-medium">
                      {a.device ?? "—"} <span className="mx-1 text-muted">·</span>
                      <span className={RESULT_TONE[a.result]}>{a.result}</span>
                    </span>
                    <span className="text-xs text-muted">{new Date(a.at).toLocaleString(localeOf(lang))}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        {passports && (
          <section>
            <h2 className="mb-3 text-lg font-semibold tracking-tight">{t(d.passportsTitle)}</h2>
            {passports.length === 0 ? (
              <Card className="text-sm text-muted">{t(d.passportsEmpty)}</Card>
            ) : (
              <ul className="space-y-2">
                {passports.map((p) => (
                  <li key={p.id}>
                    <Link
                      href={`/passport/${p.id}`}
                      className="glass flex flex-wrap items-center justify-between gap-2 rounded-xl px-4 py-3 text-sm transition-colors hover:bg-white/70"
                    >
                      <span className="font-medium">{p.model.name}</span>
                      <span className="flex items-center gap-2">
                        <span className="text-muted">{p.robustness_score.toFixed(1)} / 10</span>
                        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${VERDICT_TONE[p.verdict]}`}>
                          {t(dictionary.passport.verdicts[p.verdict])}
                        </span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
      </div>
    </PageShell>
  );
}
