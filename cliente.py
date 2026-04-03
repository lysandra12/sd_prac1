#!/usr/bin/env python3

import Pyro5.api
import os
import sys

def main():
    # Configuración
    LB_HOST = os.getenv('LB_HOST', '127.0.0.1')
    LB_PORT = int(os.getenv('LB_PORT', '9000'))
    
    # Conectar al load balancer
    ns = Pyro5.api.locate_ns(host=LB_HOST, port=LB_PORT)
    lb_uri = ns.lookup("load_balancer")
    lb = Pyro5.api.Proxy(lb_uri)

    
    print("\nComandos:")
    print("  ticket  - Solicitar un ticket")
    print("  estado  - Ver estado del sistema")
    print("  salir   - Terminar")
    
    while True:
        try:
            comando = input("\n> ").strip().lower()
            
            if comando == 'ticket':
                print("Solicitando ticket...")
                exito, resultado = lb.generar_ticket()
                
                if exito:
                    print(f"Ticket recibido: {resultado}")
                else:
                    print(f"Error: {resultado}")
                    
            elif comando == 'estado':
                estado = lb.get_estado()
                print(f"\n📊 ESTADO DEL SISTEMA")
                print(f"   Tickets entregados: {estado['entregados']}")
                print(f"   Límite: {estado['limite']}")
                print(f"   Disponibles: {estado['disponibles']}")
                print(f"   Workers activos: {estado['total_workers']}")
                for w in estado['workers']:
                    print(f"      - Worker {w['id']}: {'✅ activo' if w['activo'] else '❌ inactivo'}")
                    
            elif comando == 'salir':
                break
            else:
                print("Comando no reconocido. Usa: ticket, estado, salir")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
    
    print("\n¡Adiós!")


if __name__ == "__main__":
    main()