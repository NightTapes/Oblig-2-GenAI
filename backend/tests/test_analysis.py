import pytest


def analyze(client, dataset, action):
    return client.post(f"/api/datasets/{dataset['id']}/analyze", json=action)


@pytest.mark.parametrize(
    "aggregation,expected", [("mean", 2), ("median", 2), ("sum", 6), ("min", 1), ("max", 3), ("count", 3)]
)
def test_aggregate_complete_values(client, dataset, aggregation, expected):
    r = analyze(client, dataset, {"action": "aggregate", "metric": "x", "aggregation": aggregation})
    assert r.status_code == 200, r.text
    assert r.json()["result"]["value"] == expected and r.json()["result"]["n"] == 3


def test_group_comparison_and_counts(client, dataset):
    r = analyze(client, dataset, {"action": "compare_groups", "metric": "x", "group_by": "group"}).json()
    assert r["result"]["highest"] == {"group": "B", "value": 3, "n": 1}
    assert r["result"]["n"] == 3
    r = analyze(client, dataset, {"action": "aggregate", "group_by": "group", "aggregation": "count"}).json()
    assert r["result"]["groups"][0]["value"] == 2


def test_correlation(client, dataset):
    r = analyze(client, dataset, {"action": "calculate_correlation", "x_column": "x", "y_column": "y"})
    assert r.status_code == 200, r.text
    result = r.json()["result"]
    assert result["pearson_r"] == pytest.approx(1) and result["n"] == 3 and result["omitted_rows"] == 1
    assert "not causation" in r.json()["note"]


@pytest.mark.parametrize(
    "action",
    [
        {"action": "run_python", "code": "import os"},
        {"action": "aggregate", "metric": "unknown"},
        {"action": "aggregate", "metric": "group"},
        {"action": "aggregate", "metric": "x", "aggregation": "execute"},
        {"action": "describe_column", "column": "../../etc/passwd"},
        {"action": "describe_dataset", "sql": "SELECT *"},
        {"action": "calculate_correlation", "x_column": "x", "y_column": "group"},
        {"action": "calculate_correlation", "x_column": "x", "y_column": "x"},
        {"action": "create_chart"},
        {"action": "compare_groups", "metric": "x"},
    ],
)
def test_action_rejections(client, dataset, action):
    assert analyze(client, dataset, action).status_code == 422


def test_summary_and_missing(client, dataset):
    r = analyze(client, dataset, {"action": "list_missing_values"}).json()
    assert r["result"]["missing_cells"] == 5 and r["result"]["total_cells"] == 28
    r = analyze(client, dataset, {"action": "describe_column", "column": "x"}).json()
    assert r["result"]["mean"] == 2 and r["result"]["unique_count"] == 3


def test_undefined_correlation(client):
    p = client.post("/api/datasets/upload", files={"file": ("constant.csv", b"x,y\n1,2\n1,3\n1,4")}).json()
    assert (
        analyze(client, p, {"action": "calculate_correlation", "x_column": "x", "y_column": "y"}).status_code
        == 422
    )
