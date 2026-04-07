# tests/test_servidor.py
import pytest
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import bully
import asignador
from api import app


# ---------------- FIXTURES ----------------

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

@pytest.fixture(autouse=True)
def reset_estado():
    with bully.estado["lock"]:
        bully.estado["lider_actual"] = None
        bully.estado["en_eleccion"] = False
    asignador._registro.clear()
    asignador._registro[bully.NODE_ID] = 0
    yield


# ---------------- BULLY ----------------

def test_sin_peers_se_proclama_lider():
    with patch("bully.PEERS", []), \
         patch("bully.requests.post") as mock_post:
        bully.iniciar_eleccion()

    with bully.estado["lock"]:
        assert bully.estado["lider_actual"] == bully.NODE_ID


def test_con_peers_mayores_no_se_proclama_lider():
    peers_mayores = [f"servidor_{bully.NODE_ID + 1}:8080"]
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("bully.PEERS", peers_mayores), \
         patch("bully.requests.post", return_value=mock_response):
        bully.iniciar_eleccion()

    with bully.estado["lock"]:
        assert bully.estado["lider_actual"] is None


def test_no_inicia_eleccion_si_ya_hay_una_en_curso():
    with bully.estado["lock"]:
        bully.estado["en_eleccion"] = True

    with patch("bully.requests.post") as mock_post:
        bully.iniciar_eleccion()
        mock_post.assert_not_called()


# ---------------- ASIGNADOR ----------------

def test_elegir_nodo_devuelve_el_de_menor_carga():
    asignador._registro[1] = 3
    asignador._registro[2] = 1
    asignador._registro[3] = 5
    assert asignador.elegir_nodo() == 2


def test_incrementar_y_decrementar():
    asignador._registro[1] = 0
    asignador.incrementar(1)
    assert asignador._registro[1] == 1
    asignador.decrementar(1)
    assert asignador._registro[1] == 0


def test_decrementar_no_baja_de_cero():
    asignador._registro[1] = 0
    asignador.decrementar(1)
    assert asignador._registro[1] == 0


# ---------------- API ----------------

def test_bully_status_expone_registro_carga(client):
    with bully.estado["lock"]:
        bully.estado["lider_actual"] = 3
    response = client.get("/bully/status")
    assert response.status_code == 200
    data = response.get_json()
    assert "registro_carga" in data
    assert isinstance(data["registro_carga"], dict)


def test_nodo_no_lider_reenvía_al_lider(client):
    with bully.estado["lock"]:
        bully.estado["lider_actual"] = 3

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"servicio": "texto", "resultado": {"resultado": "aloh"}}

    with patch("bully.NODE_ID", 1), \
         patch("bully.PEERS", ["servidor_2:8080", "servidor_3:8080"]), \
         patch("api.requests.post", return_value=mock_response):
        response = client.post("/getRemoteTask", json={
            "servicio": "texto",
            "payload": {"texto": "hola"}
        })

    assert response.status_code == 200


def test_lider_delega_al_nodo_con_menos_carga(client):
    with bully.estado["lock"]:
        bully.estado["lider_actual"] = bully.NODE_ID

    asignador._registro[bully.NODE_ID] = 0

    mock_resultado = {"resultado": "aloh"}

    with patch("asignador.elegir_nodo", return_value=bully.NODE_ID), \
         patch("asignador._ejecutar_local", return_value=mock_resultado):
        response = client.post("/getRemoteTask", json={
            "servicio": "texto",
            "payload": {"texto": "hola"}
        })

    assert response.status_code == 200
    data = response.get_json()
    assert "nodo" in data
    assert "resultado" in data


def test_worker_ejecutar_local(client):
    mock_resultado = {"resultado": "aloh"}

    with patch("asignador._ejecutar_local", return_value=mock_resultado):
        response = client.post("/worker/ejecutar", json={
            "servicio": "texto",
            "payload": {"texto": "hola"}
        })

    assert response.status_code == 200
    assert response.get_json() == mock_resultado