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

# ---------------- TESTS BÁSICOS ----------------

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

# ---------------- TESTS DE LAMPORT ----------------

def test_lamport_incrementa_en_respuesta(client):
    """
    El servidor debe devolver un lamport_ts mayor al que recibió.
    """
    with patch("servidor.ejecutar_en_contenedor") as mock_exec:
        mock_exec.return_value = {"ok": True, "resultado": {"hash": "abc"}}
        response = client.post("/getRemoteTask", json={
            "servicio": "hash",
            "payload": {"input": "hola"},
            "lamport_ts": 10
        })
    assert response.status_code == 200
    data = response.get_json()
    assert "lamport_ts" in data
    assert data["lamport_ts"] > 10

def test_lamport_presente_en_respuesta(client):
    """
    Toda respuesta exitosa debe incluir lamport_ts y tarea_id.
    """
    with patch("servidor.ejecutar_en_contenedor") as mock_exec:
        mock_exec.return_value = {"ok": True, "resultado": {"resultado": "aloh"}}
        response = client.post("/getRemoteTask", json={
            "servicio": "texto",
            "payload": {"texto": "hola"},
            "lamport_ts": 1
        })
    assert response.status_code == 200
    data = response.get_json()
    assert "lamport_ts" in data
    assert "tarea_id" in data

# ---------------- TESTS DE EJECUCIÓN ----------------

def test_ejecuta_tarea_exitosa(client):
    """
    Mockea ejecutar_en_contenedor para evitar Docker real.
    Verifica que el servidor procesa la tarea y devuelve resultado.
    """
    with patch("servidor.ejecutar_en_contenedor") as mock_exec:
        mock_exec.return_value = {
            "ok": True,
            "resultado": {"hash": "abc123", "algoritmo": "sha256"}
        }
        response = client.post("/getRemoteTask", json={
            "servicio": "hash",
            "payload": {"input": "hola", "algoritmo": "sha256"},
            "lamport_ts": 1
        })

    assert response.status_code == 200
    data = response.get_json()
    assert data["servicio"] == "hash"
    assert "resultado" in data
    assert data["resultado"]["hash"] == "abc123"

def test_ejecuta_tarea_fallida(client):
    """
    Si ejecutar_en_contenedor devuelve ok=False, el servidor responde 500.
    """
    with patch("servidor.ejecutar_en_contenedor") as mock_exec:
        mock_exec.return_value = {
            "ok": False,
            "error": "Fallo simulado"
        }
        response = client.post("/getRemoteTask", json={
            "servicio": "texto",
            "payload": {"texto": "hola"},
            "lamport_ts": 1
        })

    assert response.status_code == 500
    data = response.get_json()
    assert "error" in data

# ---------------- TESTS DE MÉTRICAS ----------------

def test_metricas_estructura(client):
    """
    El endpoint /metricas debe devolver los campos esperados.
    """
    response = client.get("/metricas")
    assert response.status_code == 200
    data = response.get_json()
    assert "workers_max" in data
    assert "tareas_completadas" in data
    assert "throughput_por_minuto" in data
    assert "cola_pendiente" in data

def test_metricas_incrementa_con_tareas(client):
    """
    Después de completar tareas, tareas_completadas debe ser mayor a 0.
    """
    with patch("servidor.ejecutar_en_contenedor") as mock_exec:
        mock_exec.return_value = {"ok": True, "resultado": {"resultado": "aloh"}}
        client.post("/getRemoteTask", json={
            "servicio": "texto",
            "payload": {"texto": "hola"},
            "lamport_ts": 1
        })

    response = client.get("/metricas")
    data = response.get_json()
    assert data["tareas_completadas"] >= 1
