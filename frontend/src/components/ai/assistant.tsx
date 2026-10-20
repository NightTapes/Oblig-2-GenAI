"use client";
import { useState } from "react";
import {
  ArrowUp,
  CheckCheck,
  ChevronDown,
  LoaderCircle,
  MessageSquare,
  RefreshCw,
  Sparkles,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  AIStatus,
  Analysis,
  Chart,
  ChatReply,
  Profile,
} from "@/lib/schemas";
import { label, number } from "@/lib/utils";
import { Button } from "../ui/button";
type Message = {
  id: number;
  question: string;
  reply?: ChatReply;
  error?: string;
};
function Result({ value }: { value: Analysis }) {
  const r = value.result;
  if (value.action === "unsupported") return <p>{value.note}</p>;
  let content: React.ReactNode;
  if (Array.isArray(r.groups))
    content = (
      <div className="verified-table">
        <table>
          <thead>
            <tr>
              <th>Group</th>
              <th>{String(r.aggregation)}</th>
              <th>n</th>
            </tr>
          </thead>
          <tbody>
            {(r.groups as { group: string; value: number; n: number }[]).map(
              (g) => (
                <tr key={g.group}>
                  <td>{g.group}</td>
                  <td>{number(g.value)}</td>
                  <td>{number(g.n)}</td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>
    );
  else if (value.action === "describe_dataset")
    content = (
      <div className="verified-metrics">
        {["row_count", "column_count", "missing_percent", "numeric_count"].map(
          (k) => (
            <div key={k}>
              <span>{label(k)}</span>
              <strong>
                {number(r[k])}
                {k === "missing_percent" ? "%" : ""}
              </strong>
            </div>
          ),
        )}
      </div>
    );
  else if (value.action === "list_missing_values")
    content = (
      <>
        <strong className="result-highlight">
          {number(r.missing_percent)}% missing cells
        </strong>
        <p>
          {number(r.missing_cells)} of {number(r.total_cells)} cells
        </p>
      </>
    );
  else
    content = (
      <div className="verified-metrics">
        {Object.entries(r)
          .filter(([, v]) => v !== null && typeof v !== "object")
          .map(([k, v]) => (
            <div key={k}>
              <span>{k === "pearson_r" ? "Pearson r" : label(k)}</span>
              <strong>{number(v)}</strong>
            </div>
          ))}
      </div>
    );
  return (
    <div className="verified-result">
      <div className="result-label">
        <CheckCheck size={13} />
        VERIFIED RESULT
      </div>
      {content}
      <details>
        <summary>
          Method & limitations <ChevronDown size={12} />
        </summary>
        <p>{value.note}</p>
      </details>
    </div>
  );
}
export function Assistant({
  profile,
  status,
  onChart,
  onRefresh,
  onClose,
}: {
  profile: Profile | null;
  status: AIStatus | null;
  onChart: (chart: Chart) => void;
  onRefresh: () => void;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]),
    [input, setInput] = useState(""),
    [busy, setBusy] = useState(false);
  const numeric = profile?.columns.filter((c) => c.kind === "numeric") || [],
    cats =
      profile?.columns.filter(
        (c) =>
          ["categorical", "boolean"].includes(c.kind) && c.unique_count <= 40,
      ) || [];
  const examples = [
    "What are the most important characteristics of this dataset?",
    "What percentage of the dataset contains missing values?",
    ...(numeric.length > 1
      ? [
          `Create a scatter plot comparing ${numeric[0].name} and ${numeric[1].name}.`,
        ]
      : []),
    ...(numeric.length && cats.length
      ? [
          `Which ${cats[0].name} has the highest average ${numeric[numeric.length - 1].name}?`,
        ]
      : []),
  ];
  async function send(question: string) {
    if (!profile || busy || !status?.available || !question.trim()) return;
    const id = Date.now();
    setMessages((m) => [...m, { id, question }]);
    setInput("");
    setBusy(true);
    try {
      const reply = await api.chat(profile.id, question);
      setMessages((m) => m.map((x) => (x.id === id ? { ...x, reply } : x)));
      if (reply.verified.chart) onChart(reply.verified.chart);
    } catch (e) {
      setMessages((m) =>
        m.map((x) =>
          x.id === id
            ? {
                ...x,
                error:
                  e instanceof Error
                    ? e.message
                    : "Could not reach the assistant.",
              }
            : x,
        ),
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <aside className="assistant">
      <header className="assistant-header">
        <div className="ai-icon">
          <Sparkles size={20} />
        </div>
        <div>
          <h2>Ask DataLens AI</h2>
          <p>Your research copilot</p>
        </div>
        <Button
          className="assistant-dismiss"
          variant="ghost"
          size="icon"
          aria-label="Close assistant"
          onClick={onClose}
        >
          <X size={18} />
        </Button>
      </header>
      <div className="assistant-body">
        <div className="assistant-welcome">
          <div className="mini-ai-icon">
            <Sparkles size={16} />
          </div>
          <p>
            A little curiosity.
            <br />
            <strong>A lot of possibility.</strong>
          </p>
          <span>
            {profile
              ? "Your dataset is ready to explore. Ask a question or try one below."
              : "Bring your data. I’ll help you find the story within it."}
          </span>
        </div>
        {!messages.length && (
          <>
            <span className="eyebrow">
              {profile ? "TRY ASKING" : "WHAT WE CAN EXPLORE"}
            </span>
            <div className="prompt-list">
              {(profile
                ? examples
                : [
                    "Understand your dataset",
                    "Discover patterns & relationships",
                    "Build meaningful visualizations",
                  ]
              ).map((question) => (
                <button
                  key={question}
                  disabled={!profile || busy || !status?.available}
                  onClick={() => send(question)}
                >
                  <MessageSquare size={14} />
                  <span>{question}</span>
                  <span>↗</span>
                </button>
              ))}
            </div>
          </>
        )}
        <div className="messages" aria-live="polite">
          {messages.map((m) => (
            <div className="message-exchange" key={m.id}>
              <div className="user-message">{m.question}</div>
              {m.reply && (
                <div className="ai-message">
                  <Result value={m.reply.verified} />
                  {m.reply.explanation && (
                    <>
                      <div className="explanation-label">
                        <Sparkles size={12} />
                        AI EXPLANATION
                      </div>
                      <p>{m.reply.explanation}</p>
                    </>
                  )}
                  {m.reply.explanation_error && (
                    <div className="chat-error" role="alert">
                      <p>
                        {m.reply.explanation_error} Verified results remain
                        available.
                      </p>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={busy || !status?.available}
                        onClick={() => send(m.question)}
                      >
                        <RefreshCw size={12} />
                        Retry question
                      </Button>
                    </div>
                  )}
                </div>
              )}
              {m.error && (
                <div className="chat-error" role="alert">
                  <p>{m.error}</p>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busy}
                    onClick={() => send(m.question)}
                  >
                    <RefreshCw size={12} />
                    Retry
                  </Button>
                </div>
              )}
            </div>
          ))}
          {busy && (
            <div className="ai-processing" role="status">
              <LoaderCircle size={16} className="spin" /> Interpreting and
              verifying…
            </div>
          )}
        </div>
        <div className="assistant-trust">
          <CheckCheck size={15} />
          <p>
            Calculated with Python.
            <br />
            <span>Explained by local AI.</span>
          </p>
        </div>
      </div>
      <footer className="assistant-footer">
        <div className="model-status">
          <span className={`status-dot ${status?.available ? "online" : ""}`} />
          <span>
            {status?.available
              ? "Qwen3 · Local model installed"
              : "Local AI offline"}
          </span>
          <button onClick={onRefresh} aria-label="Refresh AI status">
            <RefreshCw size={12} />
          </button>
        </div>
        {!status?.available && (
          <p className="offline-help">
            {status?.message || "Checking your local model…"}
          </p>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
          <textarea
            aria-label="Ask about your data"
            rows={2}
            placeholder={
              profile ? "Ask about your data…" : "Import a dataset to begin…"
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            maxLength={2000}
            disabled={!profile || busy}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
          />
          <Button
            size="icon"
            type="submit"
            aria-label="Send question"
            disabled={!profile || busy || !input.trim() || !status?.available}
          >
            <ArrowUp size={18} />
          </Button>
        </form>
        <span className="assistant-footnote">
          AI can make mistakes. Review the verified results.
        </span>
      </footer>
    </aside>
  );
}
