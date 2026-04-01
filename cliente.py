#!/usr/bin/env python3
import Pyro5.api
import sys
import time

def main():
    import os
    LB_HOST = os.getenv('LB_HOST', 'localhost')
    LB_PORT = int(os.getenv('LB_PORT', '9000'))
    
    # El proxy apunta a NGINX, que actúa como load balancer
    # El nombre "worker" es arbitrario - NGINX solo reenvía TCP
    proxy = Pyro5.api.Proxy(f"PYRO:worker@{LB_HOST}:{LB_PORT}")
    
    print(f"Conectado a load balancer en {LB_HOST}:{LB_PORT}")
    print("Escribe 'ticket' para solicitar un ticket, 'estado' para ver el contador, 'salir' para terminar")
    
    while True:
        try:
            comando = input("\n> ").strip().lower()
            
            if comando == 'ticket':
                print("Solicitando ticket...")
                exito, resultado = proxy.generar_ticket()
                
                if exito:
                    print(f"Ticket recibido: {resultado}")
                else:
                    print(f"Error: {resultado}")
                    
            elif comando == 'estado': #no se pasa por nginx, conectamos con el contador directamentes
                try:
                    ns = Pyro5.api.locate_ns()
                    contador_uri = ns.lookup("worker.contador")
                    contador = Pyro5.api.Proxy(contador_uri)
                    estado = contador.get_estado()
                    print(f"📊 Estado: {estado}")
                except Exception as e:
                    print(f"No se pudo obtener estado: {e}")
                    
            elif comando == 'salir':
                break
            else:
                print("Comandos: ticket, estado, salir")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
    
    print("Adiós!")


if __name__ == "__main__":
    main()