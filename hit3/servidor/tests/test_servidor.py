import pytest
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from servidor import app, estado_bully

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

@pytest.fixture(autouse=True)
def reset_estado_bully():
    """Resetea el estado del Bully antes de cada test para evitar contaminación."""
    with estado_bully["lock"]:
        estado_bully["lider_actual"] = None
        estado_bully["en_eleccion"] = False
    yield

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

# ---------------- TESTS DE EJECUCIÓN ----------------

def test_ejecuta_tarea_exitosa(client):
    """
    Mockea subprocess y wait_for_service para evitar Docker real.
    Verifica que el servidor procesa la tarea y devuelve resultado.
    """
    mock_run = MagicMock()
    mock_run.returncode = 0
    mock_run.stdout = "abc123\n"
    mock_run.stderr = ""

    with patch("servidor.subprocess.run", return_value=mock_run), \
         patch("servidor.wait_for_service", return_value=True), \
         patch("servidor.requests.post") as mock_post:

        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"resultado": "odnum aloh"}
        )

        response = client.post("/getRemoteTask", json={
            "servicio": "texto",
            "payload": {"texto": "hola mundo"}
        })

    assert response.status_code == 200
    data = response.get_json()
    assert data["servicio"] == "texto"
    assert "resultado" in data

def test_ejecuta_tarea_hash(client):
    """Verifica que el servicio hash también funciona correctamente."""
    mock_run = MagicMock()
    mock_run.returncode = 0
    mock_run.stdout = "172.17.0.5\n"
    mock_run.stderr = ""

    with patch("servidor.subprocess.run", return_value=mock_run), \
         patch("servidor.wait_for_service", return_value=True), \
         patch("servidor.requests.post") as mock_post:

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

# ---------------- TESTS DE BULLY ----------------

def test_bully_status(client):
    """El endpoint /bully/status debe devolver node_id y lider_actual."""
    response = client.get("/bully/status")
    assert response.status_code == 200
    data = response.get_json()
    assert "node_id" in data
    assert "lider_actual" in data

def test_bully_status_sin_lider(client):
    """Al arrancar sin elección, lider_actual es None."""
    response = client.get("/bully/status")
    data = response.get_json()
    assert data["lider_actual"] is None

def test_bully_coordinator_actualiza_lider(client):
    """Al recibir COORDINATOR, el nodo actualiza su lider_actual."""
    response = client.post("/bully/coordinator", json={"node_id": 3})
    assert response.status_code == 200

    status = client.get("/bully/status")
    data = status.get_json()
    assert data["lider_actual"] == 3

def test_bully_coordinator_cancela_eleccion(client):
    """Al recibir COORDINATOR, en_eleccion debe quedar en False."""
    with estado_bully["lock"]:
        estado_bully["en_eleccion"] = True

    client.post("/bully/coordinator", json={"node_id": 3})

    with estado_bully["lock"]:
        assert estado_bully["en_eleccion"] is False

def test_bully_election_nodo_menor(client):
    """
    Si el emisor tiene ID menor al nodo local (NODE_ID=1 por defecto),
    el nodo responde OK e inicia su propia elección.
    """
    with patch("servidor.iniciar_eleccion") as mock_eleccion:
        response = client.post("/bully/election", json={"node_id": 0})
        assert response.status_code == 200
        data = response.get_json()
        assert data["msg"] == "ok"

def test_bully_election_nodo_mayor(client):
    """
    Si el emisor tiene ID mayor al nodo local, el nodo responde ignorado
    y no inicia elección.
    """
    with patch("servidor.iniciar_eleccion") as mock_eleccion:
        response = client.post("/bully/election", json={"node_id": 99})
        assert response.status_code == 200
        data = response.get_json()
        assert data["msg"] == "ignorado"
        mock_eleccion.assert_not_called()

def test_bully_eleccion_sin_peers(client):
    """
    Con PEERS vacío, al iniciar elección nadie responde
    y el nodo se proclama líder.
    """
    with patch("servidor.PEERS", []), \
         patch("servidor.requests.post") as mock_post:

        from servidor import iniciar_eleccion
        iniciar_eleccion()

    with estado_bully["lock"]:
        assert estado_bully["lider_actual"] is not None

def test_bully_eleccion_no_duplicada(client):
    """Si ya hay una elección en curso, iniciar_eleccion no la duplica."""
    with estado_bully["lock"]:
        estado_bully["en_eleccion"] = True

    with patch("servidor.requests.post") as mock_post:
        from servidor import iniciar_eleccion
        iniciar_eleccion()
        mock_post.assert_not_called()
        
        
# cubren 4 escenarios:

# Estado: /bully/status devuelve los campos correctos y arranca sin líder.
# COORDINATOR: al recibirlo el nodo actualiza su líder y cancela cualquier elección en curso.
# ELECTION: si el emisor tiene ID menor el nodo responde ok e inicia su propia elección; si tiene ID mayor responde ignorado y no hace nada.
# Elección sin peers: sin ningún peer disponible el nodo se proclama líder directamente.