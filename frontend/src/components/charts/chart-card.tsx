"use client";
import { useEffect, useRef, useState } from "react";
import type { EChartsType } from "echarts";
import { Download, FileImage, Trash2 } from "lucide-react";
import { Button } from "../ui/button";
import type { Chart } from "@/lib/schemas";
export function ChartCard({
  chart,
  onRemove,
}: {
  chart: Chart;
  onRemove: () => void;
}) {
  const node = useRef<HTMLDivElement>(null),
    instance = useRef<EChartsType | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let disposed = false;
    let observer: ResizeObserver | undefined;
    import("echarts")
      .then((echarts) => {
        if (disposed || !node.current) return;
        instance.current = echarts.init(node.current, undefined, {
          renderer: "canvas",
        });
        instance.current.setOption(chart.option);
        observer = new ResizeObserver(() => instance.current?.resize());
        observer.observe(node.current);
      })
      .catch(() =>
        setError("Chart library could not load. Reload the page to retry."),
      );
    return () => {
      disposed = true;
      observer?.disconnect();
      instance.current?.dispose();
      instance.current = null;
    };
  }, [chart]);
  async function download(type: "png" | "svg") {
    if (!instance.current) return;
    let href: string;
    if (type === "svg") {
      const echarts = await import("echarts");
      const host = document.createElement("div");
      const svg = echarts.init(host, undefined, {
        renderer: "svg",
        width: 1000,
        height: 600,
      });
      svg.setOption(chart.option);
      href = svg.getDataURL({
        type: "svg",
        excludeComponents: ["dataZoom", "toolbox"],
      });
      svg.dispose();
    } else
      href = instance.current.getDataURL({
        type: "png",
        pixelRatio: 2,
        backgroundColor: "#fff",
      });
    const link = document.createElement("a");
    link.download = `${(chart.spec.title || chart.spec.chart_type).replace(/[^a-z0-9_-]/gi, "_")}.${type}`;
    link.href = href;
    link.click();
  }
  return (
    <article className="chart-card">
      <header>
        <div>
          <span className="eyebrow">
            {chart.spec.chart_type} <span className="dot-separator">·</span>{" "}
            {chart.source === "ai"
              ? "AI RECOMMENDED"
              : chart.source === "manual"
                ? "CUSTOM VISUALIZATION"
                : "DATA RECOMMENDATION"}
          </span>
          <h3>{chart.spec.title}</h3>
        </div>
        <div className="chart-actions">
          <Button
            variant="ghost"
            size="icon"
            title="Export PNG"
            aria-label={`Export ${chart.spec.title} as PNG`}
            onClick={() => download("png")}
          >
            <Download size={16} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            title="Export SVG"
            aria-label={`Export ${chart.spec.title} as SVG`}
            onClick={() => download("svg")}
          >
            <FileImage size={16} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            title="Remove chart"
            aria-label={`Remove ${chart.spec.title}`}
            onClick={onRemove}
          >
            <Trash2 size={15} />
          </Button>
        </div>
      </header>
      {error ? (
        <p role="alert">{error}</p>
      ) : (
        <div
          className="echart"
          ref={node}
          role="img"
          aria-label={chart.spec.title}
        />
      )}
      <div className="chart-caption">
        <p>{chart.explanation}</p>
        <span>
          {chart.sampled
            ? `Display sample: ${chart.sample_size.toLocaleString()} plotted points from ${chart.total_rows.toLocaleString()} eligible observations. Statistics use all eligible rows.`
            : `${chart.sample_size.toLocaleString()} eligible observations`}
        </span>
        <span>{chart.missing_note}</span>
      </div>
    </article>
  );
}
