"use client";

import { useState } from "react";
import { useLanguage } from "@/lib/language-context";
import dictionary from "@/lib/dictionary";

export default function UploadDropzone({
  file,
  onFile,
  disabled,
}: {
  file: File | null;
  onFile: (file: File) => void;
  disabled?: boolean;
}) {
  const { t } = useLanguage();
  const [dragging, setDragging] = useState(false);

  return (
    <label
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        const f = e.dataTransfer.files?.[0];
        if (f && !disabled) onFile(f);
      }}
      className={`glass flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-12 text-center transition-colors focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-accent ${
        disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:border-accent/60"
      } ${dragging ? "border-accent bg-accent-soft/60" : "border-accent/30"}`}
    >
      <input
        type="file"
        accept=".dcm,.dicom,.png,.jpg,.jpeg"
        className="sr-only"
        disabled={disabled}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />
      <span aria-hidden className="flex h-12 w-12 items-center justify-center rounded-full bg-accent-soft text-accent">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 16V4M12 4l-4 4M12 4l4 4" />
          <path d="M4 16v3a2 2 0 002 2h12a2 2 0 002-2v-3" />
        </svg>
      </span>
      {file ? (
        <>
          <span className="max-w-full truncate text-sm font-semibold">{file.name}</span>
          <span className="text-xs text-muted">
            {(file.size / 1024).toFixed(0)} KB · {t(dictionary.common.change)}
          </span>
        </>
      ) : (
        <>
          <span className="text-sm font-medium">{t(dictionary.common.upload)}</span>
          <span className="text-xs text-muted">DICOM (.dcm) · PNG · JPG</span>
        </>
      )}
    </label>
  );
}
