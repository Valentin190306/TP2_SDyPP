import pytest
import requests
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs
import pathlib
import hashlib
import subprocess

DOCKERFILE_PATH = str(pathlib.Path(__file__).parent.parent)

@pytest.fixture(scope="module")
def servicio_b():
    subprocess.run(
        ["docker", "build", "-t", "sd-tp2-hit1-servicio-b:test", DOCKERFILE_PATH],
        check=True
    )
    container = (
        DockerContainer(image="sd-tp2-hit1-servicio-b:test")
        .with_exposed_ports(8080)
    )
    with container:
        wait_for_logs(container, "Running on", timeout=10)
        yield container

def test_hash_sha256(servicio_b):
    port = servicio_b.get_exposed_port(8080)
    url = f"http://localhost:{port}/hash"
    input_str = "hola mundo"
    response = requests.post(url, json={"input": input_str, "algoritmo": "sha256"})
    assert response.status_code == 200
    data = response.json()
    assert data["algoritmo"] == "sha256"
    expected = hashlib.sha256(input_str.encode()).hexdigest()
    assert data["hash"] == expected

def test_hash_md5(servicio_b):
    port = servicio_b.get_exposed_port(8080)
    url = f"http://localhost:{port}/hash"
    input_str = "test"
    response = requests.post(url, json={"input": input_str, "algoritmo": "md5"})
    assert response.status_code == 200
    expected = hashlib.md5(input_str.encode()).hexdigest()
    assert response.json()["hash"] == expected

def test_hash_algoritmo_invalido(servicio_b):
    port = servicio_b.get_exposed_port(8080)
    url = f"http://localhost:{port}/hash"
    response = requests.post(url, json={"input": "x", "algoritmo": "rot13"})
    assert response.status_code == 400

def test_hash_falta_input(servicio_b):
    port = servicio_b.get_exposed_port(8080)
    url = f"http://localhost:{port}/hash"
    response = requests.post(url, json={"algoritmo": "sha256"})
    assert response.status_code == 400
