from flask import Flask, request, jsonify
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",    
    handlers=[logging.StreamHandler(sys.stdout)]
    )

logger = logging.getLogger("ServicioInvertirTexto")


app = Flask(__name__)

def invertirString(txt):
    resultado = ""
    for char in txt:
        resultado = char + resultado
    
    logger.info(f"Texto invertido: {resultado}")
    return resultado

@app.route('/invertirTexto', methods=['POST'])
def ejecutarTarea():
    data = request.get_json()
    texto = data.get('texto', '')
    resultado = invertirString(texto)
    return jsonify({'resultado': resultado})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
    
    
