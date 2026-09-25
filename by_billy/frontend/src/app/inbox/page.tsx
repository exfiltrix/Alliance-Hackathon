"use client";

import { useCallback, useEffect, useState } from "react";
import PageShell from "@/components/PageShell";
import { Button, Card, DoctorNote, ErrorBox, Spinner, errorMessage } from "@/components/ui";
import { useLanguage } from "@/lib/language-context";
import dictionary, { localeOf } from "@/lib/dictionary";
import { api, pngSrc } from "@/lib/api";
import type { AutomationStatus, InboxItem, InboxListing, Severity, VerifyResponse } from "@/lib/types";
import { InboxIcon } from "@/components/icons";

const d = dictionary.inbox;
const REFRESH_MS = 3000;

const tone: Record<Severity, { bar: string; chip: string; dot: string }> = {
  danger: { bar: "border-l-danger", chip: "bg-danger/10 text-danger", dot: "bg-danger" },
  warning: { bar: "border-l-amber-400", chip: "bg-amber-100 text-amber-800", dot: "bg-amber-400" },
  ok: { bar: "border-l-ok", chip: "bg-ok/10 text-ok", dot: "bg-ok" },
};

function MultiDrop({ onFiles, busy }: { onFiles: (files: File[]) => void; busy: boolean }) {
  const { t } = useLanguage();
  const [over, setOver] = useState(false);
  return (
    <label
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        if (!busy && e.dataTransfer.files.length) onFiles(Array.from(e.dataTransfer.files));
      }}
      className={`glass flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-6 py-8 text-center transition-colors focus-within:outline focus-within:outline-2 focus-within:outline-accent ${
        over ? "border-accent bg-accent-soft/60" : "border-accent/30 hover:border-accent/60"
      } ${busy ? "cursor-wait opacity-70" : ""}`}
    >
      <input
        type="file"
        multiple
        accept=".dcm,.dicom,.png"
        className="sr-only"
        disabled={busy}
        onChange={(e) => {
          if (e.target.files?.length) onFiles(Array.from(e.target.files));
          e.target.value = "";
        }}
      />
      {busy ? (
        <span className="flex items-center gap-2 text-sm font-medium">
          <Spinner /> {t(d.checking)}
        </span>
      ) : (
        <>
          <span className="text-sm font-medium">{t(d.dropMany)}</span>
          <span className="text-xs text-muted">DICOM (.dcm) · PNG</span>
        </>
      )}
    </label>
  );
}

function Detail({ item, onReviewed }: { item: InboxItem; onReviewed: () => void }) {
  const { t } = useLanguage();
  const [result, setResult] = useState<VerifyResponse | { error: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.getInboxItem(item.id).then((x) => setResult(x.result)).catch(() => setResult({ error: "—" }));
  }, [item.id]);

  const review = async () => {
    setBusy(true);
    await api.reviewInboxItem(item.id).catch(() => undefined);
    setBusy(false);
    onReviewed();
  };

  if (!result) {
    return (
      <p className="flex items-center gap-2 px-4 pb-4 text-sm text-muted">
        <Spinner /> {t(dictionary.common.loading)}
      </p>
    );
  }
  return (
    <div className="grid gap-4 border-t border-border px-4 py-4 sm:grid-cols-[minmax(0,1fr)_240px]">
      {"preview_png" in result ? (
        <div className="flex justify-center overflow-hidden rounded-xl bg-black">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={pngSrc(result.preview_png)} alt={item.file_name} className="block max-h-[360px] w-auto max-w-full" />
        </div>
      ) : (
        <p className="text-sm text-danger">{"error" in result ? result.error : ""}</p>
      )}
      <div className="space-y-3 text-sm">
        {"preview_png" in result && result.shield && (
          <p className={result.shield.attack_suspected ? "text-danger" : "text-ok"}>
            {t(dictionary.verify.shieldTitle)}:{" "}
            {result.shield.attack_suspected ? t(dictionary.verify.shieldFlag) : t(dictionary.verify.shieldClean)}
          </p>
        )}
        <DoctorNote />
        {!item.reviewed && (
          <Button variant="ghost" onClick={review} disabled={busy} className="w-full">
            {busy && <Spinner />}
            {t(d.markReviewed)}
          </Button>
        )}
      </div>
    </div>
  );
}

