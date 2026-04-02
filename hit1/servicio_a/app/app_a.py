from flask import Flask, request, jsonify
import logging
import sys

app = Flask(__name__)

# no me olvide de lo artesanal Croch, tranquilo
def invertirString(txt):
    resultado = ""
    for char in txt:
        resultado = char + resultado
    return resultado

@app.route('/invertirTexto', methods=['POST'])
def ejecutar_tarea():
    data = request.get_json()
    texto = data.get('texto', '')
    resultado = invertirString(texto)
    return jsonify({'resultado': resultado})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
    
    
