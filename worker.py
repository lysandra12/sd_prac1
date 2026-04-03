#!/usr/bin/env python3
"""
Worker simple
- Se registra en el load balancer
- Procesa tickets cuando el load balancer se los envía
"""

import Pyro5.api
import uuid
import sys
import time

class Worker:
    def __init__(self, worker_id):
        self.worker_id = worker_id
    @Pyro5.api.expose
    def generar_ticket(self):
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
    parser.add_argument('--port', type=int, default=9001, help='Puerto donde escuchar')
    parser.add_argument('--lb-host', default='127.0.0.1', help='Host del load balancer')
    parser.add_argument('--lb-port', type=int, default=9000, help='Puerto del load balancer')
    args = parser.parse_args()
    
    ns = Pyro5.api.locate_ns()

    worker = Worker(args.id, ns)
    daemon = Pyro5.api.Daemon(host="127.0.0.1", port=args.port)
    daemon.register(f"worker_{args.id}", worker) 

   
    try:
        daemon.request_loop()
    except KeyboardInterrupt:
        print(f"\n[Worker {args.id}] Deteniendo...")
        sys.exit(0)

if __name__ == "__main__":
    main()