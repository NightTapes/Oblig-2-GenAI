from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


Kind = Literal["numeric", "categorical", "datetime", "boolean", "empty"]
Aggregation = Literal["mean", "median", "sum", "min", "max", "count"]
ChartType = Literal["histogram", "scatter", "line", "bar", "box", "heatmap"]


class ColumnProfile(StrictModel):
    name: str
    kind: Kind
    missing_count: int
    missing_percent: float
    unique_count: int
    minimum: float | None = None
    maximum: float | None = None
    mean: float | None = None
    median: float | None = None
    std: float | None = None
    distribution: list[dict[str, Any]] = Field(default_factory=list)


class DatasetProfile(StrictModel):
    id: str
    name: str
    row_count: int
    column_count: int
    missing_percent: float
    missing_count: int
    numeric_count: int
    columns: list[ColumnProfile]
    warnings: list[str]
    synthetic: bool = False
    expires_at: float


class ChartSpec(StrictModel):
    chart_type: ChartType
    x_column: str | None = Field(default=None, max_length=200)
    y_column: str | None = Field(default=None, max_length=200)
    color_column: str | None = Field(default=None, max_length=200)
    aggregation: Aggregation = "mean"
    bins: int = Field(default=20, ge=3, le=100)
    title: str = Field(default="", max_length=160)


class ChartResult(StrictModel):
    id: str
    spec: ChartSpec
    option: dict[str, Any]
    explanation: str
    source: Literal["deterministic", "ai", "manual"] = "manual"
    sampled: bool = False
    sample_size: int
    total_rows: int
    missing_note: str


class AnalysisAction(StrictModel):
    action: Literal[
        "describe_dataset",
        "describe_column",
        "aggregate",
        "calculate_correlation",
        "create_chart",
        "compare_groups",
        "list_missing_values",
        "unsupported",
    ]
    column: str | None = Field(default=None, max_length=200)
    x_column: str | None = Field(default=None, max_length=200)
    y_column: str | None = Field(default=None, max_length=200)
    group_by: str | None = Field(
        default=None,
        max_length=200,
        description="Exact categorical or boolean column name for grouping, not a value or function.",
    )
    metric: str | None = Field(
        default=None,
        max_length=200,
        description="Exact numerical column name to aggregate, not the aggregation function. For example mass_g, never mean.",
    )
    aggregation: Aggregation = "mean"
    chart: ChartSpec | None = None
    reason: str | None = Field(default=None, max_length=500)


class AnalysisResult(StrictModel):
    action: str
    result: dict[str, Any]
    note: str
    chart: ChartResult | None = None


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(StrictModel):
    verified: AnalysisResult
    explanation: str | None
    explanation_error: str | None = None


class Recommendations(StrictModel):
    charts: list[ChartResult]
    ai_refined: bool = False
    note: str


class AIRecommendations(StrictModel):
    charts: list[ChartSpec] = Field(max_length=4)


class AIOverview(StrictModel):
    summary: str = Field(max_length=1500)


class AIExplanation(StrictModel):
    explanation: str = Field(min_length=1, max_length=2000)


class AIStatus(StrictModel):
    available: bool
    model: str
    message: str


class RowsPage(StrictModel):
    rows: list[dict[str, Any]]
    total: int
    page: int
    page_size: int


class DatasetList(StrictModel):
    datasets: list[DatasetProfile]


class SampleRequest(StrictModel):
    name: Literal["plants", "environment"]