export default function InboxPage() {
  const { t, lang } = useLanguage();
  const [listing, setListing] = useState<InboxListing | null>(null);
  const [auto, setAuto] = useState<AutomationStatus | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api.getInbox().then(setListing).catch((e) => setError(errorMessage(e)));
    api.getAutomation().then(setAuto).catch(() => undefined);
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, REFRESH_MS); // folder automation adds items on its own
    return () => clearInterval(timer);
  }, [refresh]);

  const upload = async (files: File[]) => {
    setBusy(true);
    setError(null);
    try {
      await api.uploadToInbox(files);
      refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const describe = (item: InboxItem) => {
    if (item.severity === "ok") return t(d.allGood);
    const parts = item.reasons.map((r) => t(d.reasons[r]));
    if (item.changed_tiles) parts.push(`${item.changed_tiles} ${t(d.tiles)}`);
    if (item.detective_probability != null)
      parts.push(`${t(d.fake)} ${Math.round(item.detective_probability * 100)}%`);
    return parts.join(" · ");
  };

  const counts = listing?.counts;

  return (
    <PageShell title={t(d.title)} subtitle={t(d.subtitle)} icon={InboxIcon}>
      <div className="space-y-6">
        {counts && (
          <div className="grid grid-cols-3 gap-3">
            {(["danger", "warning", "ok"] as const).map((s) => (
              <Card key={s} className={`border-l-4 ${tone[s].bar}`}>
                <p className="text-xs text-muted">{t(d[s])}</p>
                <p className="mt-1 text-3xl font-semibold tracking-tight">{counts[s]}</p>
              </Card>
            ))}
          </div>
        )}

        <MultiDrop onFiles={upload} busy={busy} />

        {auto && (
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
            <span className={`inline-block h-2 w-2 rounded-full ${auto.watching ? "bg-ok" : "bg-slate-300"}`} />
            <b className="font-semibold">{t(d.auto)}</b> {auto.watching ? t(d.autoOn) : t(d.autoOff)}
            {auto.watching && (
              <>
                <span>· {t(d.scannerFolder)}: <code>{auto.scanner_dir}</code></span>
                <span>· {t(d.incomingFolder)}: <code>{auto.incoming_dir}</code></span>
              </>
            )}
            {auto.last_event && (
              <span>
                · {t(d.lastEvent)}: {auto.last_event.text}
              </span>
            )}
          </p>
        )}

        {error && <ErrorBox message={error} onRetry={refresh} />}

        {!listing && !error && (
          <p role="status" className="flex items-center gap-2 text-sm text-muted">
            <Spinner /> {t(dictionary.common.loading)}
          </p>
        )}

        {listing && listing.items.length === 0 && <Card className="text-sm text-muted">{t(d.empty)}</Card>}

        {listing && listing.items.length > 0 && (
          <ul className="space-y-2" aria-live="polite">
            {listing.items.map((item) => (
              <li
                key={item.id}
                className={`glass overflow-hidden rounded-2xl border-l-4 ${tone[item.severity].bar} ${item.reviewed ? "opacity-60" : ""}`}
              >
                <button
                  type="button"
                  onClick={() => setOpen(open === item.id ? null : item.id)}
                  aria-expanded={open === item.id}
                  className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-left"
                >
                  <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${tone[item.severity].dot}`} aria-hidden />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold">{item.file_name}</span>
                    <span className="block text-xs text-muted">{describe(item)}</span>
                  </span>
                  <span className="text-xs text-muted">
                    {new Date(item.received_at).toLocaleTimeString(localeOf(lang))} ·{" "}
                    {item.source === "folder" ? t(d.fromFolder) : t(d.fromUpload)}
                    {item.device ? ` · ${item.device}` : ""}
                  </span>
                  {item.reviewed ? (
                    <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600">{t(d.reviewed)}</span>
                  ) : (
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${tone[item.severity].chip}`}>
                      {t(d[item.severity])}
                    </span>
                  )}
                  <span className="text-xs font-medium text-accent">{open === item.id ? t(d.close) : t(d.open)}</span>
                </button>
                {open === item.id && <Detail item={item} onReviewed={refresh} />}
              </li>
            ))}
          </ul>
        )}
      </div>
    </PageShell>
  );
}
