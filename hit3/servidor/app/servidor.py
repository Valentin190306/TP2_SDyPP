import os
import threading
import sys
import logging
import subprocess
import time
import uuid
import requests

from flask import Flask, request, jsonify

# ---------------- LOGGING ----------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("Servidor")

# ---------------- VARIABLES DE ENTORNO ----------------

NODE_ID = int(os.environ.get("NODE_ID", 1))
PEERS = [p.strip() for p in os.environ.get("PEERS", "").split(",") if p.strip()]

estado_bully = {
    "lider_actual": None,
    "en_eleccion": False,
    "lock": threading.Lock()
}

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

# ---------------- ALGORITMO BULLY ----------------

def iniciar_eleccion():
    with estado_bully["lock"]:
        if estado_bully["en_eleccion"]:
            return  # ya hay una elección en curso
        estado_bully["en_eleccion"] = True

    logger.info(f"[Nodo {NODE_ID}] Iniciando elección")

    peers_mayores = [p for p in PEERS if int(p.split(":")[0].split("_")[-1]) > NODE_ID]
    # peers_mayores son los que tienen ID mayor al mío

    alguien_respondio = False

    for peer in peers_mayores:
        try:
            r = requests.post(f"http://{peer}/bully/election",
                              json={"node_id": NODE_ID}, timeout=2)
            if r.status_code == 200:
                alguien_respondio = True
        except:
            pass  # ese peer no responde, lo ignoramos

    if not alguien_respondio:
        # Nadie mayor respondió → soy el líder
        proclamarse_lider()
    else:
        # Alguien mayor tomó el control, esperamos
        with estado_bully["lock"]:
            estado_bully["en_eleccion"] = False


def proclamarse_lider():
    with estado_bully["lock"]:
        estado_bully["lider_actual"] = NODE_ID
        estado_bully["en_eleccion"] = False

    logger.info(f"[Nodo {NODE_ID}] Soy el nuevo líder")

    for peer in PEERS:
        try:
            requests.post(f"http://{peer}/bully/coordinator",
                          json={"node_id": NODE_ID}, timeout=2)
        except:
            pass


def monitorear_lider():
    """Hilo de fondo que corre siempre"""
    while True:
        time.sleep(5)  # chequea cada 5 segundos

        with estado_bully["lock"]:
            lider = estado_bully["lider_actual"]
            soy_lider = (lider == NODE_ID)
            en_eleccion = estado_bully["en_eleccion"]

        if soy_lider or en_eleccion:
            continue  # si soy líder o hay elección en curso, no hago nada

        if lider is None:
            iniciar_eleccion()
            continue

        # Busco al peer que es el líder
        peer_lider = next((p for p in PEERS if str(lider) in p), None)

        if peer_lider is None:
            iniciar_eleccion()
            continue

        try:
            r = requests.get(f"http://{peer_lider}/bully/status", timeout=2)
            if r.status_code != 200:
                raise Exception("Líder no responde bien")
        except:
            logger.warning(f"[Nodo {NODE_ID}] Líder {lider} caído, iniciando elección")
            with estado_bully["lock"]:
                estado_bully["lider_actual"] = None
            iniciar_eleccion()

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
    #host_port = get_free_port()

    logger.info(f"[{servicio_id}] Ejecutando en contenedor {container_name}")

    try:
        # 1. Pull imagen
        subprocess.run(
            ["docker", "pull", imagen],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # 2. Run contenedor SIN mapear puertos al host
        result = subprocess.run([
            "docker", "run", "-d",
            "--name", container_name,
            "--network", "hit3_red_interna",  # ← agregar esto
            imagen
        ], capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(f"Fallo docker run: {result.stderr.strip()}")

        # 3. Obtener IP interna del contenedor
        ip_info = subprocess.run(
            ["docker", "inspect", "-f",
            "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            container_name],
            capture_output=True, text=True, check=True
        )
        container_ip = ip_info.stdout.strip()

        if not container_ip:
            raise Exception("No se pudo obtener la IP del contenedor")

        logger.info(f"[{servicio_id}] IP interna: {container_ip}")

        # 4. Esperar disponibilidad usando IP interna
        health_url = f"http://{container_ip}:{container_port}/health"

        if not wait_for_service(health_url):
            raise Exception("Timeout esperando servicio")

        # 5. Ejecutar tarea
        url = f"http://{container_ip}:{container_port}{endpoint}"

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


@app.route('/bully/election', methods=['POST'])
def recibir_election():
    data = request.get_json()
    emisor_id = data["node_id"]
    logger.info(f"[Nodo {NODE_ID}] ELECTION recibido de nodo {emisor_id}")

    if NODE_ID > emisor_id:
        # Soy mayor, respondo OK y arranco mi propia elección
        threading.Thread(target=iniciar_eleccion, daemon=True).start()
        return jsonify({"msg": "ok"}), 200

    return jsonify({"msg": "ignorado"}), 200


@app.route('/bully/coordinator', methods=['POST'])
def recibir_coordinator():
    data = request.get_json()
    nuevo_lider = data["node_id"]
    with estado_bully["lock"]:
        estado_bully["lider_actual"] = nuevo_lider
        estado_bully["en_eleccion"] = False
    logger.info(f"[Nodo {NODE_ID}] Nuevo líder: {nuevo_lider}")
    return jsonify({"msg": "ok"}), 200


@app.route('/bully/status', methods=['GET'])
def bully_status():
    return jsonify({
        "node_id": NODE_ID,
        "lider_actual": estado_bully["lider_actual"]
    }), 200


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    threading.Thread(target=monitorear_lider, daemon=True).start()
    
    # Nodo 1 espera 1s, Nodo 2 espera 2s, Nodo 3 espera 3s
    time.sleep(NODE_ID * 1)
    iniciar_eleccion()
    
    app.run(host='0.0.0.0', port=8080, threaded=True)