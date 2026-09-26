"use client";

import { useCallback, useEffect, useState } from "react";
import PageShell from "@/components/PageShell";
import { Button, Card, DoctorNote, ErrorBox, Spinner, errorMessage } from "@/components/ui";
import { useLanguage } from "@/lib/language-context";
import dictionary, { localeOf } from "@/lib/dictionary";
import { api, pngSrc } from "@/lib/api";
import { setDoctorSession } from "@/components/Header";
import type { AutomationStatus, InboxItem, InboxListing, InboxQuery, Severity, VerifyResponse } from "@/lib/types";
import { InboxIcon } from "@/components/icons";

const d = dictionary.inbox;
const REFRESH_MS = 3000;
const PAGE_SIZE = 50;

const tone: Record<Severity, { bar: string; chip: string; dot: string }> = {
  danger: { bar: "border-l-danger", chip: "bg-danger/10 text-danger", dot: "bg-danger" },
  warning: { bar: "border-l-amber-400", chip: "bg-amber-100 text-amber-800", dot: "bg-amber-400" },
  ok: { bar: "border-l-ok", chip: "bg-ok/10 text-ok", dot: "bg-ok" },
};

const inputClass = "rounded-xl border border-border bg-white px-3 py-2 text-sm";

function csvCell(v: unknown): string {
  const s = String(v ?? "");
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function download(blobOrUrl: Blob | string, filename: string) {
  const url = typeof blobOrUrl === "string" ? blobOrUrl : URL.createObjectURL(blobOrUrl);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

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
  const { t, lang } = useLanguage();
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
        <a
          href={api.inboxItemPdfUrl(item.id, lang)}
          target="_blank"
          rel="noreferrer"
          className="block text-center text-xs font-medium text-accent underline underline-offset-2"
        >
          {t(d.downloadPdf)}
        </a>
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

type Batch = { total: number; done: number; ok: number; review: number; block: number; ids: number[] };

export default function InboxPage() {
  const { t, lang } = useLanguage();
  const [listing, setListing] = useState<InboxListing | null>(null);
  const [auto, setAuto] = useState<AutomationStatus | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [severity, setSeverity] = useState<Severity | "">("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [query, setQuery] = useState<InboxQuery>({});

  const load = useCallback(
    (extra: InboxQuery = {}, append = false) => {
      const q = { ...query, ...extra, limit: PAGE_SIZE };
      api
        .getInbox(q)
        .then((res) => {
          setDoctorSession();
          setListing((prev) => (append && prev ? { ...res, items: [...prev.items, ...res.items] } : res));
          setError(null);
        })
        .catch((e) => setError(errorMessage(e)));
      api.getAutomation().then(setAuto).catch(() => undefined);
    },
    [query]
  );

  useEffect(() => {
    load();
    const timer = setInterval(() => load(), REFRESH_MS); // folder automation adds items on its own
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  const applyFilters = () => {
    setQuery({ severity: severity || undefined, since: since || undefined, until: until || undefined });
  };
  const resetFilters = () => {
    setSeverity("");
    setSince("");
    setUntil("");
    setQuery({});
  };
  const loadMore = () => load({ offset: listing?.items.length ?? 0 }, true);

  const upload = async (files: File[]) => {
    setBusy(true);
    setError(null);
    setBatch({ total: files.length, done: 0, ok: 0, review: 0, block: 0, ids: [] });
    try {
      for (const file of files) {
        const [item] = await api.uploadToInbox([file]);
        setBatch((b) =>
          b && {
            ...b,
            done: b.done + 1,
            ids: [...b.ids, item.id],
            ok: b.ok + (item.severity === "ok" ? 1 : 0),
            review: b.review + (item.severity === "warning" ? 1 : 0),
            block: b.block + (item.severity === "danger" ? 1 : 0),
          }
        );
      }
      load();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const exportCsv = async () => {
    const full = await api.getInbox({ ...query, limit: 500, offset: 0 }).catch((e) => {
      setError(errorMessage(e));
      return null;
    });
    if (!full) return;
    const header = ["id", "file_name", "received_at", "status", "severity", "reasons", "device", "changed_tiles", "detective_probability", "reviewed"];
    const rows = full.items.map((i) => [
      i.id, i.file_name, i.received_at, i.status, i.severity, i.reasons.join(" "), i.device ?? "",
      i.changed_tiles, i.detective_probability ?? "", i.reviewed ? "1" : "0",
    ]);
    const csv = [header, ...rows].map((r) => r.map(csvCell).join(",")).join("\r\n");
    download(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }), "medseal-inbox.csv");
  };

  const downloadBatchPdf = async () => {
    if (!batch?.ids.length) return;
    try {
      const url = await api.batchPdfUrl(batch.ids, lang);
      download(url, "medseal-batch.pdf");
    } catch (e) {
      setError(errorMessage(e));
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
  const volume = listing?.volume;

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

        {volume && (
          <div className="grid grid-cols-3 gap-3">
            {([["today", d.volumeToday], ["week", d.volumeWeek], ["all", d.volumeAll]] as const).map(([k, label]) => (
              <Card key={k} className="bg-white/60">
                <p className="text-xs text-muted">{t(label)}</p>
                <p className="mt-1 text-2xl font-semibold tracking-tight">{volume[k]}</p>
              </Card>
            ))}
          </div>
        )}

        <Card className="flex flex-wrap items-end gap-3">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted">{t(d.filters)}</span>
          <select value={severity} onChange={(e) => setSeverity(e.target.value as Severity | "")} className={inputClass}>
            <option value="">{t(d.filterAll)}</option>
            <option value="danger">{t(d.danger)}</option>
            <option value="warning">{t(d.warning)}</option>
            <option value="ok">{t(d.ok)}</option>
          </select>
          <label className="flex items-center gap-1.5 text-xs text-muted">
            {t(d.filterFrom)}
            <input type="date" value={since} onChange={(e) => setSince(e.target.value)} className={inputClass} />
          </label>
          <label className="flex items-center gap-1.5 text-xs text-muted">
            {t(d.filterTo)}
            <input type="date" value={until} onChange={(e) => setUntil(e.target.value)} className={inputClass} />
          </label>
          <Button variant="dark" onClick={applyFilters}>{t(d.filterApply)}</Button>
          <Button variant="ghost" onClick={resetFilters}>{t(d.filterReset)}</Button>
          <span className="flex-1" />
          <Button variant="ghost" onClick={exportCsv} disabled={!listing?.items.length}>
            {t(d.exportCsv)}
          </Button>
        </Card>

        <MultiDrop onFiles={upload} busy={busy} />

        {batch && (
          <Card>
            <p className="mb-2 flex items-center justify-between text-sm font-semibold">
              <span>{t(d.batchMode)}</span>
              <span className="font-normal text-muted">{t(d.batchProgress).replace("{done}", String(batch.done)).replace("{total}", String(batch.total))}</span>
            </p>
            <div className="h-2 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${(100 * batch.done) / batch.total}%` }} />
            </div>
            <div className="mt-3 flex flex-wrap gap-4 text-sm">
              <span className="text-ok">{t(d.batchOk)}: {batch.ok}</span>
              <span className="text-amber-700">{t(d.batchReview)}: {batch.review}</span>
              <span className="text-danger">{t(d.batchBlock)}: {batch.block}</span>
              {!busy && batch.ids.length > 0 && (
                <button onClick={downloadBatchPdf} className="ml-auto text-xs font-medium text-accent underline underline-offset-2">
                  {t(d.batchDownloadPdf)}
                </button>
              )}
            </div>
          </Card>
        )}

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

        {error && <ErrorBox message={error} onRetry={() => load()} />}

        {!listing && !error && (
          <p role="status" className="flex items-center gap-2 text-sm text-muted">
            <Spinner /> {t(dictionary.common.loading)}
          </p>
        )}

        {listing && listing.items.length === 0 && <Card className="text-sm text-muted">{t(d.empty)}</Card>}

        {listing && listing.items.length > 0 && (
          <>
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
                  {open === item.id && <Detail item={item} onReviewed={() => load()} />}
                </li>
              ))}
            </ul>
            {listing.items.length >= PAGE_SIZE && listing.items.length < listing.counts.total && (
              <div className="text-center">
                <Button variant="ghost" onClick={loadMore}>{t(d.loadMore)}</Button>
              </div>
            )}
          </>
        )}
      </div>
    </PageShell>
  );
}
