#!/usr/bin/env python3
"""
Worker de Tickets - Genera UUIDs (unnumbered tickets).
Se registra en el Name Server como "worker.ticket.1", "worker.ticket.2", etc.
"""

import Pyro5.api
import uuid
import sys
import time

class WorkerTicket:
    
    def __init__(self, worker_id=1, contador_uri=None):
        self.worker_id = worker_id
        self.contador_uri = contador_uri
        self.contador = None  
    
    def _get_contador(self):
        """Obtiene el proxy al Worker Contador (con conexión bajo demanda)
        TODO: cambiar el if de self.contador_uri cuando sepa si voy a pasarlo directamente o no"""        
        if self.contador is None: #si no se ha coenctado nunca
            if self.contador_uri:
                self.contador = Pyro5.api.Proxy(self.contador_uri)
            else:
                # Buscar automáticamente en el Name Server
                ns = Pyro5.api.locate_ns()
                uri = ns.lookup("worker.contador")
                self.contador = Pyro5.api.Proxy(uri)
        return self.contador
    
    @Pyro5.api.expose
    def generar_ticket(self):
        try:
            contador = self._get_contador()
            disponible, numero = contador.reservar_ticket()
            
            if disponible:
                # Generar UUID (ticket sin número)
                ticket = str(uuid.uuid4())
                print(f"[Worker {self.worker_id}] Ticket generado: {ticket} (N° {numero})")
                return True, ticket
            else:
                print(f"[Worker {self.worker_id}] Rechazado: límite alcanzado")
                return False, "No hay tickets disponibles. Límite alcanzado."
                
        except Exception as e:
            print(f"[Worker {self.worker_id}] Error: {e}")
            return False, f"Error interno: {e}"
    
    @Pyro5.api.expose
    def saludar(self):
        """Método de prueba para verificar conectividad"""
        return f"Hola, soy el Worker {self.worker_id}"


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Worker de Tickets')
    parser.add_argument('--id', type=int, default=1, help='ID del worker')
    parser.add_argument('--port', type=int, default=9001, help='Puerto para este worker')
    parser.add_argument('--contador-uri', type=str, default=None, 
                        help='URI directa del Worker Contador (opcional)')
    args = parser.parse_args()
    
    HOST = '0.0.0.0'
    PORT = args.port
    WORKER_ID = args.id
    
    # Crear el daemon
    daemon = Pyro5.api.Daemon(host=HOST, port=PORT)
    
    # Registrar el objeto
    worker = WorkerTicket(worker_id=WORKER_ID, contador_uri=args.contador_uri)
    uri = daemon.register(worker, f"worker.ticket.{WORKER_ID}")
    
    # Conectar al Name Server
    try:
        ns = Pyro5.api.locate_ns()
        ns.register(f"worker.ticket.{WORKER_ID}", uri)
        print(f"[Worker {WORKER_ID}] Registrado en Name Server como 'worker.ticket.{WORKER_ID}'")
        print(f"[Worker {WORKER_ID}] URI: {uri}")
    except Exception as e:
        print(f"[Worker {WORKER_ID}] Error conectando al Name Server: {e}")
        print("[Worker] Asegúrate de que el Name Server esté corriendo.")
        sys.exit(1)
    
    print(f"[Worker {WORKER_ID}] Escuchando en {HOST}:{PORT}")
    print("[Worker] Presiona Ctrl+C para detener")
    
    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        print(f"\n[Worker {WORKER_ID}] Deteniendo...")
        try:
            ns.remove(f"worker.ticket.{WORKER_ID}")
        except:
            pass


if __name__ == "__main__":
    main()