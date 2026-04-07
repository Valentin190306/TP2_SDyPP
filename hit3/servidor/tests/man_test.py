import threading
import http.client
import json
import time
import random
import string

HOST = "localhost"
PORT = 80
ENDPOINT = "/getRemoteTask"

# Configuración de carga
NUM_WORKERS = 10          # cantidad de hilos concurrentes
DURATION = 3            # segundos de prueba
REQUESTS_PER_WORKER = 0  # 0 = sin límite (hasta que termine DURATION)

lock = threading.Lock()
stats = {
    "ok": 0,
    "error": 0,
    "total": 0
}

def random_text(length=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def build_payload():
    if random.random() < 0.5:
        return {
            "servicio": "texto",
            "payload": {
                "texto": random_text(20)
            }
        }
    else:
        return {
            "servicio": "hash",
            "payload": {
                "input": random_text(20),
                "algoritmo": random.choice(["sha1", "sha256", "md5"])
            }
        }

def send_request():
    time.sleep(random.uniform(0.01, 0.05))  # Simula tiempo entre solicitudes
    try:
        conn = http.client.HTTPConnection(HOST, PORT, timeout=5)
        payload = build_payload()
        body = json.dumps(payload)

        conn.request(
            "POST",
            ENDPOINT,
            body=body,
            headers={"Content-Type": "application/json"}
        )

        response = conn.getresponse()
        response.read()

        with lock:
            stats["total"] += 1
            if 200 <= response.status < 300:
                stats["ok"] += 1
            else:
                stats["error"] += 1

        conn.close()

    except Exception:
        with lock:
            stats["total"] += 1
            stats["error"] += 1

def worker(stop_time):
    count = 0
    while time.time() < stop_time:
        if REQUESTS_PER_WORKER and count >= REQUESTS_PER_WORKER:
            break
        send_request()
        count += 1

def main():
    stop_time = time.time() + DURATION
    threads = []

    for _ in range(NUM_WORKERS):
        t = threading.Thread(target=worker, args=(stop_time,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print("=== RESULTADOS ===")
    print(f"Total requests: {stats['total']}")
    print(f"OK: {stats['ok']}")
    print(f"Errores: {stats['error']}")
    if stats["total"] > 0:
        print(f"Success rate: {stats['ok'] / stats['total'] * 100:.2f}%")

if __name__ == "__main__":
    main()