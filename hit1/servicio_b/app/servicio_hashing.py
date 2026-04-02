import sys
import hashlib
import logging

from flask import Flask, request, jsonify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",    
    handlers=[logging.StreamHandler(sys.stdout)]
    )

logger = logging.getLogger("ServicioHashing")

app = Flask(__name__)

import hashlib

ALGORITMOS_PERMITIDOS = {
    "sha256",
    "sha512",
    "sha1",
    "md5"
}

@app.route('/hash', methods=['POST'])
def ejecutarTarea():
    data = request.get_json()

    if not data or 'input' not in data:
        return jsonify({'error': 'Falta "input"'}), 400

    algoritmo = data.get("algoritmo", "sha256").lower()

    if algoritmo not in ALGORITMOS_PERMITIDOS:
        return jsonify({'error': 'Algoritmo no soportado'}), 400

    input_str = data['input']
    logger.info(f"Input recibido. Algoritmo={algoritmo}")

    hash_object = hashlib.new(algoritmo)
    hash_object.update(input_str.encode("utf-8"))
    hash_hex = hash_object.hexdigest()

    logger.info(f"Hash generado")

    return jsonify({
        "algoritmo": algoritmo,
        "hash": hash_hex
    })

