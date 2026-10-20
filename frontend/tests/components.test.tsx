import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { Upload } from "@/components/datasets/upload";
import { ChartBuilder } from "@/components/charts/chart-builder";
import { Assistant } from "@/components/ai/assistant";
import { DataTable } from "@/components/datasets/data-table";
import { chartSpecSchema, type Profile } from "@/lib/schemas";
import { api } from "@/lib/api";
vi.mock("@/lib/api", () => ({
  api: { chart: vi.fn(), chat: vi.fn(), rows: vi.fn() },
}));
const profile: Profile = {
  id: "test",
  name: "measurements.csv",
  row_count: 40,
  column_count: 3,
  numeric_count: 2,
  missing_count: 0,
  missing_percent: 0,
  warnings: [],
  synthetic: false,
  expires_at: Date.now() / 1000 + 7200,
  columns: [
    { name: "x", kind: "numeric" },
    { name: "y", kind: "numeric" },
    { name: "group", kind: "categorical" },
  ].map((c) => ({
    ...c,
    kind: c.kind as "numeric" | "categorical",
    missing_count: 0,
    missing_percent: 0,
    unique_count: 2,
    minimum: null,
    maximum: null,
    mean: null,
    median: null,
    std: null,
    distribution: [],
  })),
};
beforeEach(() => vi.clearAllMocks());
describe("CSV import", () => {
  it("imports from picker and supports samples", async () => {
    const onFile = vi.fn(),
      onSample = vi.fn();
    render(
      <Upload onFile={onFile} onSample={onSample} busy={false} progress={0} />,
    );
    const file = new File(["x\n1"], "test.csv", { type: "text/csv" });
    await userEvent.upload(screen.getByLabelText("Upload CSV"), file);
    expect(onFile).toHaveBeenCalledWith(file);
    await userEvent.click(
      screen.getByRole("button", { name: /Plant growth experiment/ }),
    );
    expect(onSample).toHaveBeenCalledWith("plants");
  });
  it("validates dropped file types and size before uploading", () => {
    const onFile = vi.fn();
    const { container } = render(
      <Upload
        onFile={onFile}
        onSample={vi.fn()}
        busy={false}
        progress={0}
        maxSize={1}
      />,
    );
    fireEvent.drop(container.querySelector(".upload-zone")!, {
      dataTransfer: { files: [new File(["test"], "bad.xlsx")] },
    });
    expect(screen.getByRole("alert")).toHaveTextContent(".csv");
    fireEvent.drop(container.querySelector(".upload-zone")!, {
      dataTransfer: {
        files: [new File(["x".repeat(1024 * 1024 + 1)], "big.csv")],
      },
    });
    expect(screen.getByRole("alert")).toHaveTextContent("1 MB");
    expect(onFile).not.toHaveBeenCalled();
  });
  it("reports progress and disables duplicate uploads", () => {
    render(<Upload onFile={vi.fn()} onSample={vi.fn()} busy progress={65} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "65",
    );
    expect(screen.getByRole("button", { name: "Importing…" })).toBeDisabled();
  });
});
describe("Chart builder", () => {
  it("sends a validated compatible specification", async () => {
    vi.mocked(api.chart).mockResolvedValue({ id: "chart" } as never);
    const onChart = vi.fn();
    render(<ChartBuilder profile={profile} onChart={onChart} />);
    await userEvent.click(screen.getByRole("button", { name: "Create chart" }));
    await userEvent.selectOptions(screen.getByLabelText("Variable"), "x");
    await userEvent.click(
      screen.getByRole("button", { name: "Add to workspace" }),
    );
    await waitFor(() =>
      expect(api.chart).toHaveBeenCalledWith(
        "test",
        expect.objectContaining({ chart_type: "histogram", x_column: "x" }),
      ),
    );
    expect(onChart).toHaveBeenCalled();
    expect(
      screen.queryByRole("option", { name: "Line chart" }),
    ).not.toBeInTheDocument();
  });
  it("rejects unknown types and extreme bin counts", () => {
    expect(chartSpecSchema.safeParse({ chart_type: "pie" }).success).toBe(
      false,
    );
    expect(
      chartSpecSchema.safeParse({ chart_type: "histogram", bins: 500 }).success,
    ).toBe(false);
  });
});
describe("AI assistant", () => {
  const ready = { available: true, model: "qwen3:4b", message: "Ready" };
  it("shows processing, errors, and retry without fabricating results", async () => {
    let reject!: (e: Error) => void;
    vi.mocked(api.chat).mockReturnValue(
      new Promise((_, r) => {
        reject = r;
      }),
    );
    render(
      <Assistant
        profile={profile}
        status={ready}
        onChart={vi.fn()}
        onRefresh={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await userEvent.type(
      screen.getByLabelText("Ask about your data"),
      "Mean x?",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Send question" }),
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Interpreting and verifying",
    );
    reject(new Error("Local model unavailable"));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Local model unavailable",
      ),
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeEnabled();
    expect(screen.queryByText("VERIFIED RESULT")).not.toBeInTheDocument();
  });
  it("renders verified results separately from explanations and adds charts", async () => {
    const onChart = vi.fn();
    vi.mocked(api.chat).mockResolvedValue({
      verified: {
        action: "create_chart",
        result: { n: 40 },
        note: "No causal inference.",
        chart: { id: "new" } as never,
      },
      explanation: "A relationship to explore.",
      explanation_error: null,
    });
    render(
      <Assistant
        profile={profile}
        status={ready}
        onChart={onChart}
        onRefresh={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await userEvent.type(
      screen.getByLabelText("Ask about your data"),
      "Plot x and y",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Send question" }),
    );
    await waitFor(() =>
      expect(screen.getByText("VERIFIED RESULT")).toBeInTheDocument(),
    );
    expect(screen.getByText("AI EXPLANATION")).toBeInTheDocument();
    expect(onChart).toHaveBeenCalledWith({ id: "new" });
  });
  it("makes offline status explicit and keeps the conversation input accessible", () => {
    render(
      <Assistant
        profile={profile}
        status={{
          available: false,
          model: "qwen3:4b",
          message: "Start Ollama",
        }}
        onChart={vi.fn()}
        onRefresh={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByText("Start Ollama")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Send question" }),
    ).toBeDisabled();
  });
});
describe("Data explorer", () => {
  it("requests server pagination, numeric sorting and filtering", async () => {
    vi.mocked(api.rows).mockResolvedValue({
      rows: [{ x: "1", y: "2", group: "A" }],
      total: 40,
      page: 1,
      page_size: 25,
    });
    render(<DataTable profile={profile} />);
    await waitFor(() => expect(screen.getByText("A")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Next page" }));
    await waitFor(() =>
      expect(vi.mocked(api.rows).mock.calls.at(-1)?.[1].get("page")).toBe("2"),
    );
    await userEvent.click(screen.getByRole("button", { name: "Sort by x" }));
    await waitFor(() =>
      expect(vi.mocked(api.rows).mock.calls.at(-1)?.[1].get("sort")).toBe("x"),
    );
    await userEvent.type(screen.getByLabelText("Search records"), "A");
    await waitFor(() =>
      expect(vi.mocked(api.rows).mock.calls.at(-1)?.[1].get("search")).toBe(
        "A",
      ),
    );
  });
});
