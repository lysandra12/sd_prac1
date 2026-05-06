#!/usr/bin/env python3
import Pyro5.api
import sys
import os
import time
import threading
import redis

TOTAL_TICKETS = 20000

redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port  = int(os.getenv('REDIS_PORT', '6379'))
ns_host     = os.getenv('PYRO_NS_HOST', 'localhost')


@Pyro5.api.expose
class Worker:
    def __init__(self, worker_id):
        self.worker_id    = worker_id
        self.redis_client = redis.Redis(
            host=redis_host, port=redis_port, decode_responses=True
        )
        self._lock          = threading.Lock()
        self._success_count = 0
        self._fail_count    = 0
        self._start_time    = None
        self._last_time     = None

    def _record(self, success: bool):
        with self._lock:
            now = time.time()
            if self._start_time is None:
                self._start_time = now
            self._last_time = now
            if success:
                self._success_count += 1
            else:
                self._fail_count += 1

    def ticket_numbered(self, seat_id, client_id):
        was_free = self.redis_client.setnx(f"seat:{seat_id}", client_id)
        if was_free:
            sold = self.redis_client.incr("total_sold")
            result = True, f"Asiento {seat_id} vendido a {client_id} (Total: {sold})"
        else:
            owner  = self.redis_client.get(f"seat:{seat_id}")
            result = False, f"Asiento {seat_id} ya ocupado por {owner}"
        self._record(result[0])
        return result

    def ticket_unnumbered(self, client_id):
        sold = self.redis_client.incr("total_sold")
        if sold <= TOTAL_TICKETS:
            result = True, f"Ticket #{sold} vendido a {client_id}"
        else:
            self.redis_client.decr("total_sold")
            result = False, "No quedan tickets disponibles"
        self._record(result[0])
        return result

    def get_stats(self):
        """Devuelve metricas de este worker. Llamado por el load balancer al final."""
        with self._lock:
            total   = self._success_count + self._fail_count
            elapsed = (self._last_time - self._start_time) \
                      if self._start_time and self._last_time else 0.0
            throughput = total / elapsed if elapsed > 0 else 0.0
            return {
                "worker_id":      self.worker_id,
                "success":        self._success_count,
                "fail":           self._fail_count,
                "total":          total,
                "elapsed_s":      round(elapsed, 3),
                "throughput_ops": round(throughput, 2),
            }

    def print_stats(self):
        s = self.get_stats()
        print(
            f"\n=== Worker {s['worker_id']} ===\n"
            f"  Exitos    : {s['success']}\n"
            f"  Fallos    : {s['fail']}\n"
            f"  Total ops : {s['total']}\n"
            f"  Tiempo    : {s['elapsed_s']} s\n"
            f"  Throughput: {s['throughput_ops']} ops/s"
        )


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Worker Pyro5')
    parser.add_argument('--id',   type=int, required=True)
    parser.add_argument('--host', type=str,
                        default=os.getenv('WORKER_HOST', 'localhost'))
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()

    rc = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    try:
        rc.ping()
        print(f"Worker {args.id}: Redis OK ({redis_host}:{redis_port})")
    except redis.exceptions.ConnectionError:
        print(f"Worker {args.id}: No se pudo conectar a Redis")
        sys.exit(1)
    rc.close()

    ns     = Pyro5.api.locate_ns(ns_host, 9090)
    worker = Worker(args.id)
    daemon = Pyro5.api.Daemon(host=args.host, port=args.port)
    nombre = f"worker_{args.id}"
    uri    = daemon.register(worker, nombre)
    ns.register(nombre, uri)

    print(f"Worker {args.id} listo | uri={uri}")
    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        worker.print_stats()
        daemon.close()
        sys.exit(0)


if __name__ == "__main__":
    main()
