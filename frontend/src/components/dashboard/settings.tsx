import { FlaskConical, ShieldCheck } from "lucide-react";
import { Button } from "../ui/button";
import type { AIStatus } from "@/lib/schemas";
export function SettingsView({
  status,
  maxSize,
  ttlSeconds,
  onRefresh,
}: {
  status: AIStatus | null;
  maxSize: number;
  ttlSeconds: number;
  onRefresh: () => void;
}) {
  return (
    <div className="settings-grid">
      <section className="panel settings-card">
        <ShieldCheck size={28} />
        <h2>Local by design</h2>
        <p>
          Uploaded datasets are processed on this application’s backend server.
          The assistant connects only to your locally configured Ollama service.
        </p>
        <dl>
          <dt>Model</dt>
          <dd>{status?.model || "qwen3:4b"}</dd>
          <dt>AI connection</dt>
          <dd>{status?.available ? "Available" : "Offline"}</dd>
          <dt>Upload limit</dt>
          <dd>{maxSize} MB per CSV</dd>
          <dt>Dataset lifetime</dt>
          <dd>Temporary; {Math.round(ttlSeconds / 60)} minutes</dd>
          <dt>Storage</dt>
          <dd>Session-scoped backend files</dd>
        </dl>
        <Button variant="outline" onClick={onRefresh}>
          Refresh AI connection
        </Button>
      </section>
      <section className="panel settings-card">
        <FlaskConical size={28} />
        <h2>Made for careful exploration</h2>
        <p>
          Statistics are calculated in Python on all eligible data. AI
          explanations are labeled separately. Correlation describes association
          and does not prove causality.
        </p>
        <p>
          Blank cells count as missing. Original cell values remain visible in
          the explorer. Dates are inferred and normalized to UTC for time
          charts; review date conventions in your source CSV.
        </p>
        <p>
          This unauthenticated university MVP is intended for a trusted local
          computer. Keep your session cookie private. Restarting the backend
          clears datasets.
        </p>
        <p>
          Change service configuration in your environment file. Setup
          instructions are in the repository README.
        </p>
      </section>
    </div>
  );
}
