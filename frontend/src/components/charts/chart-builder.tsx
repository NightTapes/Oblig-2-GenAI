"use client";
import { useState } from "react";
import { Plus } from "lucide-react";
import { Dialog, DialogContent } from "../ui/dialog";
import { Button } from "../ui/button";
import { api } from "@/lib/api";
import {
  chartSpecSchema,
  type Profile,
  type Chart,
  type ChartSpec,
} from "@/lib/schemas";
import { label } from "@/lib/utils";
export function ChartBuilder({
  profile,
  onChart,
}: {
  profile: Profile;
  onChart: (chart: Chart) => void;
}) {
  const [open, setOpen] = useState(false),
    [type, setType] = useState<ChartSpec["chart_type"]>("histogram"),
    [x, setX] = useState(""),
    [y, setY] = useState(""),
    [color, setColor] = useState(""),
    [agg, setAgg] = useState<ChartSpec["aggregation"]>("mean"),
    [title, setTitle] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const numeric = profile.columns.filter((c) => c.kind === "numeric"),
    cats = profile.columns.filter(
      (c) =>
        ["categorical", "boolean"].includes(c.kind) && c.unique_count <= 40,
    ),
    times = profile.columns.filter((c) => c.kind === "datetime");
  const types = (
    [
      { id: "histogram", text: "Histogram", valid: numeric.length > 0 },
      { id: "scatter", text: "Scatter plot", valid: numeric.length > 1 },
      {
        id: "line",
        text: "Line chart",
        valid: times.length > 0 && numeric.length > 0,
      },
      { id: "bar", text: "Bar chart", valid: cats.length > 0 },
      {
        id: "box",
        text: "Box plot",
        valid: cats.length > 0 && numeric.length > 0,
      },
      { id: "heatmap", text: "Correlation heatmap", valid: numeric.length > 1 },
    ] as const
  ).filter((t) => t.valid);
  const xOptions =
    type === "line" ? times : ["bar", "box"].includes(type) ? cats : numeric;
  const actualType = types.some((t) => t.id === type) ? type : types[0]?.id;
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const spec = chartSpecSchema.parse({
        chart_type: type,
        x_column: type === "heatmap" ? null : x || null,
        y_column: ["histogram", "heatmap"].includes(type) ? null : y || null,
        color_column: ["scatter", "line"].includes(type) ? color || null : null,
        aggregation: agg,
        title,
      });
      const chart = await api.chart(profile.id, spec);
      onChart(chart);
      setOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create chart.");
    } finally {
      setBusy(false);
    }
  }
  function changeType(value: ChartSpec["chart_type"]) {
    setType(value);
    setX("");
    setY("");
    setColor("");
    setError("");
  }
  return (
    <>
      <Button
        variant="outline"
        onClick={() => {
          if (actualType) changeType(actualType);
          setOpen(true);
        }}
        disabled={!types.length}
      >
        <Plus size={16} />
        Create chart
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          title="Create a visualization"
          description="Choose your variables. Every chart uses your actual dataset."
        >
          <form onSubmit={submit} className="form-grid">
            <label>
              Chart type
              <select
                value={type}
                onChange={(e) =>
                  changeType(e.target.value as ChartSpec["chart_type"])
                }
              >
                {types.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.text}
                  </option>
                ))}
              </select>
            </label>
            {type !== "heatmap" && (
              <label>
                {type === "histogram" ? "Variable" : "X axis / group"}
                <select
                  value={x}
                  onChange={(e) => setX(e.target.value)}
                  required
                >
                  <option value="">Select a variable</option>
                  {xOptions.map((c) => (
                    <option key={c.name} value={c.name}>
                      {label(c.name)}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {!["histogram", "heatmap"].includes(type) && (
              <label>
                {type === "bar"
                  ? "Measurement (optional for count)"
                  : "Y axis / measurement"}
                <select
                  value={y}
                  onChange={(e) => setY(e.target.value)}
                  required={type !== "bar" || agg !== "count"}
                >
                  <option value="">Select a variable</option>
                  {numeric
                    .filter((c) => type !== "scatter" || c.name !== x)
                    .map((c) => (
                      <option key={c.name} value={c.name}>
                        {label(c.name)}
                      </option>
                    ))}
                </select>
              </label>
            )}
            {["bar", "line"].includes(type) && (
              <label>
                Aggregation
                <select
                  value={agg}
                  onChange={(e) =>
                    setAgg(e.target.value as ChartSpec["aggregation"])
                  }
                >
                  {["mean", "median", "sum", "min", "max", "count"].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
            )}
            {["scatter", "line"].includes(type) && (
              <label>
                Color by (optional)
                <select
                  value={color}
                  onChange={(e) => setColor(e.target.value)}
                >
                  <option value="">One series</option>
                  {cats.map((c) => (
                    <option key={c.name} value={c.name}>
                      {label(c.name)}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className="full-width">
              Chart title (optional)
              <input
                value={title}
                maxLength={160}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Give your discovery a title"
              />
            </label>
            {error && (
              <p className="error-message full-width" role="alert">
                {error}
              </p>
            )}
            <Button type="submit" disabled={busy} className="full-width">
              {busy ? "Preparing chart…" : "Add to workspace"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
