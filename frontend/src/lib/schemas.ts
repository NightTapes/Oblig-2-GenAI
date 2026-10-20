import { z } from "zod";
export const chartSpecSchema = z
  .object({
    chart_type: z.enum([
      "histogram",
      "scatter",
      "line",
      "bar",
      "box",
      "heatmap",
    ]),
    x_column: z.string().nullable().optional(),
    y_column: z.string().nullable().optional(),
    color_column: z.string().nullable().optional(),
    aggregation: z
      .enum(["mean", "median", "sum", "min", "max", "count"])
      .default("mean"),
    bins: z.number().int().min(3).max(100).default(20),
    title: z.string().max(160).default(""),
  })
  .strict();
export type ChartSpec = z.infer<typeof chartSpecSchema>;
export type Column = {
  name: string;
  kind: "numeric" | "categorical" | "datetime" | "boolean" | "empty";
  missing_count: number;
  missing_percent: number;
  unique_count: number;
  minimum: number | null;
  maximum: number | null;
  mean: number | null;
  median: number | null;
  std: number | null;
  distribution: { value: string; count: number }[];
};
export type Profile = {
  id: string;
  name: string;
  row_count: number;
  column_count: number;
  missing_percent: number;
  missing_count: number;
  numeric_count: number;
  columns: Column[];
  warnings: string[];
  synthetic: boolean;
  expires_at: number;
};
export type Chart = {
  id: string;
  spec: ChartSpec;
  option: Record<string, unknown>;
  explanation: string;
  source: "deterministic" | "ai" | "manual";
  sampled: boolean;
  sample_size: number;
  total_rows: number;
  missing_note: string;
};
export type Analysis = {
  action: string;
  result: Record<string, unknown>;
  note: string;
  chart: Chart | null;
};
export type ChatReply = {
  verified: Analysis;
  explanation: string | null;
  explanation_error: string | null;
};
export type AIStatus = { available: boolean; model: string; message: string };
export type Rows = {
  rows: Record<string, unknown>[];
  total: number;
  page: number;
  page_size: number;
};
