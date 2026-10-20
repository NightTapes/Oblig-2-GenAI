"""Only predefined analytical operations. No user/AI SQL or code is executable."""

import warnings
import duckdb
from fastapi import HTTPException
from scipy.stats import pearsonr
from app.data.profiling import finite
from app.schemas.models import AnalysisAction, AnalysisResult

MISSING_NOTE = "Calculations use all eligible observations; rows missing required variables are omitted."


def require_column(dataset, name, kinds=None):
    if not name or name not in dataset.kinds:
        raise HTTPException(
            422, f"Unknown or missing column: {name or '(none)'}. Select a column from the dataset."
        )
    if kinds and dataset.kinds[name] not in kinds:
        raise HTTPException(422, f"{name} must have type {' or '.join(kinds)} for this operation.")


def grouped(frame, group, metric, aggregation):
    # Fixed local aliases prevent identifiers and values from becoming SQL syntax.
    selected = frame[[group] + ([metric] if metric and metric != group else [])].copy()
    selected = selected.dropna(subset=[group] + ([metric] if metric else []))
    if selected[group].nunique() > 40:
        raise HTTPException(
            422, "Grouping is limited to 40 distinct categories. Choose a lower-cardinality column."
        )
    table = selected.rename(columns={group: "g", **({metric: "m"} if metric and metric != group else {})})
    if group == metric:
        table["m"] = table["g"]
    functions = {
        "mean": "avg(m)",
        "median": "median(m)",
        "sum": "sum(m)",
        "min": "min(m)",
        "max": "max(m)",
        "count": "count(*)",
    }
    with duckdb.connect(
        config={"threads": "1", "memory_limit": "128MB", "enable_external_access": "false"}
    ) as con:
        con.register("observations", table)
        rows = con.execute(
            f"SELECT g, {functions[aggregation]} AS value, count(*) AS n FROM observations GROUP BY g ORDER BY value DESC, g"
        ).fetchall()
    return [{"group": str(g), "value": finite(v), "n": int(n)} for g, v, n in rows]


def correlation(frame, x, y):
    pairs = frame[list(dict.fromkeys([x, y]))].dropna()
    n = len(pairs)
    if n < 3 or pairs[x].nunique() < 2 or pairs[y].nunique() < 2:
        raise HTTPException(
            422, "Pearson correlation requires at least 3 complete pairs and nonconstant variables."
        )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = finite(pearsonr(pairs[x].to_numpy(), pairs[y].to_numpy()).statistic)
    if r is None:
        raise HTTPException(422, "Correlation is numerically undefined for these values.")
    return {"x": x, "y": y, "pearson_r": r, "n": n, "omitted_rows": len(frame) - n}


def execute(dataset, action: AnalysisAction):
    name = action.action
    if name == "unsupported":
        return AnalysisResult(
            action=name,
            result={},
            note=action.reason
            or "Please ask for a summary, missing values, a numeric aggregation, correlation, group comparison, or a chart.",
        )
    if name == "describe_dataset":
        return AnalysisResult(
            action=name,
            result=dataset.profile.model_dump(exclude={"id", "expires_at"}),
            note="Deterministic profile of the complete dataset. Standard deviations use n−1; one-observation standard deviations are undefined.",
        )
    if name == "list_missing_values":
        p = dataset.profile
        return AnalysisResult(
            action=name,
            result={
                "missing_cells": p.missing_count,
                "total_cells": p.row_count * p.column_count,
                "missing_percent": p.missing_percent,
                "columns": [
                    {"name": c.name, "missing": c.missing_count, "percent": c.missing_percent}
                    for c in p.columns
                ],
            },
            note="Percentage is missing cells divided by all cells. Blank or whitespace-only cells count as missing; literal NA strings are preserved.",
        )
    if name == "describe_column":
        require_column(dataset, action.column)
        column = next(c for c in dataset.profile.columns if c.name == action.column)
        return AnalysisResult(
            action=name,
            result=column.model_dump(),
            note="Complete eligible column; sample standard deviation uses n−1. Category distributions show the 12 most frequent values.",
        )
    if name == "create_chart":
        if action.chart is None:
            raise HTTPException(422, "A chart specification is required.")
        from app.visualization.engine import build_chart

        chart = build_chart(dataset, action.chart, "ai")
        return AnalysisResult(
            action=name,
            result={
                "title": chart.spec.title,
                "eligible_rows": chart.total_rows,
                "displayed_rows": chart.sample_size,
            },
            chart=chart,
            note="Charts describe patterns and associations, and do not establish causality.",
        )
    frame = dataset.frame()
    if name == "calculate_correlation":
        require_column(dataset, action.x_column, ["numeric"])
        require_column(dataset, action.y_column, ["numeric"])
        if action.x_column == action.y_column:
            raise HTTPException(422, "Choose two different numerical columns.")
        return AnalysisResult(
            action=name,
            result=correlation(frame, action.x_column, action.y_column),
            note=f"{MISSING_NOTE} Pearson r measures linear association, not causation. Outliers and nonlinear relationships can make it inappropriate. No significance claim is made.",
        )
    if name in ("aggregate", "compare_groups"):
        if action.aggregation != "count" or action.metric:
            require_column(dataset, action.metric, ["numeric"])
        if name == "compare_groups" and not action.group_by:
            raise HTTPException(422, "Group comparison requires a grouping column.")
        if action.group_by:
            require_column(dataset, action.group_by, ["categorical", "boolean"])
            rows = grouped(frame, action.group_by, action.metric, action.aggregation)
            if not rows:
                raise HTTPException(422, "No complete observations are available for these variables.")
            result = {
                "group_by": action.group_by,
                "metric": action.metric,
                "aggregation": action.aggregation,
                "groups": rows,
                "highest": rows[0],
                "n": sum(r["n"] for r in rows),
            }
        else:
            values = frame[action.metric].dropna() if action.metric else frame.index.to_series()
            result = {
                "metric": action.metric,
                "aggregation": action.aggregation,
                "value": finite(getattr(values, action.aggregation)()) if len(values) else None,
                "n": len(values),
            }
        return AnalysisResult(
            action=name,
            result=result,
            note=f"{MISSING_NOTE} Group comparisons are descriptive, without hypothesis tests or causal conclusions.",
        )
    raise HTTPException(422, "Unsupported analytical action.")
