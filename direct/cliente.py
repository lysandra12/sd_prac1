#!/usr/bin/env python3
import Pyro5.api
import time
import sys
import os

ns_host = os.getenv('PYRO_NS_HOST', 'localhost')


def leer_benchmark_numbered(archivo):
    with open(archivo, 'r') as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith('#'):
                continue
            partes = linea.split()
            yield partes[1], partes[2]   # client_id, seat_id


def leer_benchmark_unnumbered(archivo):
    with open(archivo, 'r') as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith('#'):
                continue
            partes = linea.split()
            yield partes[1]              # client_id


def imprimir_stats(modo, exitos, fallos, elapsed, worker_stats):
    total = exitos + fallos
    throughput = total / elapsed if elapsed > 0 else 0
    print(f"\n{'='*50}")
    print(f"RESULTADOS CLIENTE — modo: {modo}")
    print(f"{'='*50}")
    print(f"  Exitos          : {exitos}")
    print(f"  Fallos          : {fallos}")
    print(f"  Total enviadas  : {total}")
    print(f"  Tiempo total    : {elapsed:.3f} s")
    print(f"  Throughput      : {throughput:.2f} ops/s")

    if worker_stats:
        agg = worker_stats.get("aggregate", {})
        print(f"\n--- Stats agregadas de workers ---")
        print(f"  Ops procesadas  : {agg.get('total_ops', '?')}")
        print(f"  Exitos workers  : {agg.get('total_success', '?')}")
        print(f"  Fallos workers  : {agg.get('total_fail', '?')}")
        print(f"  Tiempo workers  : {agg.get('wall_time_s', '?')} s")
        print(f"  Throughput real : {agg.get('throughput_ops_s', '?')} ops/s")
        print(f"\n--- Stats por worker ---")
        for w in worker_stats.get("workers", []):
            if "error" in w:
                print(f"  Worker ?: error al consultar — {w['error']}")
            else:
                print(
                    f"  Worker {w['worker_id']}: "
                    f"{w['success']} OK / {w['fail']} KO | "
                    f"{w['elapsed_s']} s | {w['throughput_ops']} ops/s"
                )
    print(f"{'='*50}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Cliente Pyro5')
    parser.add_argument('--modo', choices=['numbered', 'unnumbered'], required=True)
    args = parser.parse_args()

    ns     = Pyro5.api.locate_ns(ns_host, 9090)
    lb_uri = ns.lookup("load_balancer")
    lb     = Pyro5.api.Proxy(lb_uri)

    exitos = 0
    fallos = 0
    inicio = time.time()

    try:
        if args.modo == 'numbered':
            for client_id, seat_id in leer_benchmark_numbered("benchmark_numbered_60000.txt"):
                try:
                    ok, _ = lb.generar_ticket_numbered(seat_id, client_id)
                    if ok:
                        exitos += 1
                    else:
                        fallos += 1
                except Exception as e:
                    print(f"Error: {e}")
                    fallos += 1
        else:
            for client_id in leer_benchmark_unnumbered("benchmark_unnumbered_20000.txt"):
                try:
                    ok, _ = lb.generar_ticket_unnumbered(client_id)
                    if ok:
                        exitos += 1
                    else:
                        fallos += 1
                except Exception as e:
                    print(f"Error: {e}")
                    fallos += 1
    except KeyboardInterrupt:
        pass

    elapsed = time.time() - inicio

    # Recoger stats de todos los workers a traves del LB
    try:
        worker_stats = lb.get_all_stats()
    except Exception as e:
        print(f"No se pudieron obtener stats de workers: {e}")
        worker_stats = None

    imprimir_stats(args.modo, exitos, fallos, elapsed, worker_stats)
    lb._pyroRelease()


if __name__ == "__main__":
    main()
