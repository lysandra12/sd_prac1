#!/usr/bin/env python3
import Pyro5.api
import threading
import sys
import os

ns_host = os.getenv('PYRO_NS_HOST', 'localhost')
lb_host = os.getenv('LB_HOST',      'localhost')


@Pyro5.api.expose
class LoadBalancer:
    def __init__(self, ns):
        self.lock           = threading.Lock()
        self.current_worker = 0
        self._ns            = ns
        registros = ns.list()
        self.uris = [
            uri for nombre, uri in registros.items()
            if nombre.startswith("worker_")
        ]
        if not self.uris:
            raise RuntimeError("No se encontraron workers. Arrancarlos antes que el LB.")
        print(f"LoadBalancer: {len(self.uris)} workers registrados")

    def _elegir_worker(self):
        with self.lock:
            uri = self.uris[self.current_worker]
            self.current_worker = (self.current_worker + 1) % len(self.uris)
        return uri

    def generar_ticket_numbered(self, seat_id, client_id):
        try:
            with Pyro5.api.Proxy(self._elegir_worker()) as w:
                return w.ticket_numbered(seat_id, client_id)
        except Exception as e:
            return False, f"Error: {e}"

    def generar_ticket_unnumbered(self, client_id):
        try:
            with Pyro5.api.Proxy(self._elegir_worker()) as w:
                return w.ticket_unnumbered(client_id)
        except Exception as e:
            return False, f"Error: {e}"

    def get_all_stats(self):
        """
        Consulta get_stats() en cada worker y devuelve un resumen agregado.
        Llamar desde el cliente al terminar el benchmark.
        """
        stats_list   = []
        total_ops    = 0
        total_ok     = 0
        total_fail   = 0
        max_elapsed  = 0.0

        for uri in self.uris:
            try:
                with Pyro5.api.Proxy(uri) as w:
                    s = w.get_stats()
                stats_list.append(s)
                total_ops   += s["total"]
                total_ok    += s["success"]
                total_fail  += s["fail"]
                if s["elapsed_s"] > max_elapsed:
                    max_elapsed = s["elapsed_s"]
            except Exception as e:
                stats_list.append({"worker_id": "?", "error": str(e)})

        aggregate_throughput = total_ops / max_elapsed if max_elapsed > 0 else 0.0

        return {
            "workers":              stats_list,
            "aggregate": {
                "total_ops":        total_ops,
                "total_success":    total_ok,
                "total_fail":       total_fail,
                "wall_time_s":      round(max_elapsed, 3),
                "throughput_ops_s": round(aggregate_throughput, 2),
            }
        }

    def get_estado(self):
        return len(self.uris)


def main():
    ns     = Pyro5.api.locate_ns(ns_host, port=9090)
    lb     = LoadBalancer(ns)
    daemon = Pyro5.api.Daemon(host=lb_host, port=9099)
    uri    = daemon.register(lb, "load_balancer")
    ns.register("load_balancer", uri)

    print(f"Load Balancer listo | uri={uri}")
    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        print("\nLoad Balancer: Deteniendo...")
        daemon.close()
        sys.exit(0)


if __name__ == "__main__":
    main()
