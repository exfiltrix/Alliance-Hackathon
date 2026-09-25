"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import PageShell from "@/components/PageShell";
import UploadDropzone from "@/components/UploadDropzone";
import { Button, Card, ErrorBox, Field, Spinner, buttonClass, errorMessage } from "@/components/ui";
import { useLanguage } from "@/lib/language-context";
import dictionary, { localeOf } from "@/lib/dictionary";
import { api, backendUrl } from "@/lib/api";
import type { Device, SealResponse } from "@/lib/types";
import { SealIcon } from "@/components/icons";

const d = dictionary.seal;

export default function SealPage() {
  const { t, lang } = useLanguage();
  const [devices, setDevices] = useState<Device[]>([]);
  const [deviceId, setDeviceId] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [newHospital, setNewHospital] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SealResponse | null>(null);

  const loadDevices = () =>
    api
      .getDevices()
      .then((list) => {
        setDevices(list);
        setDeviceId((cur) => cur ?? list.find((x) => !x.revoked)?.id ?? null);
      })
      .catch((e) => setError(errorMessage(e)));

  useEffect(() => {
    loadDevices();
  }, []);

  const retryDevices = () => {
    setError(null);
    loadDevices();
  };

  const saveDevice = async () => {
    if (!newName.trim()) return;
    try {
      const dev = await api.createDevice(newName.trim(), newHospital.trim());
      setDevices((list) => [...list, dev]);
      setDeviceId(dev.id);
      setAdding(false);
      setNewName("");
      setNewHospital("");
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const submit = async () => {
    if (!file || deviceId == null) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await api.seal(file, deviceId));
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

  const device = devices.find((x) => x.id === result?.device_id);

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
            <Field label={t(d.device)} value={device ? `${device.name} · ${device.hospital}` : `#${result.device_id}`} />
            <Field label={t(d.tiles)} value={result.tiles} />
            <Field label={t(d.uid)} value={result.uid} mono />
            <Field label={t(d.root)} value={`${result.root.slice(0, 16)}…`} mono />
          </div>

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
            <div>
              <label className="text-sm font-medium" htmlFor="device">
                {t(d.device)}
              </label>
              <select
                id="device"
                value={deviceId ?? ""}
                onChange={(e) => setDeviceId(Number(e.target.value))}
                disabled={loading}
                className="mt-2 w-full rounded-xl border border-border bg-white px-3 py-2.5 text-sm outline-none focus:border-accent"
              >
                {devices.map((dev) => (
                  <option key={dev.id} value={dev.id} disabled={dev.revoked}>
                    {dev.name} · {dev.hospital}
                  </option>
                ))}
              </select>
            </div>

            {adding ? (
              <div className="space-y-2">
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder={t(d.deviceName)}
                  aria-label={t(d.deviceName)}
                  className="w-full rounded-xl border border-border px-3 py-2 text-sm outline-none focus:border-accent"
                />
                <input
                  value={newHospital}
                  onChange={(e) => setNewHospital(e.target.value)}
                  placeholder={t(d.hospital)}
                  aria-label={t(d.hospital)}
                  className="w-full rounded-xl border border-border px-3 py-2 text-sm outline-none focus:border-accent"
                />
                <div className="flex gap-2">
                  <Button variant="accent" onClick={saveDevice} disabled={!newName.trim()} className="flex-1">
                    {t(d.save)}
                  </Button>
                  <Button variant="ghost" onClick={() => setAdding(false)} className="flex-1">
                    {t(d.cancel)}
                  </Button>
                </div>
              </div>
            ) : (
              <button type="button" onClick={() => setAdding(true)} className="text-sm font-medium text-accent">
                {t(d.addDevice)}
              </button>
            )}

            <Button onClick={submit} disabled={!file || deviceId == null || loading} className="w-full">
              {loading && <Spinner />}
              {loading ? t(d.sealing) : t(d.submit)}
            </Button>

            <p className="text-xs text-muted">{t(d.gatewayNote)}</p>
          </Card>
        </div>
      )}

      {error && (
        <div className="mt-6">
          <ErrorBox message={error} onRetry={devices.length ? undefined : retryDevices} />
        </div>
      )}
    </PageShell>
  );
}
