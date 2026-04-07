# api.py
import threading
import logging
import requests

from flask import Flask, request, jsonify
import bully
import asignador

logger = logging.getLogger("API")

app = Flask(__name__)


# ---------------- ENDPOINT PÚBLICO ----------------

@app.route('/getRemoteTask', methods=['POST'])
def get_remote_task():
    data = request.get_json()

    if not data or 'servicio' not in data:
        return jsonify({'error': 'Falta "servicio"'}), 400

    servicio_id = data['servicio']
    payload = data.get('payload', {})

    if servicio_id not in asignador.SERVICIOS:
        return jsonify({'error': 'Servicio no soportado'}), 400

    with bully.estado["lock"]:
        lider = bully.estado["lider_actual"]
        soy_lider = (lider == bully.NODE_ID)

    # Si no soy el líder, reenvío al líder
    if not soy_lider:
        if lider is None:
            return jsonify({'error': 'Sin líder disponible, reintentá en unos segundos'}), 503

        peer_lider = next((p for p in bully.PEERS if f"_{lider}:" in p), None)
        if peer_lider is None:
            return jsonify({'error': 'No se encontró el peer líder'}), 503

        try:
            r = requests.post(f"http://{peer_lider}/getRemoteTask",
                              json=data, timeout=30)
            return jsonify(r.json()), r.status_code
        except Exception as e:
            logger.error(f"Error reenviando al líder: {e}")
            return jsonify({'error': 'Error contactando al líder'}), 503

    # Soy el líder: elijo el nodo con menos carga
    node_id = asignador.elegir_nodo()
    asignador.incrementar(node_id)

    try:
        resultado = asignador.ejecutar_tarea(node_id, servicio_id, payload)
        return jsonify({
            "servicio": servicio_id,
            "nodo": node_id,
            "resultado": resultado
        })
    except Exception as e:
        logger.error(f"Error ejecutando tarea en nodo {node_id}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        asignador.decrementar(node_id)


# ---------------- ENDPOINT INTERNO DE WORKER ----------------

@app.route('/worker/ejecutar', methods=['POST'])
def worker_ejecutar():
    """
    Endpoint interno. Solo lo llama el líder para delegar una tarea
    a este nodo directamente, sin pasar por la lógica de elección.
    """
    data = request.get_json()
    servicio_id = data.get('servicio')
    payload = data.get('payload', {})

    if servicio_id not in asignador.SERVICIOS:
        return jsonify({'error': 'Servicio no soportado'}), 400

    asignador.incrementar(bully.NODE_ID)

    try:
        resultado = asignador._ejecutar_local(servicio_id, payload)
        return jsonify(resultado)
    except Exception as e:
        logger.error(f"Error en worker local: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        asignador.decrementar(bully.NODE_ID)


# ---------------- ENDPOINTS BULLY ----------------

@app.route('/bully/election', methods=['POST'])
def recibir_election():
    data = request.get_json()
    emisor_id = data["node_id"]
    logger.info(f"[Nodo {bully.NODE_ID}] ELECTION recibido de nodo {emisor_id}")

    if bully.NODE_ID > emisor_id:
        threading.Thread(target=bully.iniciar_eleccion, daemon=True).start()
        return jsonify({"msg": "ok"}), 200

    return jsonify({"msg": "ignorado"}), 200


@app.route('/bully/coordinator', methods=['POST'])
def recibir_coordinator():
    data = request.get_json()
    nuevo_lider = data["node_id"]
    with bully.estado["lock"]:
        bully.estado["lider_actual"] = nuevo_lider
        bully.estado["en_eleccion"] = False
    logger.info(f"[Nodo {bully.NODE_ID}] Nuevo líder: {nuevo_lider}")
    return jsonify({"msg": "ok"}), 200


@app.route('/bully/status', methods=['GET'])
def bully_status():
    return jsonify({
        "node_id": bully.NODE_ID,
        "lider_actual": bully.estado["lider_actual"],
        "registro_carga": asignador.estado_registro()
    }), 200


# ---------------- HEALTH ----------------

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200