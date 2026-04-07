# servidor.py
import threading
import time
import logging
import sys

import bully
from asignador import NODE_ID
from api import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("Servidor")


if __name__ == '__main__':
    logger.info(f"Iniciando nodo {bully.NODE_ID}")
    logger.info(f"Peers: {bully.PEERS}")

    # Esperar a que los servicios locales estén listos
    time.sleep(NODE_ID * 1)

    # Arrancar monitor de líder en background
    threading.Thread(target=bully.monitorear_lider, daemon=True).start()

    # Disparar primera elección
    threading.Thread(target=bully.iniciar_eleccion, daemon=True).start()

    app.run(host='0.0.0.0', port=8080, threaded=True)