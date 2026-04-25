#!/usr/bin/env python3

import Pyro5.api
import os
import sys
from indirect.unnumbered.Clientes import Cliente
import time

def leer_archivo_linea_por_linea(nombre_archivo):
    """Versión que procesa línea por línea (eficiente para archivos grandes)"""

    with open(nombre_archivo, 'r') as archivo:
        for linea in archivo:
            linea = linea.strip()

            # Ignorar líneas vacías o comentarios
            if not linea or linea.startswith('#'):
                continue

            # Intentar parsear la línea
            partes = linea.split()
            yield partes[1], partes[2], partes[0]


def main():

    # Conectar al load balancer
    ns = Pyro5.api.locate_ns("10.0.1.74", 9090)
    lb_uri = ns.lookup("load_balancer")
    lb = Pyro5.api.Proxy(lb_uri)

    generador = leer_archivo_linea_por_linea("benchmark_unnumbered_20000.txt")  # Crear generador >

    inicio = time.time()
    for i in generador:  # Iterar sobre el generador
        try:
            exito, resultado = lb.generar_ticket()
            print(f"Cliente, Compra con exito: {resultado}")
            # Procesar cliente aquí
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"A Error: {e}")

    fin = time.time()
    tiempo_total = fin - inicio
    print(f"Tiempo total: {tiempo_total:.2f} segundos")

    generador = leer_archivo_linea_por_linea("benchmark_numbered_20000.txt")  # Crear generador >
if __name__ == "__main__":
    main()
