import itertools
import secrets
import warnings
import numpy as np
from fastapi import HTTPException
from app.analysis.operations import require_column, grouped, correlation
from app.core.config import settings
from app.data.profiling import finite
from app.schemas.models import ChartSpec, ChartResult

COLORS = ["#FCA311", "#356F94", "#548B72", "#8C6BB1", "#D56D53", "#14213D"]


def validate(dataset, spec):
    t = spec.chart_type
    if t == "heatmap":
        if sum(v == "numeric" for v in dataset.kinds.values()) < 2:
            raise HTTPException(422, "A correlation heatmap requires at least two numerical variables.")
        if any([spec.x_column, spec.y_column, spec.color_column]):
            raise HTTPException(
                422, "Heatmaps automatically use up to 16 numeric columns; omit axis and color fields."
            )
        return
    xk = (
        ["numeric"]
        if t in ("histogram", "scatter")
        else ["datetime"]
        if t == "line"
        else ["categorical", "boolean"]
    )
    require_column(dataset, spec.x_column, xk)
    if t in ("scatter", "line", "box") or (t == "bar" and spec.aggregation != "count") or spec.y_column:
        require_column(dataset, spec.y_column, ["numeric"])
    if t == "scatter" and spec.x_column == spec.y_column:
        raise HTTPException(422, "Scatter plots require two different numerical variables.")
    if t == "histogram" and spec.y_column:
        raise HTTPException(422, "Histograms accept one numerical variable.")
    if spec.color_column:
        if t not in ("scatter", "line"):
            raise HTTPException(422, "Color grouping is available for scatter and line charts.")
        require_column(dataset, spec.color_column, ["categorical", "boolean"])
    for group in ([spec.x_column] if t in ("bar", "box") else []) + (
        [spec.color_column] if spec.color_column else []
    ):
        cp = next(c for c in dataset.profile.columns if c.name == group)
        if cp.unique_count > 40:
            raise HTTPException(422, "Charts are limited to 40 groups. Choose a different grouping column.")


