# bully.py
import os
import threading
import logging
import requests

logger = logging.getLogger("Bully")

NODE_ID = int(os.environ.get("NODE_ID", 1))
PEERS = [p.strip() for p in os.environ.get("PEERS", "").split(",") if p.strip()]

estado = {
    "lider_actual": None,
    "en_eleccion": False,
    "lock": threading.Lock()
}


def iniciar_eleccion():
    with estado["lock"]:
        if estado["en_eleccion"]:
            return
        estado["en_eleccion"] = True

    logger.info(f"[Nodo {NODE_ID}] Iniciando elección")

    peers_mayores = [p for p in PEERS if int(p.split(":")[0].split("_")[-1]) > NODE_ID]
    alguien_respondio = False

    for peer in peers_mayores:
        try:
            r = requests.post(f"http://{peer}/bully/election",
                              json={"node_id": NODE_ID}, timeout=2)
            if r.status_code == 200:
                alguien_respondio = True
        except:
            pass

    if not alguien_respondio:
        proclamarse_lider()
    else:
        with estado["lock"]:
            estado["en_eleccion"] = False


def proclamarse_lider():
    with estado["lock"]:
        estado["lider_actual"] = NODE_ID
        estado["en_eleccion"] = False

    logger.info(f"[Nodo {NODE_ID}] Soy el nuevo líder")

    for peer in PEERS:
        try:
            requests.post(f"http://{peer}/bully/coordinator",
                          json={"node_id": NODE_ID}, timeout=2)
        except:
            pass


def monitorear_lider():
    while True:
        threading.Event().wait(5)

        with estado["lock"]:
            lider = estado["lider_actual"]
            soy_lider = (lider == NODE_ID)
            en_eleccion = estado["en_eleccion"]

        if soy_lider or en_eleccion:
            continue

        if lider is None:
            iniciar_eleccion()
            continue

        peer_lider = next((p for p in PEERS if str(lider) in p), None)

        if peer_lider is None:
            iniciar_eleccion()
            continue

        try:
            r = requests.get(f"http://{peer_lider}/bully/status", timeout=2)
            if r.status_code != 200:
                raise Exception("Líder no responde")
        except:
            logger.warning(f"[Nodo {NODE_ID}] Líder {lider} caído, iniciando elección")
            with estado["lock"]:
                estado["lider_actual"] = None
            iniciar_eleccion()