import time
import pytest
from app.core.config import settings
from app.main import app


def test_import_profile_original_values(client, dataset):
    p = dataset
    assert p["row_count"] == 4 and p["column_count"] == 7
    cols = {c["name"]: c for c in p["columns"]}
    assert {k: cols[k]["kind"] for k in cols} == {
        "date": "datetime",
        "group": "categorical",
        "x": "numeric",
        "y": "numeric",
        "flag": "boolean",
        "mixed": "categorical",
        "empty": "empty",
    }
    assert cols["x"]["mean"] == 2 and cols["x"]["median"] == 2 and cols["x"]["std"] == 1
    assert cols["x"]["minimum"] == 1 and cols["x"]["maximum"] == 3
    assert cols["x"]["missing_percent"] == 25
    assert p["missing_count"] == 5 and p["missing_percent"] == pytest.approx(5 / 28 * 100)
    assert cols["empty"]["unique_count"] == 0
    rows = client.get(f"/api/datasets/{p['id']}/rows").json()["rows"]
    assert rows[1]["flag"] == "FALSE" and rows[1]["mixed"] == "no" and rows[3]["x"] == ""


@pytest.mark.parametrize(
    "name,content,status",
    [
        ("bad.xlsx", b"a,b\n1,2", 415),
        ("empty.csv", b"", 413),
        ("header.csv", b"a,b", 422),
        ("bad.csv", b"a,b\n1,2,3", 422),
        ("bad.csv", b"a,b\n1", 422),
        ("bad.csv", b'a,b\n1,"unterminated', 422),
        ("bad.csv", b"a,a\n1,2", 422),
        ("bad.csv", b"a,\n1,2", 422),
        ("bad.csv", b"a\n\x00", 422),
        ("bad.csv", b"a,b\n\n1,2", 422),
    ],
)
def test_reject_invalid_csv(client, name, content, status):
    response = client.post("/api/datasets/upload", files={"file": (name, content)})
    assert response.status_code == status, response.text
    assert response.json()["error"]["message"]


@pytest.mark.parametrize("delimiter", [",", ";", "\t", "|"])
def test_common_delimiters(client, delimiter):
    csv = f"location{delimiter}value\nOslo{delimiter}2\nBergen{delimiter}3"
    response = client.post("/api/datasets/upload", files={"file": ("test.csv", csv.encode())})
    assert response.status_code == 201 and response.json()["column_count"] == 2


@pytest.mark.parametrize(
    "content", [b"\xef\xbb\xbfa,b\n1,2", "city;value\nMünchen;1\nZürich;2".encode("cp1252")]
)
def test_encodings(client, content):
    response = client.post("/api/datasets/upload", files={"file": ("test.csv", content)})
    assert response.status_code == 201, response.text


def test_preserve_lexical_values_and_missing_policy(client):
    p = client.post(
        "/api/datasets/upload", files={"file": ("values.csv", b"code,note\n001,NA\n002, \n")}
    ).json()
    rows = client.get(f"/api/datasets/{p['id']}/rows").json()["rows"]
    assert rows[0]["code"] == "001" and rows[0]["note"] == "NA" and rows[1]["note"] == " "
    assert p["missing_count"] == 1


def test_pagination_filter_and_numeric_sort(client, dataset):
    key = dataset["id"]
    response = client.get(
        f"/api/datasets/{key}/rows", params={"page": 2, "page_size": 2, "sort": "x", "descending": True}
    )
    assert [r["x"] for r in response.json()["rows"]] == ["1", ""]
    rows = client.get(f"/api/datasets/{key}/rows", params={"search": "B"}).json()
    assert rows["total"] == 2
    assert client.get(f"/api/datasets/{key}/rows", params={"sort": "DROP TABLE"}).status_code == 422
    assert client.get(f"/api/datasets/{key}/rows", params={"page_size": 1000}).status_code == 422


def test_session_isolation(client, dataset):
    # Same app/store, independent cookie jar. Creating a second TestClient lifespan would replace the store.
    cookie = client.cookies.get("datalens_session")
    client.cookies.clear()
    key = dataset["id"]
    assert client.get(f"/api/datasets/{key}/profile").status_code == 404
    assert client.get("/api/datasets").json()["datasets"] == []
    assert client.delete(f"/api/datasets/{key}").status_code == 404
    assert client.post(f"/api/datasets/{key}/analyze", json={"action": "describe_dataset"}).status_code == 404
    client.cookies.clear()
    client.cookies.set("datalens_session", cookie, path="/api")
    assert client.get(f"/api/datasets/{key}/profile").status_code == 200


def test_delete_and_expiration(client, dataset):
    key = dataset["id"]
    item = app.state.store.items[key]
    item.profile.expires_at = time.time() - 1
    assert client.get(f"/api/datasets/{key}/profile").status_code == 404
    assert not item.path.exists()
    p = client.post("/api/datasets/sample", json={"name": "plants"}).json()
    assert client.delete(f"/api/datasets/{p['id']}").status_code == 204
    assert client.get(f"/api/datasets/{p['id']}/profile").status_code == 404


def test_limits_and_csrf(client, monkeypatch):
    monkeypatch.setattr(settings, "max_rows", 1)
    r = client.post("/api/datasets/upload", files={"file": ("large.csv", b"x\n1\n2")})
    assert r.status_code == 422
    r = client.post(
        "/api/datasets/sample", json={"name": "plants"}, headers={"Origin": "https://evil.example"}
    )
    assert r.status_code == 403
    assert client.post("/api/datasets/sample", content=b"x" * 33000).status_code == 413
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    assert client.post("/api/datasets/upload", files={"file": ("large.csv", b"x\n1")}).status_code == 413


def test_session_capacity(client, monkeypatch):
    monkeypatch.setattr(settings, "max_session_datasets", 1)
    assert client.post("/api/datasets/sample", json={"name": "plants"}).status_code == 201
    assert client.post("/api/datasets/sample", json={"name": "environment"}).status_code == 429


def test_extremes_and_single_observation(client):
    r = client.post(
        "/api/datasets/upload",
        files={"file": ("edge.csv", b"constant,large,mixed\n1,1e308,inf\n1,1e308,2\n")},
    )
    assert r.status_code == 201
    p = r.json()
    assert p["columns"][0]["std"] == 0
    assert p["columns"][2]["kind"] == "categorical"
    r = client.post("/api/datasets/upload", files={"file": ("single.csv", b"x\n1")})
    assert r.json()["columns"][0]["std"] is None
