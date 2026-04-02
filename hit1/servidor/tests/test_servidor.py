import pytest
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from servidor import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"

def test_falta_servicio(client):
    response = client.post("/getRemoteTask", json={})
    assert response.status_code == 400

def test_servicio_no_soportado(client):
    response = client.post("/getRemoteTask", json={"servicio": "inexistente"})
    assert response.status_code == 400

@patch("servidor.subprocess.run")
@patch("servidor.wait_for_service", return_value=True)
@patch("servidor.requests.post")
def test_ejecuta_tarea_exitosa(mock_post, mock_wait, mock_run, client):
    mock_run.return_value = MagicMock(returncode=0)
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"hash": "abc123", "algoritmo": "sha256"}
    )
    response = client.post("/getRemoteTask", json={
        "servicio": "hash",
        "payload": {"input": "hola", "algoritmo": "sha256"}
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data["servicio"] == "hash"
    assert "resultado" in data