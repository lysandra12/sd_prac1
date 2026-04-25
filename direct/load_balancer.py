#!/usr/bin/env python3
import socket
import Pyro5.api
import uuid
import threading
import time
import collections
import random
import sys

class LoadBalancer:
    def __init__(self, ns):
        self.limite = 20000
        self.contador = 0
        self.contador_lock = threading.Lock()
        self.current_worker = 0
        registros = ns.list()  # devuelve {nombre: uri}
        self.uris = [
            uri for nombre, uri in registros.items()
            if nombre.startswith("worker")
        ]

    def _elegir_worker(self):
        total = len(self.uris)
        if total == 0:
            raise RuntimeError("No hay workers disponibles")

        print(f"Eligiendo worker entre {total} disponibles")
        worker = self.uris[self.current_worker]
        self.current_worker = (self.current_worker + 1) % total
        return self.uris[self.current_worker - 1]

    @Pyro5.api.expose
    def generar_ticket(self):
        try:
            worker_uri = self._elegir_worker()

            with self.contador_lock:
                if self.contador >= self.limite:
                    return False, "Límite de tickets alcanzado"
                self.contador += 1

            print(f"Enviando solicitud a {worker_uri}")

            with Pyro5.api.Proxy(worker_uri) as worker:
                numero_ticket = worker.ticket_numbered()
                return True, numero_ticket

        except Exception as e:
            return False, f"Error al generar ticket: {e}"

    @Pyro5.api.expose
    def get_estado(self):
        with self.worker_lock:
            return self.contador, len(self.uris)

    @Pyro5.api.expose
    def reset(self):
        with self.worker_lock:
            self.contador = 0

def main():
    ns = Pyro5.api.locate_ns("10.0.1.74", port=9090)
    lb = LoadBalancer(ns)
    ip = socket.gethostbyname(socket.gethostname())
    daemon = Pyro5.api.Daemon(host="10.0.1.67", port=9099)
    uri = daemon.register(lb, "load_balancer")
    ns.register("load_balancer", uri)

    try:
        print(f"Load Balancer ready")
        daemon.requestLoop()
    except KeyboardInterrupt:
        print("\n[LB] Deteniendo...")
        daemon.close()
        sys.exit(0)


if __name__ == "__main__":
    main()
