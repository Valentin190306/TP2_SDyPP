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
        "imagen": "valen190306/sd-tp2-hit1-servicio-b:latest",
        "endpoint": "/hash",
        "port": 8080
    },
    "texto": {
        "imagen": "valen190306/sd-tp2-hit1-servicio-a:latest",
        "endpoint": "/invertirTexto",
        "port": 8080
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
            # Aceptamos 404 o 405 como prueba de que el servidor Flask del worker está vivo
            if r.status_code in [200, 404, 405]:
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

        # 2. Run contenedor (SIN mapear puertos, Docker maneja la red interna)
        subprocess.run([
            "docker", "run", "-d",
            "--name", container_name,
            imagen
        ], check=True)

        # 3. Obtener la IP interna del contenedor worker
        ip_info = subprocess.run(
            ["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", container_name],
            capture_output=True, text=True, check=True
        )
        container_ip = ip_info.stdout.strip()

        if not container_ip:
            raise Exception("No se pudo obtener la IP del contenedor worker")

        # 4. Esperar disponibilidad en la IP interna
        health_url = f"http://{container_ip}:{container_port}/health"

        if not wait_for_service(health_url):
            raise Exception("Timeout esperando servicio")

        # 5. Ejecutar tarea usando la IP interna
        url = f"http://{container_ip}:{container_port}{endpoint}"

        response = requests.post(
            url,
            json=payload,
            timeout=5
        )

        # Verificar que la petición fue exitosa
        response.raise_for_status()
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
            "detalle": str(e.stderr) if e.stderr else str(e)
        }), 500

    except requests.exceptions.RequestException as e:
        logger.error(f"Error HTTP en worker: {str(e)}")
        return jsonify({
            "error": "Error comunicacion HTTP",
            "detalle": str(e)
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