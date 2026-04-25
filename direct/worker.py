#!/usr/bin/env python3
import Pyro5.api
import uuid
import sys
import time
import uuid
import os
import redis

redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', '6379'))

class Worker:
    def __init__(self, worker_id):
        self.worker_id = worker_id

    @Pyro5.api.expose
    def ticket_numbered(self, redis_client):
        if redis_client.get("total_sold") is 20000:
            return False, "Límite de tickets alcanzado"
        else:
            sold = redis_client.incr("total_sold")        
            print(f"worker {self.worker_id} ha generado un ticket")
        return str(uuid.uuid4())
    
    @Pyro5.api.expose
    def ticker_unnumbered(self, redis_client, seat_id, client_id):
        was_free = redis_client.setnx(seat_id, "OCCUPIED")
        if was_free:
            sold = redis_client.incr("total_sold")
            return True, f"Asiento {seat_id} vendido a {client_id} (Total: {sold}/{TOTAL_SEATS})"
        owner = redis_client.get(seat_id)
        return False, f"Asiento {seat_id} ya ocupado por {owner}"

    @Pyro5.api.expose
    def saludar(self):
        """Método de prueba"""
        return f"Hola, soy el Worker {self.worker_id}"

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Worker')
    parser.add_argument('--id', type=int, required=True, help='ID del worker')
    args = parser.parse_args()

    ns = Pyro5.api.locate_ns("10.0.1.74",9090)

    worker = Worker(args.id)
    daemon = Pyro5.api.Daemon(host="10.0.1.254", port=9909)  # Puerto automático
    nombre_objeto = "worker_" + str(args.id)
    uri = daemon.register(worker, nombre_objeto)
    ns.register(nombre_objeto, uri)

    redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    redis_client.flushdb()
    redis_client.set("total_sold", 0)
    try:
        redis_client.ping()
        print(f"Worker {worker}: Conexión exitosa a Redis")
    except redis.exceptions.ConnectionError:
        print(f"Worker {worker}: No se pudo conectar a Redis")
        sys.exit(1)

    try:
        print(f"worker ready")
        daemon.requestLoop()
    except KeyboardInterrupt:
        print(f"\n[Worker {args.id}] Deteniendo...")
        daemon.close()
        sys.exit(0)

if __name__ == "__main__":
    main()
