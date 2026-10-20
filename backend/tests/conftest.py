import pytest
from fastapi.testclient import TestClient
from app.core.config import settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def csv_data():
    return b"date,group,x,y,flag,mixed,empty\n2026-01-01,A,1,2,true,1,\n2026-01-02,A,2,4,FALSE,no,\n2026-01-03,B,3,6,TRUE,3,\n2026-01-04,B,,8,false,4,\n"


@pytest.fixture
def dataset(client, csv_data):
    response = client.post("/api/datasets/upload", files={"file": ("experiment.csv", csv_data, "text/csv")})
    assert response.status_code == 201, response.text
    return response.json()
