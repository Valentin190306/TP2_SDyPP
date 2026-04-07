import sys
import os
import logging
import subprocess
import time
import uuid
import socket
import threading
import queue
import requests
from flask import Flask, request, jsonify

# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("Servidor")

# ---------------- CONFIG ----------------
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 4))

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

# ---------------- RELOJ DE LAMPORT ----------------
class RelojLamport:
    def __init__(self):
        self._clock = 0
        self._lock = threading.Lock()

    def send_event(self):
        with self._lock:
            self._clock += 1
            return self._clock

    def receive_event(self, timestamp_entrante):
        with self._lock:
            self._clock = max(self._clock, timestamp_entrante) + 1
            return self._clock

    def valor(self):
        with self._lock:
            return self._clock

reloj = RelojLamport()

# ---------------- COLA CON EXCLUSIÓN MUTUA ----------------

task_queue = queue.PriorityQueue()
queue_mutex = threading.Lock()

# Semáforo que limita workers activos simultáneos
worker_semaphore = threading.Semaphore(MAX_WORKERS)

# Métricas de throughput
metricas = {
    "completadas": 0,
    "inicio": time.time(),
    "lock": threading.Lock()
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
            # Si responde un 200 (OK), o 404 (No encontrado) o 405 (Método no permitido)
            # significa que Flask está corriendo y escuchando peticiones.
            if r.status_code in [200, 404, 405]:
                return True
        except requests.exceptions.RequestException:
            time.sleep(0.5)
    return False

# ---------------- EJECUCIÓN DE TAREA ----------------

def ejecutar_en_contenedor(servicio_id, payload, tarea_id):
    config = SERVICIOS[servicio_id]
    imagen = config["imagen"]
    endpoint = config["endpoint"]
    container_port = config["port"]
    container_name = f"tmp-{uuid.uuid4().hex[:8]}"

    logger.info(f"[{tarea_id}] Worker iniciando contenedor {container_name}")

    try:
        # 1. Levantamos el contenedor SIN mapear puertos al host.
        # Docker se encarga de la red interna automáticamente.
        result = subprocess.run([
            "docker", "run", "-d",
            "--name", container_name,
            imagen
        ], capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(f"Fallo docker run: {result.stderr.strip()}")

        # 2. Le preguntamos a Docker cuál es la IP interna que le asignó
        ip_info = subprocess.run(
            ["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", container_name],
            capture_output=True, text=True, check=True
        )
        container_ip = ip_info.stdout.strip()
        
        if not container_ip:
            raise Exception("No se pudo obtener la IP del contenedor worker")

        logger.info(f"[{tarea_id}] IP interna asignada: {container_ip}")

        # 3. Esperamos usando la IP interna directa del contenedor
        health_url = f"http://{container_ip}:{container_port}/health"
        if not wait_for_service(health_url):
            raise Exception("Timeout esperando que el servicio levante internamente")

        # 4. Hacemos la petición real de la tarea
        url = f"http://{container_ip}:{container_port}{endpoint}"
        response = requests.post(url, json=payload, timeout=10)
        
        # Verificamos que la tarea en sí no haya dado error
        response.raise_for_status() 
        resultado_json = response.json()

        logger.info(f"[{tarea_id}] Tarea completada exitosamente")
        return {"ok": True, "resultado": resultado_json}
    
    except requests.exceptions.RequestException as e:
        logger.error(f"[{tarea_id}] Error HTTP en worker: {str(e)}")
        return {"ok": False, "error": f"Error comunicacion HTTP: {str(e)}"}

    except Exception as e:
        logger.error(f"[{tarea_id}] Error general: {str(e)}")
        return {"ok": False, "error": str(e)}

    finally:
        # Limpieza del contenedor temporal
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    

# ---------------- WORKER LOOP ----------------
"""
Hilo permanente que consume tareas de la cola.
Cada tarea extraída ocupa un slot del semáforo.
Cuando termina, libera el slot y deposita el resultado en el Event.
"""
def worker_loop():
    while True:
        # Bloquea hasta que haya una tarea en la cola
        #tarea_id, datos, result_event = task_queue.get()
        ts_local, tarea_id, datos, result_event = task_queue.get()   

        # Ocupa un slot del pool (bloquea si todos están ocupados)
        worker_semaphore.acquire()

        def procesar(tarea_id=tarea_id, datos=datos, result_event=result_event):
            try:
                resultado = ejecutar_en_contenedor(
                    datos["servicio_id"],
                    datos["payload"],
                    tarea_id
                )
                result_event["resultado"] = resultado
            finally:
                worker_semaphore.release()
                result_event["listo"].set()

                with metricas["lock"]:
                    metricas["completadas"] += 1

        # Cada tarea corre en su propio hilo para no bloquear el worker_loop
        t = threading.Thread(target=procesar, daemon=True)
        t.start()

# Arrancar el hilo consumidor de cola al iniciar
threading.Thread(target=worker_loop, daemon=True).start()

# ---------------- APP ----------------
app = Flask(__name__)

@app.route('/getRemoteTask', methods=['POST'])
def ejecutaTareaRemota():
    data = request.get_json()

    if not data or 'servicio' not in data:
        return jsonify({'error': 'Falta "servicio"'}), 400

    servicio_id = data['servicio']
    payload = data.get("payload", {})
    lamport_cliente = data.get("lamport_ts", 0)  # timestamp del cliente

    if servicio_id not in SERVICIOS:
        return jsonify({'error': 'Servicio no soportado'}), 400

    # Actualizar reloj local con el timestamp del cliente
    ts_local = reloj.receive_event(lamport_cliente)
    tarea_id = f"tarea-{uuid.uuid4().hex[:6]}"

    logger.info(f"[{tarea_id}] Recibida con Lamport cliente={lamport_cliente} → local={ts_local}")

    # Encolar con exclusión mutua explícita
    result_event = {"listo": threading.Event(), "resultado": None}

    with queue_mutex:
        task_queue.put((ts_local, tarea_id, {
            "servicio_id": servicio_id,
            "payload": payload
        }, result_event))
        logger.info(f"[{tarea_id}] Encolada con prioridad Lamport={ts_local}")

    # Esperar resultado (bloqueante para el cliente HTTP)
    result_event["listo"].wait(timeout=60)

    if result_event["resultado"] is None:
        return jsonify({"error": "Timeout esperando worker"}), 504

    resultado = result_event["resultado"]

    # Incrementar reloj al responder
    ts_respuesta = reloj.send_event()

    if resultado["ok"]:
        return jsonify({
            "servicio": servicio_id,
            "resultado": resultado["resultado"],
            "lamport_ts": ts_respuesta,
            "tarea_id": tarea_id
        })
    else:
        return jsonify({
            "error": "Fallo en ejecución",
            "detalle": resultado["error"],
            "lamport_ts": ts_respuesta
        }), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


@app.route('/metricas', methods=['GET'])
def ver_metricas():
    """
    Devuelve throughput actual: tareas completadas por minuto. (variar N workers y medir).
    """
    with metricas["lock"]:
        completadas = metricas["completadas"]
        elapsed = time.time() - metricas["inicio"]

    tpm = (completadas / elapsed) * 60 if elapsed > 0 else 0

    return jsonify({
        "workers_max": MAX_WORKERS,
        "tareas_completadas": completadas,
        "tiempo_segundos": round(elapsed, 2),
        "throughput_por_minuto": round(tpm, 2),
        "cola_pendiente": task_queue.qsize()
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, threaded=True)