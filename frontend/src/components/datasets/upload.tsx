"use client";
import { useRef, useState } from "react";
import { ArrowUpRight, FileUp, Leaf, Wind } from "lucide-react";
import { Button } from "../ui/button";
export function Upload({
  onFile,
  onSample,
  busy,
  progress,
  maxSize = 20,
}: {
  onFile: (f: File) => void;
  onSample: (name: "plants" | "environment") => void;
  busy: boolean;
  progress: number;
  maxSize?: number;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState("");
  function choose(file?: File) {
    if (!file || busy) return;
    setError("");
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Please choose a .csv file.");
      return;
    }
    if (file.size > maxSize * 1024 * 1024) {
      setError(`This file exceeds the ${maxSize} MB limit.`);
      return;
    }
    onFile(file);
  }
  return (
    <>
      <div
        className={`upload-zone ${drag ? "dragging" : ""} ${busy ? "upload-busy" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          choose(e.dataTransfer.files[0]);
        }}
      >
        <div className="upload-icon">
          <FileUp size={30} strokeWidth={1.5} />
        </div>
        <h3>
          {busy
            ? "Preparing your dataset…"
            : "A new discovery starts with your data"}
        </h3>
        <p>
          {busy
            ? "Uploading, validating, and profiling your CSV."
            : "Drop your CSV here, or choose a file to get started."}
        </p>
        <input
          ref={input}
          className="sr-only"
          aria-label="Upload CSV"
          type="file"
          accept=".csv,text/csv"
          disabled={busy}
          onChange={(e) => {
            choose(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        <Button disabled={busy} onClick={() => input.current?.click()}>
          <FileUp size={16} /> {busy ? "Importing…" : "Choose CSV file"}
        </Button>
        <span className="upload-meta">
          CSV · Up to {maxSize} MB · Processed on your backend
        </span>
        {busy && (
          <div
            className="upload-progress"
            role="progressbar"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Import progress"
          >
            <span style={{ width: `${Math.max(5, progress)}%` }} />
          </div>
        )}
      </div>
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
      <div className="sample-heading">
        <span>OR EXPLORE A SAMPLE</span>
        <span>Thoughtfully generated. Ready to explore.</span>
      </div>
      <div className="sample-grid">
        {(
          [
            {
              id: "plants",
              title: "Plant growth experiment",
              subtitle: "Growth, temperature & treatment groups",
              icon: Leaf,
              tag: "BIOLOGY",
              color: "green",
            },
            {
              id: "environment",
              title: "Environmental monitoring",
              subtitle: "Air quality, humidity & temperature",
              icon: Wind,
              tag: "ENVIRONMENT",
              color: "blue",
            },
          ] as const
        ).map((s) => (
          <button
            className="sample-card"
            key={s.id}
            disabled={busy}
            onClick={() => onSample(s.id)}
          >
            <div className={`sample-icon ${s.color}`}>
              <s.icon size={25} />
            </div>
            <div>
              <span className="eyebrow">
                {s.tag} <span className="synthetic-tag">SYNTHETIC</span>
              </span>
              <h4>{s.title}</h4>
              <p>{s.subtitle}</p>
            </div>
            <ArrowUpRight size={18} />
          </button>
        ))}
      </div>
    </>
  );
}