def build_chart(dataset, spec: ChartSpec, source="manual"):
    validate(dataset, spec)
    df, t, x, y = dataset.frame(), spec.chart_type, spec.x_column, spec.y_column
    needed = list(dict.fromkeys(c for c in (x, y, spec.color_column) if c))
    data = df.dropna(subset=needed) if needed else df
    total, sample_size, sampled = len(data), len(data), False
    if not total:
        raise HTTPException(422, "There are no complete observations for this chart.")
    option = {
        "color": COLORS,
        "animation": False,
        "textStyle": {"fontFamily": "Inter, sans-serif", "color": "#6B7280"},
        "tooltip": {"trigger": "item", "renderMode": "richText", "confine": True},
        "grid": {"left": 48, "right": 25, "top": 35, "bottom": 55, "containLabel": True},
        "legend": {"type": "scroll", "top": 0},
        "xAxis": {
            "type": "value",
            "name": x or "",
            "nameLocation": "middle",
            "nameGap": 36,
            "nameTextStyle": {"fontSize": 10, "width": 220, "overflow": "truncate"},
            "axisLine": {"show": False},
            "splitLine": {"show": False},
        },
        "yAxis": {
            "type": "value",
            "name": y or "Count",
            "nameLocation": "middle",
            "nameGap": 38,
            "nameRotate": 90,
            "nameTextStyle": {"fontSize": 10, "width": 180, "overflow": "truncate"},
            "splitLine": {"lineStyle": {"color": "#EEF0F3"}},
        },
    }
    explanation = ""
    extra_note = ""
    title = spec.title
    if t == "histogram":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            counts, edges = np.histogram(data[x].to_numpy(), bins=spec.bins)
        if not np.isfinite(edges).all() or len(set(edges.tolist())) < len(edges):
            raise HTTPException(
                422, "Values are outside stable histogram range. Rescale this variable before plotting."
            )
        option["xAxis"].update(
            type="category",
            data=[f"{edges[i]:.4g}–{edges[i + 1]:.4g}" for i in range(len(counts))],
            axisLabel={"interval": "auto", "rotate": 20},
        )
        option["series"] = [
            {
                "name": "Observations",
                "type": "bar",
                "barCategoryGap": "5%",
                "data": counts.tolist(),
                "itemStyle": {"borderRadius": [3, 3, 0, 0]},
            }
        ]
        title = title or f"Distribution of {x}"
        explanation = f"A histogram reveals the shape and spread of {x}. Bin counts use all {total:,} nonmissing values."
    elif t in ("scatter", "line"):
        if t == "line":
            keys = [x] + ([spec.color_column] if spec.color_column else [])
            data = data.groupby(keys, observed=True, as_index=False)[y].agg(spec.aggregation).sort_values(x)
        if len(data) > settings.chart_point_limit:
            data = (
                data.iloc[np.linspace(0, len(data) - 1, settings.chart_point_limit, dtype=int)]
                if t == "line"
                else data.sample(settings.chart_point_limit, random_state=42)
            )
            sampled = True
        sample_size = len(data)
        series = []
        groups = data.groupby(spec.color_column, observed=True) if spec.color_column else [(y, data)]
        for group, part in groups:
            points = [
                [v.isoformat() if t == "line" else finite(v), finite(w)]
                for v, w in part[[x, y]].itertuples(index=False, name=None)
            ]
            series.append(
                {
                    "name": str(group),
                    "type": t,
                    "data": points,
                    "symbolSize": 7 if t == "scatter" else 4,
                    "showSymbol": t != "line" or len(part) < 100,
                    "itemStyle": {"opacity": 0.8},
                    "emphasis": {"focus": "series"},
                }
            )
        option["series"] = series
        option["dataZoom"] = [
            {"type": "inside", "filterMode": "none"},
            {"type": "slider", "height": 13, "bottom": 3, "borderColor": "transparent"},
        ]
        if t == "line":
            option["xAxis"]["type"] = "time"
            extra_note = f"Equal timestamps are aggregated by {spec.aggregation} per series. "
            if not sampled:
                sample_size = total
        title = title or (f"{y} over time" if t == "line" else f"{x} vs. {y}")
        explanation = f"{'Track changes over time' if t == 'line' else 'Explore the association between two numerical variables'}. A pattern does not establish a causal effect."
    elif t == "bar":
        rows = grouped(df, x, y, spec.aggregation)
        total = sample_size = sum(r["n"] for r in rows)
        if not total:
            raise HTTPException(422, "No complete observations available for this bar chart.")
        option["xAxis"].update(type="category", data=[r["group"] for r in rows], axisLabel={"rotate": 15})
        option["yAxis"]["name"] = f"{spec.aggregation}({y or 'rows'})"
        option["series"] = [
            {
                "type": "bar",
                "name": spec.aggregation,
                "data": [r["value"] for r in rows],
                "barMaxWidth": 48,
                "itemStyle": {"borderRadius": [4, 4, 0, 0]},
            }
        ]
        title = title or f"{spec.aggregation.title()} {y or 'observations'} by {x}"
        explanation = f"Compare {spec.aggregation} values across {x}. All complete observations contribute to each group."
    elif t == "box":
        groups = list(data.groupby(x, observed=True))
        boxes = []
        for _, part in groups:
            q = np.quantile(part[y].to_numpy(), [0, 0.25, 0.5, 0.75, 1])
            boxes.append([finite(v) for v in q])
        option["xAxis"].update(type="category", data=[str(g) for g, _ in groups])
        option["series"] = [
            {
                "name": y,
                "type": "boxplot",
                "data": boxes,
                "itemStyle": {"color": "#FFF1D6", "borderColor": "#CA7C03"},
            }
        ]
        title = title or f"{y} by {x}"
        explanation = "Compare distributions with median, quartiles, and full-range whiskers (minimum to maximum). These whiskers are not a Tukey outlier rule."
    elif t == "heatmap":
        cols = [c for c, kind in dataset.kinds.items() if kind == "numeric"][:16]
        cells, pair_counts = [], []
        for i, j in itertools.product(range(len(cols)), repeat=2):
            try:
                r = correlation(df, cols[i], cols[j])
                cells.append([i, j, round(r["pearson_r"], 4)])
                pair_counts.append(f"{cols[i]} × {cols[j]}: n={r['n']}")
            except HTTPException:
                cells.append([i, j, None])
        option["xAxis"].update(type="category", data=cols, name="", axisLabel={"rotate": 22})
        option["yAxis"].update(type="category", data=cols, name="")
        option["grid"].update(bottom=80)
        option["visualMap"] = {
            "min": -1,
            "max": 1,
            "calculable": True,
            "orient": "horizontal",
            "left": "center",
            "bottom": 0,
            "inRange": {"color": ["#356F94", "#F4F6F8", "#FCA311"]},
        }
        option["series"] = [
            {
                "type": "heatmap",
                "data": cells,
                "label": {"show": len(cols) <= 8},
                "emphasis": {"itemStyle": {"borderWidth": 2, "borderColor": "#14213D"}},
            }
        ]
        title = title or "Linear relationships"
        explanation = "Pearson r uses complete pairs for each cell; blanks indicate undefined correlation. Association is not causation."
        extra_note = "First 16 numeric columns. " + "; ".join(pair_counts)
    spec = spec.model_copy(update={"title": title})
    omitted = len(df) - total
    return ChartResult(
        id=secrets.token_urlsafe(12),
        spec=spec,
        option=option,
        explanation=explanation,
        source=source,
        sampled=sampled,
        sample_size=sample_size,
        total_rows=total,
        missing_note=f"{omitted:,} rows missing required values omitted. {extra_note}".strip(),
    )


def recommend(dataset):
    numeric = [c for c, k in dataset.kinds.items() if k == "numeric"]
    times = [c for c, k in dataset.kinds.items() if k == "datetime"]
    cats = [
        c.name
        for c in dataset.profile.columns
        if c.kind in ("categorical", "boolean") and c.unique_count <= 40 and c.unique_count > 0
    ]
    specs = []
    if numeric:
        specs.append(ChartSpec(chart_type="histogram", x_column=numeric[0]))
    if len(numeric) >= 2:
        specs.append(
            ChartSpec(
                chart_type="scatter",
                x_column=numeric[0],
                y_column=numeric[1],
                color_column=cats[0] if cats else None,
            )
        )
    if times and numeric:
        specs.append(
            ChartSpec(
                chart_type="line",
                x_column=times[0],
                y_column=numeric[-1],
                color_column=cats[0] if cats else None,
            )
        )
    if cats and numeric:
        specs.append(ChartSpec(chart_type="box", x_column=cats[0], y_column=numeric[-1]))
    elif cats:
        specs.append(ChartSpec(chart_type="bar", x_column=cats[0], aggregation="count"))
    if len(numeric) >= 2 and len(specs) < 4:
        specs.append(ChartSpec(chart_type="heatmap"))
    charts = []
    for spec in specs[:4]:
        try:
            charts.append(build_chart(dataset, spec, "deterministic"))
        except (HTTPException, ValueError, OverflowError):
            continue
    return charts
