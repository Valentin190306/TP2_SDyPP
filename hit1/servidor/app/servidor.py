import sys
import logging
import subprocess
import time
import uuid
import socket
import requests

from flask import Flask, request, jsonify

# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("Servidor")

# ---------------- CONFIG SERVICIOS ----------------
SERVICIOS = {
    "hash": {
        "imagen": "usuario/servicio-hash:latest",
        "endpoint": "/hash",
        "port": 5000
    },
    "texto": {
        "imagen": "usuario/servicio-texto:latest",
        "endpoint": "/procesar",
        "port": 5000
    }
}

# ---------------- UTILS ----------------
def get_free_port():
    s = socket.socket()
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def wait_for_service(url, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code == 200:
                return True
        except:
            time.sleep(0.5)
    return False


# ---------------- APP ----------------
app = Flask(__name__)


@app.route('/getRemoteTask', methods=['POST'])
def ejecutaTareaRemota():
    data = request.get_json()

    if not data or 'servicio' not in data:
        return jsonify({'error': 'Falta "servicio"'}), 400

    servicio_id = data['servicio']
    payload = data.get("payload", {})

    if servicio_id not in SERVICIOS:
        return jsonify({'error': 'Servicio no soportado'}), 400

    config = SERVICIOS[servicio_id]

    imagen = config["imagen"]
    endpoint = config["endpoint"]
    container_port = config["port"]

    container_name = f"tmp-{uuid.uuid4().hex[:8]}"
    host_port = get_free_port()

    logger.info(f"[{servicio_id}] Ejecutando en contenedor {container_name}")

    try:
        # 1. Pull imagen
        subprocess.run(
            ["docker", "pull", imagen],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # 2. Run contenedor
        subprocess.run([
            "docker", "run", "-d",
            "--name", container_name,
            "-p", f"{host_port}:{container_port}",
            imagen
        ], check=True)

        # 3. Esperar disponibilidad
        health_url = f"http://localhost:{host_port}/health"

        if not wait_for_service(health_url):
            raise Exception("Timeout esperando servicio")

        # 4. Ejecutar tarea
        url = f"http://localhost:{host_port}{endpoint}"

        response = requests.post(
            url,
            json=payload,
            timeout=5
        )

        result = response.json()

        logger.info(f"[{servicio_id}] Resultado obtenido")

        return jsonify({
            "servicio": servicio_id,
            "resultado": result
        })

    except subprocess.CalledProcessError as e:
        logger.error(f"Error Docker: {e.stderr}")
        return jsonify({
            "error": "Fallo en ejecución Docker",
            "detalle": str(e.stderr)
        }), 500

    except Exception as e:
        logger.error(f"Error general: {str(e)}")
        return jsonify({
            "error": "Fallo en ejecución",
            "detalle": str(e)
        }), 500

    finally:
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.info(f"Contenedor {container_name} eliminado")


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)