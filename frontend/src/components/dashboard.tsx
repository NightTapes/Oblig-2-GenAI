"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  BarChart3,
  Check,
  CheckCheck,
  ChevronRight,
  Columns3,
  Database,
  FileSpreadsheet,
  FlaskConical,
  HelpCircle,
  LayoutDashboard,
  Menu,
  Plus,
  Rows3,
  Settings2,
  ShieldCheck,
  Sparkles,
  Table2,
  Trash2,
  Upload as UploadIcon,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import type { AIStatus, Chart, Profile } from "@/lib/schemas";
import { number } from "@/lib/utils";
import { Button } from "./ui/button";
import { Dialog, DialogContent } from "./ui/dialog";
import { Upload } from "./datasets/upload";
import { DataTable } from "./datasets/data-table";
import { ChartCard } from "./charts/chart-card";
import { ChartBuilder } from "./charts/chart-builder";
import { Assistant } from "./ai/assistant";
import { Quality } from "./dashboard/quality";
import { SettingsView } from "./dashboard/settings";
import { Welcome } from "./dashboard/welcome";
const navigation = [
  { id: "Overview", icon: LayoutDashboard },
  { id: "Visualizations", icon: BarChart3 },
  { id: "Data Explorer", icon: Table2 },
  { id: "Datasets", icon: Database },
  { id: "Settings", icon: Settings2 },
];
export default function Dashboard() {
  const [page, setPage] = useState("Overview"),
    [datasets, setDatasets] = useState<Profile[]>([]),
    [active, setActive] = useState<Profile | null>(null),
    [charts, setCharts] = useState<Chart[]>([]),
    [status, setStatus] = useState<AIStatus | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(true),
    [chartBusy, setChartBusy] = useState(false),
    [progress, setProgress] = useState(0),
    [importOpen, setImportOpen] = useState(false),
    [navOpen, setNavOpen] = useState(false),
    [aiOpen, setAiOpen] = useState(false),
    [maxSize, setMaxSize] = useState(20),
    [ttlSeconds, setTtlSeconds] = useState(7200),
    [recNote, setRecNote] = useState(""),
    [aiBusy, setAiBusy] = useState(false),
    [connected, setConnected] = useState(false);
  const activeId = useRef<string | null>(null),
    generation = useRef(0);
  const refreshStatus = useCallback(() => {
    api
      .status()
      .then(setStatus)
      .catch(() =>
        setStatus({
          available: false,
          model: "qwen3:4b",
          message: "Backend unavailable. Start the API and refresh the status.",
        }),
      );
  }, []);
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const health = await api.health();
        if (!alive) return;
        setConnected(true);
        setMaxSize(health.max_upload_mb);
        setTtlSeconds(health.ttl_seconds);
        const list = await api.datasets();
        if (!alive) return;
        setDatasets(list.datasets);
        if (list.datasets[0]) setActive(list.datasets[0]);
        refreshStatus();
      } catch {
        if (alive)
          setError(
            "Cannot reach the backend. Start the FastAPI server and refresh this page.",
          );
      } finally {
        if (alive) setBusy(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [refreshStatus]);
  useEffect(() => {
    activeId.current = active?.id || null;
    const current = ++generation.current;
    if (!active) {
      setCharts([]);
      return;
    }
    setChartBusy(true);
    setCharts([]);
    api
      .recommendations(active.id)
      .then((r) => {
        if (current === generation.current) {
          setCharts(r.charts);
          setRecNote(r.note);
        }
      })
      .catch((e) => {
        if (current === generation.current) setError(e.message);
      })
      .finally(() => {
        if (current === generation.current) setChartBusy(false);
      });
  }, [active]);
  async function load(source: File | "plants" | "environment") {
    if (busy) return;
    setBusy(true);
    setProgress(5);
    setError("");
    try {
      const p =
        source instanceof File
          ? await api.upload(source, setProgress)
          : await api.sample(source);
      setProgress(100);
      setDatasets((d) => [p, ...d]);
      setActive(p);
      setPage("Overview");
      setImportOpen(false);
      setConnected(true);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not import this dataset.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function refine() {
    if (!active) return;
    const id = active.id;
    setAiBusy(true);
    setError("");
    try {
      const result = await api.recommendations(id, true);
      if (activeId.current !== id) return;
      if (result.ai_refined) setCharts((c) => [...result.charts, ...c]);
      setRecNote(
        result.ai_refined ? `AI overview: ${result.note}` : result.note,
      );
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "AI recommendations unavailable.",
      );
    } finally {
      setAiBusy(false);
    }
  }
  async function remove(p: Profile) {
    try {
      await api.remove(p.id);
      setDatasets((d) => d.filter((x) => x.id !== p.id));
      if (active?.id === p.id)
        setActive(datasets.find((x) => x.id !== p.id) || null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not remove dataset.");
    }
  }
  function navigate(name: string) {
    setPage(name);
    setNavOpen(false);
  }
  const addChart = (chart: Chart) => setCharts((c) => [chart, ...c]);
  return (
    <div className={`app-shell ${aiOpen ? "ai-open" : ""}`}>
      <div
        className={`nav-backdrop ${navOpen ? "visible" : ""}`}
        onClick={() => setNavOpen(false)}
      />
      <aside className={`sidebar ${navOpen ? "open" : ""}`}>
        <a className="brand" href="/" aria-label="DataLens AI home">
          <span className="brand-mark">
            <BarChart3 size={24} />
          </span>
          <span>
            DataLens<span className="brand-ai">AI</span>
            <small>FROM DATA TO DISCOVERY</small>
          </span>
        </a>
        <div className="workspace-label">RESEARCH WORKSPACE</div>
        <nav aria-label="Main navigation">
          {navigation.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${page === item.id ? "active" : ""}`}
              onClick={() => navigate(item.id)}
            >
              <item.icon size={18} strokeWidth={1.7} />
              <span>{item.id}</span>
              {page === item.id && <span className="active-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-dataset">
          <span className="workspace-label">ACTIVE DATASET</span>
          {active ? (
            <>
              <div className="active-file">
                <FileSpreadsheet size={18} />
                <div>
                  <strong title={active.name}>{active.name}</strong>
                  <span>
                    {number(active.row_count)} rows · {active.column_count}{" "}
                    columns
                  </span>
                </div>
                <span className="status-dot online" />
              </div>
              <select
                aria-label="Switch active dataset"
                value={active.id}
                onChange={(e) => {
                  setActive(
                    datasets.find((d) => d.id === e.target.value) || null,
                  );
                  setPage("Overview");
                }}
              >
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </>
          ) : (
            <p className="sidebar-no-data">
              Your next discovery
              <br />
              is one dataset away.
            </p>
          )}
          <Button
            variant="outline"
            className="sidebar-import"
            onClick={() => setImportOpen(true)}
            disabled={busy}
          >
            <Plus size={16} />
            Import dataset
          </Button>
        </div>
        <div className="sidebar-bottom">
          <div className="local-badge">
            <span className="status-dot online" />
            LOCAL-FIRST WORKSPACE
          </div>
          <p>
            Your data. Your environment.
            <br />
            No cloud AI required.
          </p>
          <div className="sidebar-project">
            <span>DL</span>
            <div>
              <strong>Research workspace</strong>
              <small>DataLens AI · v1.0</small>
            </div>
            <FlaskConical size={16} />
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            <Button
              variant="ghost"
              size="icon"
              className="mobile-menu"
              aria-label="Open navigation"
              onClick={() => setNavOpen(true)}
            >
              <Menu size={19} />
            </Button>
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>{page}</strong>
          </div>
          <div className="topbar-actions">
            <span className="backend-status">
              <span className={`status-dot ${connected ? "online" : ""}`} />
              {connected ? "Backend connected" : "Backend offline"}
            </span>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Open settings and help"
              onClick={() => navigate("Settings")}
            >
              <HelpCircle size={18} />
            </Button>
            <button
              className="user-avatar"
              aria-label="Research workspace settings"
              onClick={() => navigate("Settings")}
            >
              DL
            </button>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <span className="eyebrow">YOUR SCIENTIFIC WORKSPACE</span>
              <h1>
                {page === "Overview"
                  ? active
                    ? active.name.replace(/\.csv$/i, "").replaceAll("_", " ")
                    : "From data to discovery."
                  : page}
              </h1>
              <p>
                {page === "Overview"
                  ? active
                    ? "A clearer view of your data. A new perspective on your research."
                    : "Every dataset has a story. Let’s find yours."
                  : page === "Visualizations"
                    ? "See patterns. Explore relationships. Find your next question."
                    : page === "Data Explorer"
                      ? "Get closer to the observations behind your discoveries."
                      : page === "Datasets"
                        ? "Your imported datasets, together in one place."
                        : "A transparent workspace, running on your terms."}
              </p>
            </div>
            <div className="page-actions">
              <Button
                variant="outline"
                className="mobile-ai"
                onClick={() => setAiOpen(true)}
              >
                <Sparkles size={16} />
                Ask AI
              </Button>
              <Button onClick={() => setImportOpen(true)} disabled={busy}>
                <UploadIcon size={16} />
                Import dataset
              </Button>
            </div>
          </div>
          {error && (
            <div className="error-banner" role="alert">
              <span>{error}</span>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Dismiss error"
                onClick={() => setError("")}
              >
                <X size={16} />
              </Button>
            </div>
          )}
          {page === "Settings" ? (
            <SettingsView
              status={status}
              maxSize={maxSize}
              ttlSeconds={ttlSeconds}
              onRefresh={refreshStatus}
            />
          ) : page === "Datasets" ? (
            <>
              <div className="section-heading">
                <h2>
                  Dataset library{" "}
                  <span className="count-badge">{datasets.length}</span>
                </h2>
                <span className="muted">
                  Temporary, private to this browser session
                </span>
              </div>
              {!datasets.length ? (
                <Upload
                  onFile={load}
                  onSample={load}
                  busy={busy}
                  progress={progress}
                  maxSize={maxSize}
                />
              ) : (
                <div className="dataset-grid">
                  {datasets.map((d) => (
                    <article className="panel dataset-card" key={d.id}>
                      <FileSpreadsheet size={27} />
                      <h3>{d.name}</h3>
                      <p>
                        {number(d.row_count)} rows · {d.column_count} columns
                      </p>
                      {d.synthetic && (
                        <span className="tag">Synthetic sample</span>
                      )}
                      <p className="muted">
                        Expires{" "}
                        {new Date(d.expires_at * 1000).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </p>
                      <div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setActive(d);
                            setPage("Overview");
                          }}
                        >
                          {active?.id === d.id ? (
                            <Check size={14} />
                          ) : (
                            <ArrowRight size={14} />
                          )}
                          Explore
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Delete ${d.name}`}
                          onClick={() => remove(d)}
                        >
                          <Trash2 size={16} />
                        </Button>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </>
          ) : !active ? (
            <Welcome
              onLoad={load}
              busy={busy}
              progress={progress}
              maxSize={maxSize}
            />
          ) : (
            <>
              {page !== "Data Explorer" && (
                <>
                  <div className="dataset-context">
                    <span className="dataset-ready">
                      <Check size={13} />
                      DATASET READY
                    </span>
                    {active.synthetic && (
                      <span className="tag">
                        Synthetic sample · illustrative data
                      </span>
                    )}
                    <span>
                      {active.column_count} variables · Original values
                      preserved
                    </span>
                  </div>
                  <div className="stats-grid">
                    {[
                      {
                        label: "Total observations",
                        value: number(active.row_count),
                        icon: Rows3,
                        note: "Rows in your dataset",
                      },
                      {
                        label: "Variables",
                        value: active.column_count,
                        icon: Columns3,
                        note: "Across all data types",
                      },
                      {
                        label: "Missing values",
                        value: `${number(active.missing_percent)}%`,
                        icon: Activity,
                        note: `${number(active.missing_count)} cells need attention`,
                      },
                      {
                        label: "Numerical variables",
                        value: active.numeric_count,
                        icon: BarChart3,
                        note: "Ready for quantitative analysis",
                      },
                    ].map((s, i) => (
                      <div className="stat-card" key={s.label}>
                        <div>
                          <span>{s.label}</span>
                          <s.icon size={17} />
                        </div>
                        <strong>{s.value}</strong>
                        <small>
                          <span className={`stat-dot dot-${i}`} />
                          {s.note}
                        </small>
                      </div>
                    ))}
                  </div>
                </>
              )}
              {page === "Data Explorer" ? (
                <>
                  <div className="section-heading">
                    <div>
                      <h2>Explore your observations</h2>
                      <p>
                        Filtering and sorting run on the full dataset, before
                        pagination.
                      </p>
                    </div>
                    <span className="tag">25 records per page</span>
                  </div>
                  <DataTable key={active.id} profile={active} />
                  <Quality profile={active} />
                </>
              ) : (
                <>
                  <div className="section-heading chart-section-heading">
                    <div>
                      <h2>
                        {page === "Overview"
                          ? "Your data, in perspective"
                          : "Visualization workspace"}{" "}
                        <span className="count-badge">{charts.length}</span>
                      </h2>
                      <p>
                        {recNote ||
                          "Charts chosen for the structure of your data."}
                      </p>
                    </div>
                    <div className="section-actions">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={refine}
                        disabled={aiBusy || !status?.available}
                      >
                        <Sparkles size={14} />
                        {aiBusy ? "Asking Qwen3…" : "AI recommendations"}
                      </Button>
                      <ChartBuilder
                        key={active.id}
                        profile={active}
                        onChart={(chart) => {
                          if (activeId.current === active?.id) addChart(chart);
                        }}
                      />
                    </div>
                  </div>
                  {chartBusy ? (
                    <div className="chart-grid" aria-label="Loading charts">
                      {[1, 2].map((i) => (
                        <div key={i} className="chart-skeleton skeleton" />
                      ))}
                    </div>
                  ) : charts.length ? (
                    <div className="chart-grid">
                      {charts.map((chart) => (
                        <ChartCard
                          key={chart.id}
                          chart={chart}
                          onRemove={() =>
                            setCharts((c) => c.filter((x) => x.id !== chart.id))
                          }
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="panel empty-charts">
                      <BarChart3 size={30} />
                      <h3>A fresh perspective awaits</h3>
                      <p>Create a chart using the variables in this dataset.</p>
                    </div>
                  )}
                  {page === "Overview" && <Quality profile={active} />}
                </>
              )}
            </>
          )}
          <footer className="workspace-footer">
            <span>DataLens AI</span>
            <span>Built for questions worth asking.</span>
            <span>
              <ShieldCheck size={12} />
              Local-first analysis
            </span>
          </footer>
        </main>
      </div>
      <div className={`assistant-wrapper ${aiOpen ? "open" : ""}`}>
        <Assistant
          key={active?.id || "empty"}
          profile={active}
          status={status}
          onChart={(chart) => {
            if (activeId.current === active?.id) addChart(chart);
          }}
          onRefresh={refreshStatus}
          onClose={() => setAiOpen(false)}
        />
      </div>
      {aiOpen && (
        <div className="ai-backdrop" onClick={() => setAiOpen(false)} />
      )}

      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent
          title="Import a dataset"
          description="Your next discovery begins here. Choose a CSV or explore a synthetic sample."
        >
          {error && (
            <p role="alert" className="error-message">
              {error}
            </p>
          )}
          <Upload
            onFile={load}
            onSample={load}
            busy={busy}
            progress={progress}
            maxSize={maxSize}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
