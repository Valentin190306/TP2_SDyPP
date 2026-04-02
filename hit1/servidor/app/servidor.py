import sys
import logging
from flask import Flask, request, jsonify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",    
    handlers=[logging.StreamHandler(sys.stdout)]
    )

logger = logging.getLogger("Servidor")

app = Flask(__name__)

@app.route('/getRemoteTask', methods=['POST'])
def ejecutaTareaRemota():
    data = request.get_json()

    if not data or 'servicio' not in data:
        return jsonify({'error': 'Falta "servicio"'}), 400

    servicio = data['servicio']
    logger.info(f"Solicitud recibida para servicio: {servicio}")

    # Aquí podrías agregar lógica para determinar qué tarea ejecutar según el servicio solicitado
    # Por simplicidad, vamos a devolver una respuesta genérica
    return jsonify({
        "servicio": servicio,
        "resultado": f"Tarea ejecutada para el servicio {servicio}"
    })
    
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)