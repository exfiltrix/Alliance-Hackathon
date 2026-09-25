"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import PageShell from "@/components/PageShell";
import { Card, ErrorBox, Spinner, buttonClass, errorMessage } from "@/components/ui";
import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";
import { api } from "@/lib/api";
import type { Stats } from "@/lib/types";
import { ChartIcon } from "@/components/icons";

const d = dictionary.dashboard;

export default function DashboardPage() {
  const { t } = useLanguage();
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    api
      .getStats()
      .then(setStats)
      .catch((e) => setError(errorMessage(e)));

  useEffect(() => {
    load();
  }, []);

  const retry = () => {
    setError(null);
    load();
  };

  const tiles = stats
    ? [
        { label: t(d.sealed), value: stats.sealed },
        { label: t(d.verified), value: stats.verified },
        { label: t(d.tampered), value: stats.tampered, danger: true },
        { label: t(d.unsigned), value: stats.unsigned },
        { label: t(d.modelsTested), value: stats.models_tested },
        { label: t(d.avgRobustness), value: `${stats.avg_robustness.toFixed(1)} / 10` },
      ]
    : [];

  return (
    <PageShell title={t(d.title)} subtitle={t(d.subtitle)} icon={ChartIcon}>
      {error && <ErrorBox message={error} onRetry={retry} />}

      {!stats && !error && (
        <p className="flex items-center gap-2 text-sm text-muted">
          <Spinner /> {t(dictionary.common.loading)}
        </p>
      )}

      {stats && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
          {tiles.map((x) => (
            <Card key={x.label}>
              <p className="text-xs text-muted">{x.label}</p>
              <p className={`mt-2 text-3xl font-semibold tracking-tight ${x.danger ? "text-danger" : ""}`}>
                {x.value}
              </p>
            </Card>
          ))}
        </div>
      )}

      <div className="mt-8 flex flex-col gap-3 sm:flex-row">
        <Link href="/seal" className={buttonClass("dark")}>
          {t(dictionary.home.ctaPrimary)}
        </Link>
        <Link href="/verify" className={buttonClass("accent")}>
          {t(dictionary.home.ctaSecondary)}
        </Link>
        <Link href="/crash-test" className={buttonClass("ghost")}>
          {t(dictionary.crash.start)}
        </Link>
      </div>
    </PageShell>
  );
}
