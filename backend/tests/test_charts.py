import pytest
from app.core.config import settings


@pytest.mark.parametrize(
    "spec",
    [
        {"chart_type": "histogram", "x_column": "x"},
        {"chart_type": "scatter", "x_column": "x", "y_column": "y", "color_column": "group"},
        {"chart_type": "line", "x_column": "date", "y_column": "y", "color_column": "group"},
        {"chart_type": "bar", "x_column": "group", "y_column": "x"},
        {"chart_type": "bar", "x_column": "group", "aggregation": "count"},
        {"chart_type": "box", "x_column": "group", "y_column": "x"},
        {"chart_type": "heatmap"},
    ],
)
def test_six_chart_types(client, dataset, spec):
    r = client.post(f"/api/datasets/{dataset['id']}/charts", json=spec)
    assert r.status_code == 201, r.text
    chart = r.json()
    assert chart["option"]["series"] and chart["spec"]["title"]
    assert chart["source"] == "manual"
    if spec["chart_type"] == "histogram":
        assert sum(chart["option"]["series"][0]["data"]) == 3
    if spec["chart_type"] == "heatmap":
        cells = chart["option"]["series"][0]["data"]
        assert cells[0][2] == 1 and cells[1][2] == 1
        assert "n=3" in chart["missing_note"]


@pytest.mark.parametrize(
    "spec",
    [
        {"chart_type": "pie", "x_column": "x"},
        {"chart_type": "scatter", "x_column": "group", "y_column": "x"},
        {"chart_type": "line", "x_column": "x", "y_column": "y"},
        {"chart_type": "bar", "x_column": "x", "y_column": "y"},
        {"chart_type": "histogram", "x_column": "x", "bins": 10000},
        {"chart_type": "scatter", "x_column": "x", "y_column": "x"},
        {"chart_type": "histogram", "x_column": "x", "color_column": "group"},
        {"chart_type": "heatmap", "x_column": "x"},
        {"chart_type": "histogram", "x_column": "unknown"},
    ],
)
def test_invalid_charts(client, dataset, spec):
    assert client.post(f"/api/datasets/{dataset['id']}/charts", json=spec).status_code == 422


def test_sampling_is_disclosed_and_stats_complete(client, dataset, monkeypatch):
    monkeypatch.setattr(settings, "chart_point_limit", 2)
    r = client.post(
        f"/api/datasets/{dataset['id']}/charts",
        json={"chart_type": "scatter", "x_column": "x", "y_column": "y"},
    ).json()
    assert r["sampled"] and r["sample_size"] == 2 and r["total_rows"] == 3
    r = client.post(
        f"/api/datasets/{dataset['id']}/analyze", json={"action": "aggregate", "metric": "x"}
    ).json()
    assert r["result"]["n"] == 3 and r["result"]["value"] == 2


def test_recommendations(client, dataset):
    r = client.get(f"/api/datasets/{dataset['id']}/recommendations").json()
    assert 1 <= len(r["charts"]) <= 4 and not r["ai_refined"]
    assert all(chart["source"] == "deterministic" for chart in r["charts"])


def test_high_cardinality_rejected(client):
    content = "g,x\n" + "\n".join(f"group{i},{i}" for i in range(41))
    p = client.post("/api/datasets/upload", files={"file": ("groups.csv", content.encode())}).json()
    assert (
        client.post(
            f"/api/datasets/{p['id']}/charts", json={"chart_type": "bar", "x_column": "g", "y_column": "x"}
        ).status_code
        == 422
    )
