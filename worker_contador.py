#!/usr/bin/env python3
"""
Worker Contador - Mantiene la cuenta de tickets entregados.
Se registra en el Name Server como "worker.contador"
"""

import Pyro5.api
import sys
import time

class WorkerContador:
    
    def __init__(self, limite=20000):
        self.limite = limite
        self.contador = 0
    
    @Pyro5.api.expose
    def reservar_ticket(self):
        if self.contador < self.limite:
            self.contador += 1
            print(f"[Contador] Ticket {self.contador} reservado. Quedan: {self.limite - self.contador}")
            return True, self.contador
        else:
            print(f"[Contador] Límite alcanzado. No se pueden entregar más tickets.")
            return False, None
    
    @Pyro5.api.expose
    def get_estado(self):

        return {
            'entregados': self.contador,
            'limite': self.limite,
            'disponibles': self.limite - self.contador
        }


def main():
    HOST = '0.0.0.0'  # Escucha en todas las interfaces
    PORT = 9000       # Puerto para este worker
    
    daemon = Pyro5.api.Daemon(host=HOST, port=PORT)
    worker = WorkerContador(limite=20000)
    uri = daemon.register(worker, "worker.contador")
    
    # Conectar al Name Server y registrar el objeto
    try:
        ns = Pyro5.api.locate_ns()
        ns.register("worker.contador", uri)
        print(f"[Contador] Registrado en Name Server: {uri}")
    except Exception as e:
        print(f"[Contador] Error conectando al Name Server: {e}")
        print("[Contador] Asegúrate de que el Name Server esté corriendo.")
        print("[Contador] Para iniciarlo: python -m Pyro5.nameserver")
        sys.exit(1)
    
    print(f"[Contador] Worker Contador escuchando en {HOST}:{PORT}")
    print("[Contador] Presiona Ctrl+C para detener")
    
    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        print("\n[Contador] Deteniendo worker...")
        # Limpiar registro del Name Server
        try:
            ns.remove("worker.contador")
        except:
            pass


if __name__ == "__main__":
    main()