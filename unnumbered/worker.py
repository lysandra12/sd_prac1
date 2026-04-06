#!/usr/bin/env python3


import Pyro5.api
import uuid
import sys
import time
import uuid

class Worker:
    def __init__(self, worker_id):
        self.worker_id = worker_id
    @Pyro5.api.expose
    def ticket(self):
        print(f"worker {self.worker_id} ha generado un ticket")
        return str(uuid.uuid4())

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

    try:
        print(f"worker ready")
        daemon.requestLoop()
    except KeyboardInterrupt:
        print(f"\n[Worker {args.id}] Deteniendo...")
        daemon.close()
        sys.exit(0)

if __name__ == "__main__":
    main()
