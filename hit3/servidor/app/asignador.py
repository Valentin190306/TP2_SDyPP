# asignador.py
import os
import threading
import logging
import requests

logger = logging.getLogger("Asignador")

NODE_ID = int(os.environ.get("NODE_ID", 1))
PEERS = [p.strip() for p in os.environ.get("PEERS", "").split(",") if p.strip()]

SERVICIOS = {
    "texto": "/invertirTexto",
    "hash":  "/hash"
}

# Registro de carga de cada nodo, incluyendo el propio
_registro = {NODE_ID: 0}
_lock = threading.Lock()

for peer in PEERS:
    peer_id = int(peer.split(":")[0].split("_")[-1])
    _registro[peer_id] = 0


def _url_servicio(node_id, servicio_id):
    """Devuelve la URL del servicio en el nodo indicado."""
    if node_id == NODE_ID:
        base = os.environ.get(
            "SERVICIO_A_URL" if servicio_id == "texto" else "SERVICIO_B_URL"
        )
    else:
        peer = next((p for p in PEERS if f"_{node_id}:" in p), None)
        if peer is None:
            raise ValueError(f"No se encontró peer para nodo {node_id}")
        # host = peer.split(":")[0]  # ej: "servidor_2
        # Convencion: servicio_a_N y servicio_b_N en puerto 8080
        svc = "a" if servicio_id == "texto" else "b"
        base = f"http://servicio_{svc}_{node_id}:8080"

    endpoint = SERVICIOS[servicio_id]
    return f"{base}{endpoint}"


def elegir_nodo():
    """Devuelve el node_id con menos tareas activas."""
    with _lock:
        return min(_registro, key=_registro.get)


def incrementar(node_id):
    with _lock:
        _registro[node_id] = _registro.get(node_id, 0) + 1
        logger.info(f"Estado de registro {dict(_registro)}")

def decrementar(node_id):
    with _lock:
        _registro[node_id] = max(0, _registro.get(node_id, 0) - 1)
        logger.info(f"Estado de registro {dict(_registro)}")



def actualizar_desde_peer(node_id, tareas_activas):
    """Llamado cuando un peer reporta su carga."""
    with _lock:
        _registro[node_id] = tareas_activas


def estado_registro():
    with _lock:
        return dict(_registro)


def ejecutar_tarea(node_id, servicio_id, payload):
    if node_id == NODE_ID:
        return _ejecutar_local(servicio_id, payload)
    else:
        try:
            return _delegar_a_peer(node_id, servicio_id, payload)
        except Exception as e:
            logger.warning(f"Nodo {node_id} no responde, marcando como caído y reintentando")
            _marcar_caido(node_id)
            # Reintenta con el siguiente nodo disponible
            nuevo_nodo = elegir_nodo()
            if nuevo_nodo == node_id:
                raise Exception("No hay nodos disponibles") from e
            return ejecutar_tarea(nuevo_nodo, servicio_id, payload)


def _marcar_caido(node_id):
    with _lock:
        _registro[node_id] = 999  # valor alto para que no sea elegido


def _ejecutar_local(servicio_id, payload):
    if servicio_id not in SERVICIOS:
        raise ValueError(f"Servicio no soportado: {servicio_id}")

    url = _url_servicio(NODE_ID, servicio_id)
    logger.info(f"[Nodo {NODE_ID}] Ejecutando {servicio_id} localmente → {url}")

    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def _delegar_a_peer(node_id, servicio_id, payload):
    peer = next((p for p in PEERS if f"_{node_id}:" in p), None)
    if peer is None:
        raise ValueError(f"No se encontró peer para nodo {node_id}")

    url = f"http://{peer}/worker/ejecutar"
    logger.info(f"[Nodo {NODE_ID}] Delegando {servicio_id} a nodo {node_id} → {url}")

    response = requests.post(url, json={
        "servicio": servicio_id,
        "payload": payload
    }, timeout=15)
    response.raise_for_status()
    return response.json()