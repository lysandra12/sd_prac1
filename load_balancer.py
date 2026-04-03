#!/usr/bin/env python3

import Pyro5.api
import uuid
import threading
import time
from collections import defaultdict
import random 
import sys
class LoadBalancer:
    def __init__(self, ns):
        self.limite = 20000
        self.contador = 0
        self.contador_lock = threading.Lock()  # Para operaciones atómicas
        self.worker_lock = threading.Lock()
        registros = ns.list()  # Devuelve un dict {nombre: uri}
        self.uris = [uri for nombre, uri in registros.items() if nombre.startswith("worker")]  

    @Pyro5.api.expose
    def _elegir_worker(self):
        len = len(self.uris)
        numero = random.randint(1, len)  
        return self.uris[numero]

    @Pyro5.api.expose
    def generar_ticket(self):
        worker_uri = self._elegir_worker()
        worker = Pyro5.api.Proxy(worker_uri)
        with self.contador_lock:
            if self.contador >= self.limite:
                return False, "Límite de tickets alcanzado"
            self.contador += 1
            numero_ticket = worker.generar_ticket()
            return True, numero_ticket

    @Pyro5.api.expose
    def get_estado(self):
        with self.worker_lock:
            return self.contador, len(self.uris)

    @Pyro5.api.expose
    def reset(self):
        with self.worker_lock:
            self.contador = 0

def main():
    ns = Pyro5.api.locate_ns()
    lb = LoadBalancer(ns)
    daemon = Pyro5.api.Daemon(host="127.0.0.1", port=9000)
    uri = daemon.register(lb, "load_balancer")
    
    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        print("\n[LB] Deteniendo...")
        sys.exit(0)


if __name__ == "__main__":
    main()