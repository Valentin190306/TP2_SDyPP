import pytest
import requests
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs
import pathlib

DOCKERFILE_PATH = str(pathlib.Path(__file__).parent.parent)

@pytest.fixture(scope="module")
def servicio_a():
    # Buildea la imagen desde el Dockerfile local y levanta el contenedor
    container = (
        DockerContainer(image="sd-tp2-hit1-servicio-a:test")
        .with_exposed_ports(8080)
    )
    # Necesitamos buildear primero
    import subprocess
    subprocess.run(
        ["docker", "build", "-t", "sd-tp2-hit1-servicio-a:test", DOCKERFILE_PATH],
        check=True
    )
    with container:
        wait_for_logs(container, "Running on", timeout=10)
        yield container

def test_invertir_texto_simple(servicio_a):
    port = servicio_a.get_exposed_port(8080)
    url = f"http://localhost:{port}/invertirTexto"
    response = requests.post(url, json={"texto": "hola"})
    assert response.status_code == 200
    assert response.json()["resultado"] == "aloh"

def test_invertir_texto_vacio(servicio_a):
    port = servicio_a.get_exposed_port(8080)
    url = f"http://localhost:{port}/invertirTexto"
    response = requests.post(url, json={"texto": ""})
    assert response.status_code == 200
    assert response.json()["resultado"] == ""

def test_invertir_texto_palindromo(servicio_a):
    port = servicio_a.get_exposed_port(8080)
    url = f"http://localhost:{port}/invertirTexto"
    response = requests.post(url, json={"texto": "aba"})
    assert response.status_code == 200
    assert response.json()["resultado"] == "aba"